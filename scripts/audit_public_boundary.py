"""Fail-closed release audit for tracked public files."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PRIVATE_PARTS = frozenset(
    {"runs", "reports", "private", "seeded", "candidate_project", "data", "datasets", "model_responses"}
)
NATIVE_DIRS = frozenset({"check", "temperary", "result", "error", "model", "muticase", "break", "secmesh"})
NATIVE_SUFFIXES = frozenset({".lcc", ".db", ".sqlite", ".sqlite3", ".log"})
HIDDEN_JSON_KEYS = frozenset(
    {"seed", "reason_code", "ng_baseline", "ng_seeded", "seeded_path", "template_path", "how"}
)
MACHINE_PATH = re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|home|实习)[\\/]|/(?:home|Users)/[^/\s]+/)")
CREDENTIAL = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{20,}|(?:api[_-]?key|token)\s*[:=]\s*[\"']?[A-Za-z0-9_-]{24,})")


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    rule: str
    detail: str


def tracked_paths(root: str | Path) -> list[Path]:
    base = Path(root).resolve()
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=base,
        text=True,
        encoding="utf-8",
    )
    return [base / line for line in output.splitlines() if line]


def _json_hidden_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(HIDDEN_JSON_KEYS & {str(key) for key in value})
        for child in value.values():
            found.update(_json_hidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_json_hidden_keys(child))
    return found


def audit_paths(root: str | Path, paths: Iterable[Path]) -> list[Violation]:
    base = Path(root).resolve()
    violations: list[Violation] = []
    for path in paths:
        path = Path(path)
        try:
            relative = path.resolve().relative_to(base)
        except ValueError:
            violations.append(Violation(str(path), "path-escape", "file is outside repository"))
            continue
        parts = {part.casefold() for part in relative.parts}
        rel = relative.as_posix()
        if rel.casefold() == "configs/parent_repo.local.txt":
            violations.append(Violation(rel, "private-path", "local parent configuration is tracked"))
        if parts & PRIVATE_PARTS:
            violations.append(Violation(rel, "private-path", "experiment input/output path is tracked"))
        if parts & NATIVE_DIRS or path.suffix.casefold() in NATIVE_SUFFIXES or path.name.casefold() == "osispost.out":
            violations.append(Violation(rel, "native-output", "native OSIS output is tracked"))
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        content_exempt = relative.parts and relative.parts[0].casefold() in {"tests", "docs"}
        example_exempt = rel == "configs/parent_repo.example.txt"
        if not content_exempt and not example_exempt and MACHINE_PATH.search(text):
            violations.append(Violation(rel, "machine-path", "machine-specific absolute path"))
        if not content_exempt and CREDENTIAL.search(text):
            violations.append(Violation(rel, "credential", "credential-like literal"))
        if path.suffix.casefold() == ".json" and not content_exempt:
            try:
                hidden = _json_hidden_keys(json.loads(text))
            except json.JSONDecodeError:
                hidden = set()
            if hidden:
                violations.append(Violation(rel, "hidden-json", f"hidden keys: {sorted(hidden)}"))
    return sorted(violations, key=lambda item: (item.path, item.rule))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = Path(args.root).resolve()
    violations = audit_paths(root, tracked_paths(root))
    for violation in violations:
        print(f"{violation.path}: {violation.rule}: {violation.detail}")
    if violations:
        print(f"public boundary audit failed: {len(violations)} violation(s)")
        return 1
    print("public boundary audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
