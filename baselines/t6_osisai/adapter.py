"""T6 calls the parent check-repair agent. It does not rebuild the parent's files."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from baselines._framework_common import finish


def _load_parent_eval(parent: Path):
    import importlib.util

    path = parent / "datasets" / "check_repair" / "run_eval.py"
    if not path.is_file():
        raise FileNotFoundError(f"parent check-repair runner is missing: {path}")
    spec = importlib.util.spec_from_file_location("parent_check_repair_run_eval", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load parent check-repair runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parent_chat(request: dict[str, Any]) -> dict[str, Any]:
    """One parent ``chat_via_agent`` call. The parent session owns skills and the project."""

    parent = Path(str(request.get("parent_repo") or os.environ.get("OSIS_PARENT_REPO") or ""))
    module = _load_parent_eval(parent)
    task_id = str(request["task"]["task_id"])
    samples = module.load_samples(parent / "datasets" / "check_repair" / "samples.json")
    item = next((row for row in samples if str(row.get("id")) == task_id), None)
    if item is None:
        raise FileNotFoundError(f"parent check-repair sample is missing: {task_id}")
    args = SimpleNamespace(
        opencode_url="",
        model=request["model"],
        provider="osisapi",
        variant=request.get("variant") or "",
        timeout=float(request.get("generation_timeout_s") or 1800),
        rebuild=False,
    )
    output = module.chat_via_agent(item, args)
    project_py = module.osis_project_py()
    return {**output, "project_py": str(project_py)}


def _sync_candidate(request: dict[str, Any], output: dict[str, Any]) -> None:
    source = output.get("project_py")
    if not source:
        return
    dest = Path(request["workspace"]) / "candidate_project" / "py"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def run_generation(request: dict[str, Any], *, chat: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T6",
        "framework": "osis-ai-native",
        "interaction_mode": "parent_session",
        "skill_loading": "parent_repo",
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (chat or parent_chat)(request)
        _sync_candidate(request, output)
        metadata.update(
            final_answer=str(output.get("raw") or output.get("final_answer") or ""),
            model_calls=int((output.get("usage") or {}).get("model_calls") or output.get("model_calls") or 0),
            tool_calls=int(output.get("tool_calls") or 0),
            tokens=output.get("usage") or output.get("tokens"),
            latency_s=output.get("latency_s"),
            status="completed",
            stop_reason="completed",
        )
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T6", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
