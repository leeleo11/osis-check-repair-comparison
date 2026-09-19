from __future__ import annotations

from pathlib import Path

import pytest

from check_repair.ng import CheckRow, clear_check_results, item_names, parse_check_rows, require_complete


def test_clear_check_results_removes_only_stale_native_outputs(tmp_path: Path) -> None:
    check = tmp_path / "Check"
    temporary = tmp_path / "Temperary"
    check.mkdir()
    temporary.mkdir()
    stale_lcc = check / "01_target_case.lcc"
    keep = check / "notes.txt"
    stale_txt = temporary / "01_target_case.txt"
    stale_lcc.write_text("stale", encoding="utf-8")
    keep.write_text("keep", encoding="utf-8")
    stale_txt.write_text("stale", encoding="utf-8")

    clear_check_results(tmp_path)

    assert not stale_lcc.exists()
    assert not stale_txt.exists()
    assert keep.exists()


def test_parse_check_rows_uses_gbk_tabular_export(tmp_path: Path) -> None:
    check = tmp_path / "Check"
    check.mkdir()
    (check / "01_target_case.lcc").write_text("native", encoding="utf-8")

    calls: list[str] = []

    def fake_run(command: str, timeout: float = 60) -> tuple[bool, str]:
        calls.append(command)
        output = tmp_path / "Temperary" / "01_target_case.txt"
        output.parent.mkdir(exist_ok=True)
        output.write_text("说明\n单元\t结果\n1\tOK\n2\tNG\n", encoding="gbk")
        return True, ""

    rows = parse_check_rows(tmp_path, fake_run)

    assert rows == [CheckRow("01_target_case", "NG", 1, 1)]
    assert calls and calls[0].startswith("/output,")
    assert item_names(rows) == ["target"]


@pytest.mark.parametrize("mode", ["missing", "no-header"])
def test_parse_marks_incomplete_exports(tmp_path: Path, mode: str) -> None:
    check = tmp_path / "Check"
    check.mkdir()
    (check / "01_target_case.lcc").write_text("native", encoding="utf-8")

    def fake_run(command: str, timeout: float = 60) -> tuple[bool, str]:
        if mode == "no-header":
            output = tmp_path / "Temperary" / "01_target_case.txt"
            output.parent.mkdir(exist_ok=True)
            output.write_text("unrelated", encoding="gbk")
        return True, ""

    rows = parse_check_rows(tmp_path, fake_run)
    expected = "NOFILE" if mode == "missing" else "NOHEADER"
    assert rows[0].status == expected
    with pytest.raises(RuntimeError, match=expected):
        require_complete(rows)


def test_require_complete_rejects_empty_results() -> None:
    with pytest.raises(RuntimeError, match="no check results"):
        require_complete([])
