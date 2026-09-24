"""T6 uses the parent OSIS-AI framework on the same template-free skill snapshot as T1-T5."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import finish
from scripts.create_skill_snapshot import create_snapshot


def _reject_templates(skills: Path) -> None:
    leaked = [
        path.relative_to(skills).as_posix()
        for path in skills.rglob("*")
        if path.name.casefold() == "templates"
    ]
    if leaked:
        raise RuntimeError("check-repair skills still contain templates: " + ", ".join(leaked))


def _agents_source(request: dict[str, Any]) -> Path:
    explicit = request.get("osis_agents_file") or os.environ.get("OSIS_AGENTS_FILE")
    if explicit:
        path = Path(str(explicit))
    else:
        parent = Path(str(request.get("parent_repo") or os.environ.get("OSIS_PARENT_REPO") or ""))
        path = parent / ".agents" / "AGENTS.md"
    if not path.is_file():
        raise FileNotFoundError(f"parent OSIS-AI instructions are missing: {path}")
    return path


def prepare_isolated_env(request: dict[str, Any]) -> Path:
    """Mount the run skill snapshot. Do not mount the parent skill tree."""

    skills = Path(request["skills_dir"])
    workspace = Path(request["workspace"])
    root = workspace / "t6_isolated_project"
    if root.exists():
        shutil.rmtree(root)
    agents = root / ".agents"
    create_snapshot(skills, agents / "skills")
    _reject_templates(agents / "skills")
    shutil.copy2(_agents_source(request), agents / "AGENTS.md")
    candidate_src = workspace / "candidate_project"
    if candidate_src.is_dir():
        shutil.copytree(candidate_src, root / "candidate_project")
    (agents / "opencode.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "instructions": [str((agents / "AGENTS.md").resolve())],
                "permission": {"*": "allow"},
                "default_agent": "build",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "task.json").write_text(
        json.dumps(request["task"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _sync_candidate(request: dict[str, Any], project: Path) -> None:
    source = project / "candidate_project" / "py"
    if not source.is_dir():
        return
    dest = Path(request["workspace"]) / "candidate_project" / "py"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def run_generation(
    request: dict[str, Any],
    *,
    runtime: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T6",
        "framework": "osis-ai-native",
        "interaction_mode": "parent_framework",
        "skill_loading": "template_free_snapshot",
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        project = prepare_isolated_env(request)
        if runtime is None:
            raise FileNotFoundError("isolated OpenCode server is not started by the unit runner")
        output = runtime(request, project)
        _sync_candidate(request, project)
        metadata.update(
            final_answer=str(output.get("raw") or output.get("final_answer") or ""),
            model_calls=int(output.get("model_calls") or 0),
            tool_calls=int(output.get("tool_calls") or 0),
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
