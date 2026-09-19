"""Portable path discovery for the external OSIS parent repository."""

from __future__ import annotations

import os
from pathlib import Path


FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
ENV_VAR = "OSIS_PARENT_REPO"
LOCAL_CONFIG_FILENAME = "parent_repo.local.txt"
CONFIG_FILENAME = "parent_repo.txt"
RUN_ROOT_ENV = "OSIS_CHECK_REPAIR_RUN_ROOT"

_REQUIRED_MARKERS = (
    Path(".agents/skills"),
    Path("datasets/check_repair/samples.json"),
)


class ParentRepoNotFound(RuntimeError):
    pass


def _looks_like_parent(path: Path) -> bool:
    try:
        return path.is_dir() and all((path / marker).exists() for marker in _REQUIRED_MARKERS)
    except OSError:
        return False


def _from_local_config() -> Path | None:
    for name in (LOCAL_CONFIG_FILENAME, CONFIG_FILENAME):
        path = FRAMEWORK_ROOT / "configs" / name
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            candidate = Path(os.path.expandvars(value)).expanduser()
            if not candidate.is_absolute():
                candidate = FRAMEWORK_ROOT / candidate
            return candidate.resolve()
    return None


def resolve_parent_repo(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve a marker-validated parent path using explicit/env/config order."""
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        if not _looks_like_parent(candidate):
            raise ParentRepoNotFound(f"explicit parent lacks required markers: {candidate}")
        return candidate

    raw_env = os.environ.get(ENV_VAR)
    if raw_env:
        candidate = Path(os.path.expandvars(raw_env)).expanduser().resolve()
        if _looks_like_parent(candidate):
            return candidate

    configured = _from_local_config()
    if configured is not None and _looks_like_parent(configured):
        return configured

    sibling = FRAMEWORK_ROOT.parent / "osis-skill-enhance-main"
    if _looks_like_parent(sibling):
        return sibling.resolve()
    raise ParentRepoNotFound(
        f"cannot locate parent repo; use --parent-repo, {ENV_VAR}, or configs/{LOCAL_CONFIG_FILENAME}"
    )


def resolve_run_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    raw = explicit if explicit is not None else os.environ.get(RUN_ROOT_ENV)
    path = Path(raw).expanduser() if raw is not None else FRAMEWORK_ROOT / "runs"
    if not path.is_absolute():
        path = FRAMEWORK_ROOT / path
    return path.resolve()


def resolve_skills_dir(parent_repo: str | os.PathLike[str]) -> Path:
    root = Path(parent_repo).resolve()
    skills = (root / ".agents" / "skills").resolve()
    try:
        skills.relative_to(root)
    except ValueError as exc:
        raise ParentRepoNotFound("skills directory escapes parent repo") from exc
    if not skills.is_dir():
        raise ParentRepoNotFound(f"skills directory is missing: {skills}")
    return skills
