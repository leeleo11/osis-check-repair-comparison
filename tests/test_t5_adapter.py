from __future__ import annotations

from pathlib import Path

from baselines.t5_crewai.adapter import AGENT_POLICY, ROLE_CAN_WRITE, ROLE_ORDER, run_generation


def test_t5_matches_modeling_crew_policy() -> None:
    assert ROLE_ORDER == ("diagnoser", "repairer", "verifier")
    assert AGENT_POLICY["allow_delegation"] is True
    assert AGENT_POLICY["allow_code_execution"] is False
    assert ROLE_CAN_WRITE == {"diagnoser": False, "repairer": True, "verifier": False}


def test_t5_runs_diagnose_repair_verify_sequence(adapter_request: dict[str, object]) -> None:
    def fake_runtime(request, prompt):
        assert "Repair the named failed" in prompt
        candidate = Path(str(request["workspace"])) / "candidate_project" / "py"
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate / "main.py").write_text("VALUE = 55\n", encoding="utf-8")
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
    assert result["allow_delegation"] is True
    assert result["verifier_write_access"] is False
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 55\n"
