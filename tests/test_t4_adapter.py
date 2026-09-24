from __future__ import annotations

from pathlib import Path

from baselines.t4_openhands.adapter import build_t4_prompt, load_native_skills, run_generation


def test_native_skill_loader_flattens_all_openhands_groups(tmp_path: Path) -> None:
    groups = ({"repo": "a"}, {"knowledge": "b"}, {"agent": "c"})
    assert load_native_skills(tmp_path, loader=lambda _: groups) == ["a", "b", "c"]


def test_t4_prompt_uses_native_terminal_and_editor(adapter_request: dict[str, object]) -> None:
    prompt = build_t4_prompt(adapter_request)
    assert "InvokeSkillTool" in prompt
    assert "file editor" in prompt
    assert "terminal" in prompt


def test_t4_prompt_relies_on_native_skills_and_records_events(adapter_request: dict[str, object]) -> None:
    captured: dict[str, object] = {}

    def fake_runtime(request, prompt, native_skills):
        captured["prompt"] = prompt
        captured["native_skills"] = native_skills
        candidate = Path(str(request["workspace"])) / "candidate_project" / "py"
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate / "main.py").write_text("VALUE = 44\n", encoding="utf-8")
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
    assert "InvokeSkillTool" in prompt
    assert len(captured["native_skills"]) == 1
    assert result["skill_loading"] == "openhands_native_progressive"
    assert result["native_skill_count"] == 1
    assert result["events"][0]["kind"] == "skill"
    workspace = Path(str(adapter_request["workspace"]))
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 44\n"
