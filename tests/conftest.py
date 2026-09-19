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
