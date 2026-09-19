"""Trusted native verifier shared by all six framework adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .ng import CheckRow, NativeCommand, _run, clear_check_results, item_names, parse_check_rows, require_complete


@dataclass(frozen=True, slots=True)
class VerificationResult:
    rows: tuple[CheckRow, ...]
    ng_items: tuple[str, ...]
    check_mode: str
    complete: bool = True


def _native_command() -> NativeCommand:
    try:
        from pyosis.core.command import osis_run
    except ImportError as exc:  # pragma: no cover - exercised only in native env
        raise RuntimeError("pyosis is required for native verification") from exc
    return osis_run


def _native_solve() -> None:
    try:
        from pyosis import OSISEngine
    except ImportError as exc:  # pragma: no cover - exercised only in native env
        raise RuntimeError("pyosis is required to rebuild a candidate") from exc
    OSISEngine().solve(timeout=900)


class NativeCheckVerifier:
    def __init__(
        self,
        run_command: NativeCommand | None = None,
        solve_command: Callable[[], None] | None = None,
    ) -> None:
        self._run_command = run_command
        self._solve_command = solve_command

    def verify(
        self,
        project_root: str | Path,
        post_out: str | Path | None = None,
        rebuild: bool = False,
    ) -> VerificationResult:
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"candidate project does not exist: {root}")
        command = self._run_command or _native_command()

        if rebuild:
            (self._solve_command or _native_solve)()

        clear_check_results(root)
        post = Path(post_out).resolve() if post_out is not None else None
        if post is not None and post.is_file():
            _run(command, f"/input,{post}", 900)
            _run(command, "CdEleSel,All", 60)
            _run(command, "CheckSolve", 900)
            mode = "osispost-checksolve"
        else:
            _run(command, "checkdel,all", 60)
            _run(command, "CombinationAndCheck", 900)
            mode = "combination-and-check"

        rows = tuple(parse_check_rows(root, command))
        require_complete(rows)
        return VerificationResult(
            rows=rows,
            ng_items=tuple(item_names(rows)),
            check_mode=mode,
        )
