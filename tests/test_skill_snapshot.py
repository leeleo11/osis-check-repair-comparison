from pathlib import Path

from scripts.create_skill_snapshot import create_snapshot


def test_snapshot_drops_template_directories(tmp_path: Path) -> None:
    source = tmp_path / "skills" / "osis-bridge"
    template = source / "references" / "templates" / "bridge-a" / "prep"
    template.mkdir(parents=True)
    (source / "SKILL.md").write_text("skill", encoding="utf-8")
    (source / "references" / "guide.md").write_text("guide", encoding="utf-8")
    (template / "main.py").write_text("answer", encoding="utf-8")
    output = tmp_path / "snapshot"

    copied = create_snapshot(source.parent, output)

    assert (output / "osis-bridge" / "SKILL.md").is_file()
    assert (output / "osis-bridge" / "references" / "guide.md").is_file()
    assert not (output / "osis-bridge" / "references" / "templates").exists()
    assert copied == 2
