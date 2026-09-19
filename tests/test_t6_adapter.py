from __future__ import annotations

from pathlib import Path

from baselines.t6_osisai.adapter import run_generation


def test_t6_uses_isolated_native_project_and_syncs_candidate(adapter_request: dict[str, object]) -> None:
    captured: dict[str, object] = {}

    def fake_runtime(request, project, prompt):
        captured["project"] = project
        captured["prompt"] = prompt
        (project / "py" / "main.py").write_text("VALUE = 66\n", encoding="utf-8")
        return {"final_answer": "fixed", "model_calls": 2, "tool_calls": 3}

    result = run_generation(adapter_request, runtime=fake_runtime)
    workspace = Path(str(adapter_request["workspace"]))
    isolated = Path(captured["project"])
    assert isolated == workspace / "t6_isolated_project"
    assert (isolated / ".agents" / "skills").is_dir()
    assert str(workspace) not in str(captured["prompt"])
    assert result["framework"] == "osis-ai-native"
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 66\n"
