"""T6 native OpenCode session in a per-run isolated project."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from baselines._framework_common import finish


Runtime = Callable[[dict[str, Any], Path, str], dict[str, Any]]


def _prepare_project(request: dict[str, Any]) -> Path:
    workspace = Path(request["workspace"])
    candidate = workspace / "candidate_project"
    isolated = workspace / "t6_isolated_project"
    if isolated.exists():
        shutil.rmtree(isolated)
    isolated.mkdir(parents=True)
    if (candidate / "py").is_dir():
        shutil.copytree(candidate / "py", isolated / "py")
    agents = isolated / ".agents"
    agents.mkdir()
    shutil.copytree(Path(request["skills_dir"]), agents / "skills")
    (agents / "AGENTS.md").write_text(
        "Use the mounted AgentSkills progressively. Work only in this project. "
        "Inspect py before editing, make the smallest repair, compile Python, and report localization JSON.\n",
        encoding="utf-8",
    )
    config = {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [str((agents / "AGENTS.md").resolve())],
        "model": f"comparison/{request['model']}",
        "provider": {
            "comparison": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": request.get("base_url", ""), "apiKey": "{env:OSIS_MODEL_API_KEY}"},
                "models": {request["model"]: {"name": request["model"]}},
            }
        },
        "permission": {"*": "allow"},
    }
    (agents / "opencode.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return isolated


def _wait_healthy(base_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/global/health", timeout=2).status_code == 200:
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise RuntimeError("isolated OpenCode server did not become healthy")


def _native_runtime(request: dict[str, Any], project: Path, prompt: str) -> dict[str, Any]:
    executable = request.get("opencode_executable") or os.environ.get("OPENCODE_EXE") or "opencode"
    port = int(request.get("t6_port") or os.environ.get("T6_AI_PORT", "4097"))
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["OPENCODE_CONFIG_DIR"] = str(project / ".agents")
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    process = subprocess.Popen(
        [str(executable), "serve", "--port", str(port)],
        cwd=str(project),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_healthy(base_url, min(90.0, float(request.get("request_timeout_s", 90))))
        parent = os.environ.get("OSIS_PARENT_REPO")
        if parent:
            sys.path.insert(0, str(Path(parent) / "src"))
        from opencode_client import OpencodeClient, QuestionMonitor, extract_stats, extract_text

        client = OpencodeClient(base_url=base_url, timeout=float(request.get("generation_timeout_s", 1800)))
        session = client.create_session(f"check-repair:{request['task']['task_id']}")
        monitor = QuestionMonitor(client, session, strategy="first", poll_interval=1.0)
        monitor.start()
        try:
            message = client.chat(
                session,
                prompt,
                provider_id="comparison",
                model_id=request["model"],
                timeout=float(request.get("generation_timeout_s", 1800)),
                variant=request.get("variant") or None,
            )
        finally:
            monitor.stop()
        stats = extract_stats(message)
        return {
            "final_answer": extract_text(message),
            "model_calls": int(stats.get("model_calls") or 0),
            "tool_calls": int(stats.get("tool_calls") or 0),
            "tokens": stats,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T6",
        "framework": "osis-ai-native",
        "interaction_mode": "native_stateful",
        "skill_loading": "isolated_native",
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        project = _prepare_project(request)
        prompt = (
            "按 AGENTS.md 的原生工作流修复当前工程中的验算问题。\n\n"
            + json.dumps(request["task"], ensure_ascii=False, indent=2)
        )
        output = (runtime or _native_runtime)(request, project, prompt)
        metadata.update(output)
        candidate_py = Path(request["workspace"]) / "candidate_project" / "py"
        if candidate_py.exists():
            shutil.rmtree(candidate_py)
        shutil.copytree(project / "py", candidate_py)
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T6", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
