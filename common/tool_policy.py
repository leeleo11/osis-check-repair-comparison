"""Filesystem policy for framework-controlled candidate edits."""

from __future__ import annotations

import ast
from pathlib import Path


class PathPolicyError(ValueError):
    pass


ALLOWED_SUFFIXES = frozenset({".py", ".md", ".json", ".yaml", ".yml", ".txt"})


class CandidateWorkspace:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str, *, for_write: bool = False) -> Path:
        raw = Path(str(relative_path))
        if raw.is_absolute() or ".." in raw.parts or not raw.parts:
            raise PathPolicyError("candidate path must be relative and cannot contain '..'")
        resolved = (self.root / raw).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise PathPolicyError("path escapes candidate workspace") from exc
        if for_write and resolved.suffix.lower() not in ALLOWED_SUFFIXES:
            raise PathPolicyError(f"file type is not writable: {resolved.suffix}")
        return resolved

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8", errors="replace")

    def write_text(self, relative_path: str, content: str) -> Path:
        target = self.resolve(relative_path, for_write=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        return target

    def list_files(self) -> list[str]:
        return sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_file())

    def compile_python(self) -> dict[str, str]:
        failures: dict[str, str] = {}
        for path in sorted(self.root.rglob("*.py")):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            except (SyntaxError, UnicodeError) as exc:
                failures[path.relative_to(self.root).as_posix()] = str(exc)
        return failures
