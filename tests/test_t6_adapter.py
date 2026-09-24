from __future__ import annotations

from pathlib import Path

from baselines.t6_osisai.adapter import run_generation


def test_t6_syncs_the_parent_project_into_the_candidate(
    adapter_request: dict[str, object], tmp_path: Path
) -> None:
    project_py = tmp_path / "osis_py"
    project_py.mkdir()
    (project_py / "main.py").write_text("VALUE = 66\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def chat(request: dict[str, object]) -> dict[str, object]:
        captured["task_id"] = request["task"]["task_id"]  # type: ignore[index]
        captured["model"] = request["model"]
        return {"raw": "fixed", "project_py": str(project_py)}

    result = run_generation(adapter_request, chat=chat)
    workspace = Path(str(adapter_request["workspace"]))
    assert captured["task_id"] == "smoke-adapter"
    assert captured["model"] == "test-model"
    assert result["interaction_mode"] == "parent_session"
    assert result["final_answer"] == "fixed"
    assert (workspace / "candidate_project" / "py" / "main.py").read_text(encoding="utf-8") == "VALUE = 66\n"
    assert not (workspace / "t6_isolated_project").exists()


def test_t6_fails_without_the_parent_runner(adapter_request: dict[str, object]) -> None:
    result = run_generation(adapter_request)
    assert result["status"] == "failed"
    assert result["error_type"] in {"FileNotFoundError", "ImportError", "TypeError"}
