from __future__ import annotations

from pathlib import Path

from check_repair.verifier import NativeCheckVerifier


def _native_project(tmp_path: Path) -> Path:
    project = tmp_path / "candidate"
    check = project / "Check"
    check.mkdir(parents=True)
    (check / "01_target_case.lcc").write_text("native", encoding="utf-8")
    return project


def _fake_native_run(project: Path, calls: list[str]):
    def run(command: str, timeout: float = 60) -> tuple[bool, str]:
        calls.append(command)
        if command.startswith("/output,"):
            out = project / "Temperary" / "01_target_case.txt"
            out.parent.mkdir(exist_ok=True)
            out.write_text("单元\t结果\n1\tOK\n", encoding="gbk")
        elif command in {"CheckSolve", "CombinationAndCheck"}:
            check = project / "Check"
            check.mkdir(exist_ok=True)
            (check / "01_target_case.lcc").write_text("fresh", encoding="utf-8")
        return True, ""

    return run


def test_verifier_prefers_osispost_and_never_runs_combination(tmp_path: Path) -> None:
    project = _native_project(tmp_path)
    post = project / "OSISPost.out"
    post.write_text("native post", encoding="utf-8")
    calls: list[str] = []
    result = NativeCheckVerifier(_fake_native_run(project, calls)).verify(project, post_out=post)
    joined = "\n".join(calls)
    assert "/input," in joined
    assert "CheckSolve" in calls
    assert "CombinationAndCheck" not in calls
    assert result.ng_items == ()
    assert result.complete is True


def test_verifier_falls_back_to_combination_when_post_is_missing(tmp_path: Path) -> None:
    project = _native_project(tmp_path)
    calls: list[str] = []
    verifier = NativeCheckVerifier(_fake_native_run(project, calls))
    verifier.verify(project, post_out=project / "missing.out")
    assert "checkdel,all" in calls
    assert "CombinationAndCheck" in calls
    assert "CheckSolve" not in calls


def test_native_command_failure_is_fatal(tmp_path: Path) -> None:
    project = _native_project(tmp_path)

    def fail(command: str, timeout: float = 60) -> tuple[bool, str]:
        return False, "engine error"

    try:
        NativeCheckVerifier(fail).verify(project)
    except RuntimeError as exc:
        assert "engine error" in str(exc)
    else:
        raise AssertionError("native command failure was accepted")
