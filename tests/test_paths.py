from __future__ import annotations

from pathlib import Path

import pytest

import common.paths as paths


def _parent_repo(path: Path) -> Path:
    (path / ".agents" / "skills").mkdir(parents=True)
    (path / "datasets" / "check_repair").mkdir(parents=True)
    (path / "datasets" / "check_repair" / "samples.json").write_text("[]", encoding="utf-8")
    return path


def test_parent_resolution_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = _parent_repo(tmp_path / "explicit")
    ambient = _parent_repo(tmp_path / "ambient")
    monkeypatch.setenv(paths.ENV_VAR, str(ambient))
    assert paths.resolve_parent_repo(explicit) == explicit.resolve()
    assert paths.resolve_parent_repo() == ambient.resolve()


def test_local_config_is_portable_and_comments_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    framework = tmp_path / "framework"
    configured = _parent_repo(tmp_path / "parent")
    (framework / "configs").mkdir(parents=True)
    (framework / "configs" / "parent_repo.local.txt").write_text(
        f"# local only\n{configured}\n", encoding="utf-8"
    )
    monkeypatch.setattr(paths, "FRAMEWORK_ROOT", framework)
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    assert paths.resolve_parent_repo() == configured.resolve()


def test_invalid_explicit_parent_fails_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambient = _parent_repo(tmp_path / "ambient")
    monkeypatch.setenv(paths.ENV_VAR, str(ambient))
    with pytest.raises(paths.ParentRepoNotFound, match="markers"):
        paths.resolve_parent_repo(tmp_path / "wrong")
