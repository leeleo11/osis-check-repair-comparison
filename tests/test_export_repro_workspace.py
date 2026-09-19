from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.export_repro_workspace import export_repro_workspace


def test_export_copies_only_tracked_files_and_writes_local_parent_config(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    (source / ".gitignore").write_text("runs/\nconfigs/*.local.txt\n", encoding="utf-8")
    (source / "README.md").write_text("public", encoding="utf-8")
    (source / "runs").mkdir()
    (source / "runs" / "result.json").write_text("private", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "README.md"], cwd=source, check=True)
    destination = tmp_path / "export"
    parent = tmp_path / "external-parent"

    copied = export_repro_workspace(source, destination, parent)

    assert copied == [".gitignore", "README.md"]
    assert (destination / "README.md").read_text() == "public"
    assert not (destination / "runs").exists()
    config = destination / "configs" / "parent_repo.local.txt"
    assert config.read_text(encoding="utf-8").strip() == str(parent.resolve())
    assert not (destination / ".git").exists()
