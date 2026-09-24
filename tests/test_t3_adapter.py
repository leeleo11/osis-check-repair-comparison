from __future__ import annotations

from pathlib import Path

from baselines.t3_smolagents.adapter import AUTHORIZED_IMPORTS, run_generation


def test_t3_uses_codeagent_contract(adapter_request: dict[str, object]) -> None:
    def fake_runtime(request, prompt):
        assert "import pathlib" in prompt
        assert str(request["skills_dir"]) in prompt
        candidate = Path(str(request["workspace"])) / "candidate_project" / "py"
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate / "main.py").write_text("VALUE = 33\n", encoding="utf-8")
        return {"final_answer": "fixed", "model_calls": 3, "tool_calls": 2, "agent_state": "success"}

    result = run_generation(adapter_request, runtime=fake_runtime)
    workspace = Path(str(adapter_request["workspace"]))
    assert result["framework"] == "smolagents"
    assert result["interaction_mode"] == "codeact"
    assert result["authorized_imports"] == ["json", "pathlib"]
    assert AUTHORIZED_IMPORTS == ["json", "pathlib"]
    assert result["agent_state"] == "success"
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 33\n"
