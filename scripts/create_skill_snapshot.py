"""Build an ignored, no-template skill snapshot shared by T1-T6."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.paths import resolve_parent_repo


EXCLUDED_PARTS = frozenset({"templates", "test", "tests", "answer", "answers", "expected", "ground_truth"})


def create_snapshot(source: Path, destination: Path) -> int:
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    copied = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part.casefold() in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            continue
        target = destination / relative
        if path.is_dir():
            target.mkdir(exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return copied


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
