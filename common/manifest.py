"""Deterministic artifact hashing without machine-specific paths."""

from __future__ import annotations

import hashlib
from pathlib import Path


_PRIVATE_DIRS = frozenset({"private", "seeded", "candidate_project"})


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_hashes(run_dir: str | Path) -> dict[str, str]:
    root = Path(run_dir).resolve()
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part.lower() in _PRIVATE_DIRS for part in relative.parts):
            continue
        result[relative.as_posix()] = sha256_file(path)
    return result
