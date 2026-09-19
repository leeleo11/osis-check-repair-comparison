"""Create the isolated Python environments used by T1-T5."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ENVIRONMENTS = {
    "main": (".venv", "test,t2"),
    "t3": (".venvs/t3", "t3"),
    "t4": (".venvs/t4", "t4"),
    "t5": (".venvs/t5", "t5"),
}


def commands(root: Path, python: str = "3.13") -> list[list[str]]:
    result: list[list[str]] = []
    for _, (directory, extra) in ENVIRONMENTS.items():
        environment = root / directory
        executable = environment / ("Scripts/python.exe" if __import__("os").name == "nt" else "bin/python")
        result.append(["uv", "venv", "--python", python, str(environment)])
        result.append(["uv", "pip", "install", "--python", str(executable), "-e", f".[{extra}]"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="3.13")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for command in commands(root, args.python):
        print(" ".join(command))
        if not args.dry_run:
            subprocess.run(command, cwd=root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
