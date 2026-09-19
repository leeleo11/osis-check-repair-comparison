"""Small shared helpers used inside T1-T5 framework processes."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from common.skill_adapter import SkillAdapter
from common.tool_policy import CandidateWorkspace


def load_request(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    return json.loads(Path(args.request).read_text(encoding="utf-8"))


def candidate_workspace(request: dict[str, Any]) -> CandidateWorkspace:
    return CandidateWorkspace(Path(request["workspace"]) / "candidate_project")


def build_prompt(request: dict[str, Any]) -> str:
    task = request["task"]
    return (
        "Repair the named failed OSIS check in the staged candidate project.\n"
        "Use only the mounted public skills and candidate tools. Do not inspect parent datasets, "
        "hidden references, other runs, or evaluator files. Preserve unrelated behavior.\n"
        "At the end, report the final localization JSON and summarize edited files.\n\n"
        + json.dumps(task, ensure_ascii=False, indent=2)
    )


def skill_reader(request: dict[str, Any]) -> SkillAdapter:
    return SkillAdapter(Path(request["skills_dir"]))


def finish(
    workspace: str | Path,
    architecture_id: str,
    metadata: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    result = dict(metadata)
    result.setdefault("architecture_id", architecture_id)
    result["elapsed_s"] = max(0.0, time.monotonic() - started)
    candidate = CandidateWorkspace(root / "candidate_project")
    result["files_written"] = candidate.list_files()
    path = root / f"{architecture_id.lower()}_generation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
