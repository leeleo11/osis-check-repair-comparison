"""Fail-closed parsing of native OSIS check exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


NativeCommand = Callable[[str, float], object]


@dataclass(frozen=True, slots=True)
class CheckRow:
    name: str
    status: str
    ok_count: int
    ng_count: int


def clear_check_results(project_root: str | Path) -> None:
    root = Path(project_root)
    for path in (root / "Check").glob("*.lcc"):
        path.unlink(missing_ok=True)
    for path in (root / "Temperary").glob("*.txt"):
        path.unlink(missing_ok=True)


def _run(run_command: NativeCommand, command: str, timeout: float) -> None:
    try:
        result = run_command(command, timeout)
    except TypeError:
        result = run_command(command, timeout=timeout)  # type: ignore[call-arg]
    if isinstance(result, tuple):
        ok = bool(result[0])
        detail = str(result[1]) if len(result) > 1 else ""
    elif isinstance(result, bool):
        ok, detail = result, ""
    else:
        ok, detail = True, ""
    if not ok:
        raise RuntimeError(f"native command failed: {command}: {detail}")


def _read_export(path: Path, name: str) -> CheckRow:
    if not path.is_file():
        return CheckRow(name, "NOFILE", 0, 0)
    lines = path.read_text(encoding="gbk", errors="replace").splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "结果" in line and any(token in line for token in ("单元", "验算", "位置", "安全"))
        ),
        None,
    )
    if header_index is None:
        return CheckRow(name, "NOHEADER", 0, 0)

    reader = csv.DictReader(lines[header_index:], delimiter="\t")
    if reader.fieldnames is None:
        return CheckRow(name, "NOHEADER", 0, 0)
    normalized = {str(field).strip(): field for field in reader.fieldnames}
    result_field = normalized.get("结果")
    if result_field is None:
        return CheckRow(name, "NOHEADER", 0, 0)
    ok_count = 0
    ng_count = 0
    for row in reader:
        value = str(row.get(result_field) or "").strip().upper()
        if "NG" in value:
            ng_count += 1
        elif "OK" in value:
            ok_count += 1
    status = "NG" if ng_count else "OK"
    return CheckRow(name, status, ok_count, ng_count)


def parse_check_rows(
    project_root: str | Path,
    run_command: NativeCommand,
) -> list[CheckRow]:
    root = Path(project_root).resolve()
    check_dir = root / "Check"
    temporary = root / "Temperary"
    temporary.mkdir(parents=True, exist_ok=True)
    rows: list[CheckRow] = []
    for lcc in sorted(check_dir.glob("*.lcc")):
        name = lcc.stem
        output = temporary / f"{name}.txt"
        _run(run_command, f"/output,{output},echk,{name}", 60)
        rows.append(_read_export(output, name))
    return rows


def require_complete(rows: Iterable[CheckRow]) -> None:
    collected = list(rows)
    if not collected:
        raise RuntimeError("no check results were produced")
    incomplete = [row for row in collected if row.status not in {"OK", "NG"}]
    if incomplete:
        detail = ", ".join(f"{row.name}={row.status}" for row in incomplete)
        raise RuntimeError(f"incomplete check results: {detail}")


def item_names(rows: Iterable[CheckRow], status: str = "NG") -> list[str]:
    names: list[str] = []
    for row in rows:
        if row.status != status:
            continue
        parts = row.name.split("_", 2)
        names.append(parts[1] if len(parts) >= 2 else row.name)
    return names
