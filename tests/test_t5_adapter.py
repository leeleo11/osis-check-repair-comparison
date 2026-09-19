from __future__ import annotations

from pathlib import Path

from baselines.t5_crewai.adapter import ROLE_ORDER, build_role_tools, run_generation


def test_t5_role_boundaries_make_verifier_read_only(adapter_request: dict[str, object]) -> None:
    tools = build_role_tools(adapter_request)
    assert ROLE_ORDER == ("diagnoser", "repairer", "verifier")
    assert tools["diagnoser"].allow_write is False
    assert tools["repairer"].allow_write is True
    assert tools["verifier"].allow_write is False
    assert tools["verifier"].write_candidate_file("py/main.py", "BAD") == "TOOL_ERROR: this role is read-only"


def test_t5_runs_diagnose_repair_verify_sequence(adapter_request: dict[str, object]) -> None:
    def fake_runtime(request, prompt, role_tools):
        role_tools["repairer"].write_candidate_file("py/main.py", "VALUE = 55\n")
        return {
            "final_answer": "verified",
            "role_outputs": {role: role for role in ROLE_ORDER},
            "model_calls": 3,
            "tool_calls": 2,
        }

    result = run_generation(adapter_request, runtime=fake_runtime)
    workspace = Path(str(adapter_request["workspace"]))
    assert result["framework"] == "crewai"
    assert result["roles"] == list(ROLE_ORDER)
    assert result["verifier_write_access"] is False
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 55\n"
