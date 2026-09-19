from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


PUBLIC_SMOKE_FIELDS = {
    "task_id",
    "bridge_type",
    "difficulty",
    "natural_language_prompt",
    "protocol_version",
}

FORBIDDEN_TRACKED_PARTS = {
    "runs",
    "reports",
    "private",
    "seeded",
    "candidate_project",
    "check",
    "temperary",
    "result",
    "error",
}


def _tracked_files(repo_root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
    )
    return [Path(line) for line in output.splitlines() if line]


def test_smoke_fixture_has_only_five_public_fields(smoke_task: dict[str, object]) -> None:
    assert set(smoke_task) == PUBLIC_SMOKE_FIELDS
    assert smoke_task["task_id"] == "smoke-synthetic-001"
    prompt = str(smoke_task["natural_language_prompt"]).lower()
    assert "reason_code" not in prompt
    assert "ng_seeded" not in prompt


def test_smoke_fixture_conforms_to_committed_schema(repo_root: Path, smoke_task: dict[str, object]) -> None:
    schema_path = repo_root / "tasks" / "schema" / "check_repair_task.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(smoke_task)
    assert set(smoke_task) <= set(schema["properties"])
    assert schema["additionalProperties"] is False


def test_unignored_tree_contains_no_private_artifact_paths(repo_root: Path) -> None:
    offenders: list[str] = []
    for relative in _tracked_files(repo_root):
        parts = {part.lower() for part in relative.parts}
        if parts & FORBIDDEN_TRACKED_PARTS:
            offenders.append(relative.as_posix())
        if relative.suffix.lower() in {".lcc", ".sqlite", ".db", ".log"}:
            offenders.append(relative.as_posix())
        if relative.name.lower() == "osispost.out":
            offenders.append(relative.as_posix())
    assert offenders == []


def test_public_payload_has_no_machine_path(repo_root: Path, smoke_task: dict[str, object]) -> None:
    serialized = json.dumps(smoke_task, ensure_ascii=False)
    assert not re.search(r"[A-Za-z]:[\\/]", serialized)
    assert str(repo_root) not in serialized
