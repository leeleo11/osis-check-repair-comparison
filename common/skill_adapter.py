"""Bounded, read-only access to a frozen AgentSkills directory."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class SkillPathError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SkillMeta:
    skill_id: str
    name: str
    description: str


class SkillAdapter:
    def __init__(self, skills_dir: str | Path, *, max_read_bytes: int = 200_000) -> None:
        self.root = Path(skills_dir).resolve()
        if not self.root.is_dir():
            raise NotADirectoryError(self.root)
        self.max_read_bytes = max_read_bytes

    def _inside(self, candidate: Path) -> Path:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SkillPathError(f"path escapes skills root: {candidate}") from exc
        return resolved

    def _skill_dir(self, skill_id: str) -> Path:
        if not skill_id or Path(skill_id).name != skill_id:
            raise SkillPathError(f"invalid skill id: {skill_id!r}")
        directory = self._inside(self.root / skill_id)
        if directory.parent != self.root or not directory.is_dir():
            raise SkillPathError(f"unknown skill: {skill_id}")
        return directory

    @staticmethod
    def _frontmatter(text: str) -> dict[str, str]:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}
        result: dict[str, str] = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, separator, value = line.partition(":")
            if separator:
                result[key.strip()] = value.strip().strip("\"'")
        return result

    def _read(self, path: Path) -> str:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size > self.max_read_bytes:
            raise SkillPathError(f"skill file exceeds {self.max_read_bytes} bytes")
        return path.read_text(encoding="utf-8", errors="replace")

    def list_skills(self) -> list[SkillMeta]:
        result: list[SkillMeta] = []
        for directory in sorted(self.root.iterdir(), key=lambda path: path.name.casefold()):
            skill_file = directory / "SKILL.md"
            if not directory.is_dir() or not skill_file.is_file():
                continue
            values = self._frontmatter(self._read(skill_file))
            result.append(
                SkillMeta(
                    skill_id=directory.name,
                    name=values.get("name", directory.name),
                    description=values.get("description", ""),
                )
            )
        return result

    def skill_index(self) -> list[dict[str, str]]:
        return [
            {"skill_id": skill.skill_id, "name": skill.name, "description": skill.description}
            for skill in self.list_skills()
        ]

    def read_skill(self, skill_id: str) -> str:
        return self._read(self._inside(self._skill_dir(skill_id) / "SKILL.md"))

    def read_reference(self, skill_id: str, relative_path: str) -> str:
        raw = Path(relative_path)
        if not relative_path or raw.is_absolute() or ".." in raw.parts:
            raise SkillPathError("reference path must be a safe relative path")
        return self._read(self._inside(self._skill_dir(skill_id) / raw))

    def skill_bundle_hash(self) -> str:
        digest = hashlib.sha256()
        files = sorted(
            (path for path in self.root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(self.root).as_posix(),
        )
        for path in files:
            relative = path.relative_to(self.root).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def fixed_bundle_text(self) -> str:
        """Return every SKILL.md body in deterministic order for T1."""
        sections = [f"# Skill snapshot sha256={self.skill_bundle_hash()}"]
        for skill in self.list_skills():
            sections.extend((f"\n## {skill.skill_id}", self.read_skill(skill.skill_id)))
        return "\n".join(sections)
