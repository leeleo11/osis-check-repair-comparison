"""Export a clean reproduction workspace from Git-tracked source only."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _tracked_relative(source: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files"], cwd=source, text=True, encoding="utf-8"
    )
    return [Path(line) for line in output.splitlines() if line]


def export_repro_workspace(
    source: str | Path,
    destination: str | Path,
    parent_repo: str | Path,
) -> list[str]:
    source_root = Path(source).resolve()
    target_root = Path(destination).resolve()
    if target_root == source_root or source_root in target_root.parents:
        raise ValueError("destination must be outside the source repository")
    if target_root.exists() and any(target_root.iterdir()):
        raise FileExistsError("destination must be empty")
    target_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for relative in _tracked_relative(source_root):
        source_path = source_root / relative
        if not source_path.is_file():
            continue
        target_path = target_root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(relative.as_posix())
    config = target_root / "configs" / "parent_repo.local.txt"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(str(Path(parent_repo).resolve()) + "\n", encoding="utf-8")
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    parser.add_argument("--source", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--parent-repo", required=True)
    args = parser.parse_args()
    copied = export_repro_workspace(args.source, args.destination, args.parent_repo)
    print(f"exported {len(copied)} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
