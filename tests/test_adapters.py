from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.adapters import ADAPTER_SPECS, get_adapter
from common.manifest import artifact_hashes
from common.tool_policy import CandidateWorkspace, PathPolicyError


def test_all_six_architectures_are_registered_with_distinct_frameworks() -> None:
    assert set(ADAPTER_SPECS) == {"T1", "T2", "T3", "T4", "T5", "T6"}
    assert ADAPTER_SPECS["T2"].framework == "langgraph"
    assert ADAPTER_SPECS["T3"].framework == "smolagents"
    assert ADAPTER_SPECS["T4"].framework == "openhands"
    assert ADAPTER_SPECS["T5"].framework == "crewai"
    assert get_adapter("T6").native_runtime is True
    with pytest.raises(KeyError):
        get_adapter("T7")


def test_candidate_workspace_bounds_reads_and_writes(tmp_path: Path) -> None:
    workspace = CandidateWorkspace(tmp_path / "candidate")
    workspace.write_text("py/main.py", "print('safe')\n")
    assert workspace.read_text("py/main.py") == "print('safe')\n"
    assert workspace.list_files() == ["py/main.py"]
    with pytest.raises(PathPolicyError):
        workspace.write_text("../escape.py", "bad")
    with pytest.raises(PathPolicyError):
        workspace.write_text("py/native.exe", "bad")


def test_artifact_hashes_are_relative_and_stable(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "a.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    first = artifact_hashes(tmp_path)
    second = artifact_hashes(tmp_path)
    assert first == second
    assert set(first) == {"nested/a.json"}
    assert len(first["nested/a.json"]) == 64
