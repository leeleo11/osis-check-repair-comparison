"""Small shared helpers used inside T1-T5 framework processes."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import time
from pathlib import Path
from typing import Any

from common.skill_adapter import SkillAdapter
from common.tool_policy import CandidateWorkspace


def load_request(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    args = parser.parse_args(argv)
    return json.loads(Path(args.request).read_text(encoding="utf-8"))


def candidate_workspace(request: dict[str, Any]) -> CandidateWorkspace:
    return CandidateWorkspace(Path(request["workspace"]) / "candidate_project")


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


# Libraries install a small default loop bound when the argument is omitted.
# The experiment does not stop on steps. This value only disables that default.
LIBRARY_LOOP_BOUND = 1_000_000


def resolve_max_steps(value: object, *, default: int = 200) -> int:
    try:
        steps = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return steps if steps > 0 else 100_000


def resolve_max_tokens(value: object) -> int | None:
    try:
        tokens = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return tokens if tokens > 0 else None


def build_prompt(request: dict[str, Any]) -> str:
    task = request["task"]
    return (
        "Repair the named failed OSIS check in the staged candidate project.\n"
        "Use only the mounted public skills and candidate tools. Do not inspect parent datasets, "
        "hidden references, other runs, or evaluator files. Preserve unrelated behavior.\n"
        "At the end, report the final localization JSON and summarize edited files.\n\n"
        + json.dumps(task, ensure_ascii=False, indent=2)
    )


def skill_reader(request: dict[str, Any]) -> SkillAdapter:
    return SkillAdapter(Path(request["skills_dir"]))


def tool_error(exc: BaseException) -> str:
    return f"TOOL_ERROR: {type(exc).__name__}: {exc}"


class BoundedTools:
    """Same bounded capability set exposed through each framework API."""

    def __init__(self, request: dict[str, Any], *, allow_write: bool = True) -> None:
        self.skills = skill_reader(request)
        self.candidate = candidate_workspace(request)
        self.allow_write = allow_write

    def list_skills(self) -> str:
        """List mounted public skills as compact JSON."""
        return json.dumps(self.skills.skill_index(), ensure_ascii=False)

    def read_skill(self, skill_id: str) -> str:
        """Read one mounted SKILL.md.

        Args:
            skill_id: Exact mounted skill directory name.
        """
        try:
            return self.skills.read_skill(skill_id)
        except Exception as exc:  # noqa: BLE001
            return tool_error(exc)

    def read_skill_reference(self, skill_id: str, relative_path: str) -> str:
        """Read a bounded reference file from one mounted skill.

        Args:
            skill_id: Exact mounted skill directory name.
            relative_path: Relative path inside that skill directory.
        """
        try:
            return self.skills.read_reference(skill_id, relative_path)
        except Exception as exc:  # noqa: BLE001
            return tool_error(exc)

    def list_candidate_files(self) -> str:
        """List files in the staged candidate project as JSON."""
        return json.dumps(self.candidate.list_files(), ensure_ascii=False)

    def read_candidate_file(self, relative_path: str) -> str:
        """Read one UTF-8 candidate file.

        Args:
            relative_path: Path relative to the candidate project.
        """
        try:
            return self.candidate.read_text(relative_path)
        except Exception as exc:  # noqa: BLE001
            return tool_error(exc)

    def write_candidate_file(self, relative_path: str, content: str) -> str:
        """Write one text file inside the candidate project.

        Args:
            relative_path: Path relative to the candidate project.
            content: Complete replacement file content.
        """
        if not self.allow_write:
            return "TOOL_ERROR: this role is read-only"
        try:
            self.candidate.write_text(relative_path, content)
            return f"wrote {relative_path} ({len(content)} chars)"
        except Exception as exc:  # noqa: BLE001
            return tool_error(exc)

    def list_reference_files(self, skill_id: str, template_name: str = "") -> str:
        """List files under one skill, or under one template directory inside it."""
        try:
            skill_dir = self.skills._skill_dir(skill_id)
            target = skill_dir
            if template_name.strip():
                raw = Path(template_name)
                if raw.is_absolute() or ".." in raw.parts:
                    raise ValueError("template path must stay inside the skill")
                target = skill_dir / raw
            if not target.is_dir():
                raise FileNotFoundError(template_name or skill_id)
            files = sorted(
                path.relative_to(skill_dir).as_posix()
                for path in target.rglob("*")
                if path.is_file()
            )
            return json.dumps(files, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return tool_error(exc)

    def search_skill_cases(self, query: str) -> str:
        """Search mounted skill markdown for a case or API keyword."""
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return "[]"
        hits: list[dict[str, str]] = []
        root = self.skills.root
        for path in sorted(root.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lowered = text.casefold()
            if not any(term in lowered for term in terms):
                continue
            hits.append(
                {
                    "skill_id": path.relative_to(root).parts[0],
                    "path": path.relative_to(root).as_posix(),
                    "preview": text[:240],
                }
            )
            if len(hits) >= 20:
                break
        return json.dumps(hits, ensure_ascii=False)

    def functions(self, *, include_write: bool | None = None) -> list[Any]:
        """LangGraph has no domain tools. This is the same surface as the modeling line."""
        writable = self.allow_write if include_write is None else include_write
        functions: list[Any] = [
            self.list_skills,
            self.read_skill,
            self.read_skill_reference,
            self.list_reference_files,
            self.search_skill_cases,
            self.list_candidate_files,
            self.read_candidate_file,
        ]
        if writable:
            functions.append(self.write_candidate_file)
        return functions


def model_api_settings(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": request["model"],
        "base_url": request.get("base_url") or os.environ.get("OSIS_MODEL_BASE_URL", ""),
        "api_key": request.get("api_key") or os.environ.get("OSIS_MODEL_API_KEY", ""),
        "temperature": float(request.get("temperature", 0.0)),
        "timeout": float(request.get("request_timeout_s", 180.0)),
        "max_tokens": resolve_max_tokens(request.get("max_output_tokens", request.get("max_tokens"))),
    }


def finish(
    workspace: str | Path,
    architecture_id: str,
    metadata: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    result = dict(metadata)
    result.setdefault("architecture_id", architecture_id)
    result["elapsed_s"] = max(0.0, time.monotonic() - started)
    candidate = CandidateWorkspace(root / "candidate_project")
    result["files_written"] = candidate.list_files()
    path = root / f"{architecture_id.lower()}_generation.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
