from __future__ import annotations

from pathlib import Path

import pytest

from common.skill_adapter import SkillAdapter, SkillPathError


def _skills(root: Path) -> Path:
    skill = root / "bridge-box"
    reference = skill / "references"
    reference.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: Box bridge\ndescription: Build and repair a box bridge.\n---\n# Body\n",
        encoding="utf-8",
    )
    (reference / "guide.md").write_text("safe reference", encoding="utf-8")
    return root


def test_skill_index_and_hash_are_deterministic(tmp_path: Path) -> None:
    root = _skills(tmp_path / "skills")
    first = SkillAdapter(root)
    second = SkillAdapter(root)
    assert first.skill_index() == [
        {"skill_id": "bridge-box", "name": "Box bridge", "description": "Build and repair a box bridge."}
    ]
    assert first.skill_bundle_hash() == second.skill_bundle_hash()
    assert first.read_skill("bridge-box").startswith("---")
    assert first.read_reference("bridge-box", "references/guide.md") == "safe reference"


@pytest.mark.parametrize("path", ["../outside.md", "../../secret", "/absolute"])
def test_reference_read_rejects_traversal(tmp_path: Path, path: str) -> None:
    adapter = SkillAdapter(_skills(tmp_path / "skills"))
    with pytest.raises(SkillPathError):
        adapter.read_reference("bridge-box", path)


def test_skill_hash_changes_when_snapshot_changes(tmp_path: Path) -> None:
    root = _skills(tmp_path / "skills")
    before = SkillAdapter(root).skill_bundle_hash()
    (root / "bridge-box" / "references" / "guide.md").write_text("changed", encoding="utf-8")
    assert SkillAdapter(root).skill_bundle_hash() != before
