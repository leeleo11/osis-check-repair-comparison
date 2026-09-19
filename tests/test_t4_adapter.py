from __future__ import annotations

from pathlib import Path

from baselines.t4_openhands.adapter import load_native_skills, run_generation


def test_native_skill_loader_flattens_all_openhands_groups(tmp_path: Path) -> None:
    groups = ({"repo": "a"}, {"knowledge": "b"}, {"agent": "c"})
    assert load_native_skills(tmp_path, loader=lambda _: groups) == ["a", "b", "c"]


def test_t4_prompt_relies_on_native_skills_and_records_events(adapter_request: dict[str, object]) -> None:
    captured: dict[str, object] = {}

    def fake_runtime(request, prompt, tools, native_skills):
        captured["prompt"] = prompt
        captured["native_skills"] = native_skills
        tools.write_candidate_file("py/main.py", "VALUE = 44\n")
        return {
            "final_answer": "fixed",
            "execution_status": "FINISHED",
            "model_calls": 2,
            "tool_calls": 2,
            "framework_steps": 5,
            "events": [{"kind": "skill", "name": "osis-check-repair"}],
        }

    result = run_generation(
        adapter_request,
        runtime=fake_runtime,
        skill_loader=lambda _: ({}, {}, {"native": object()}),
    )
    prompt = str(captured["prompt"])
    assert "Read before edit" not in prompt
    assert "InvokeSkillTool" in prompt
    assert len(captured["native_skills"]) == 1
    assert result["skill_loading"] == "openhands_native_progressive"
    assert result["native_skill_count"] == 1
    assert result["events"][0]["kind"] == "skill"
