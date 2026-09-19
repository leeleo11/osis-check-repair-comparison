from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def smoke_task(repo_root: Path) -> dict[str, object]:
    path = repo_root / "tasks" / "smoke" / "check_repair_smoke.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def adapter_request(tmp_path: Path) -> dict[str, object]:
    workspace = tmp_path / "workspace"
    candidate = workspace / "candidate_project" / "py"
    candidate.mkdir(parents=True)
    (candidate / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    skills = tmp_path / "skills" / "osis-check-repair"
    (skills / "references").mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: Check repair\ndescription: Diagnose and repair checks.\n---\n# Workflow\nRead before edit.\n",
        encoding="utf-8",
    )
    (skills / "references" / "guide.md").write_text("public guide", encoding="utf-8")
    return {
        "architecture_id": "",
        "task": {
            "task_id": "smoke-adapter",
            "bridge_type": "synthetic",
            "difficulty": "smoke",
            "natural_language_prompt": "Repair the named failed check.",
            "protocol_version": "check-repair-v2",
            "total_timeout_s": 120,
            "metadata": {},
        },
        "workspace": str(workspace),
        "skills_dir": str(skills.parent),
        "model": "test-model",
        "base_url": "https://example.invalid/v1",
        "api_key": "test-only",
        "temperature": 0,
        "request_timeout_s": 30,
        "max_steps": 12,
        "max_output_tokens": 1000,
    }
