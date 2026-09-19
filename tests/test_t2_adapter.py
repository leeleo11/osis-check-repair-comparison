from __future__ import annotations

from pathlib import Path

from baselines.t2_langgraph.adapter import run_generation


def test_t2_uses_langgraph_runtime_and_captures_trace(adapter_request: dict[str, object]) -> None:
    def fake_runtime(request, prompt, tools):
        assert "Repair the named failed" in prompt
        tools.write_candidate_file("py/main.py", "VALUE = 22\n")
        return {
            "final_answer": "done",
            "model_calls": 2,
            "tool_calls": 1,
            "trace": [{"kind": "tool", "name": "write_candidate_file"}],
        }

    result = run_generation(adapter_request, runtime=fake_runtime)
    workspace = Path(str(adapter_request["workspace"]))
    assert result["framework"] == "langgraph"
    assert result["interaction_mode"] == "react"
    assert result["tool_calls"] == 1
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 22\n"
    assert (workspace / "t2_generation.json").is_file()
