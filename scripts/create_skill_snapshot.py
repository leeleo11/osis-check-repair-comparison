"""Copy the parent skill tree that T6's OpenCode already uses.

T1-T5 read this copy. Nothing inside ``.agents/skills`` is removed, so the
files match the parent agent. Dataset gold stays outside this tree.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.paths import resolve_parent_repo


def create_snapshot(source: Path, destination: Path) -> int:
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=False)
    return sum(1 for path in destination.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    parser.add_argument("--output", default="tmp/check-repair-skill-snapshot")
    args = parser.parse_args()
    parent = resolve_parent_repo(args.parent_repo)
    source = parent / ".agents" / "skills"
    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parents[1] / output
    copied = create_snapshot(source, output)
    print(f"snapshot contains {copied} files at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
