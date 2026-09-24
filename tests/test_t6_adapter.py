from __future__ import annotations

from pathlib import Path

from baselines.t6_osisai.adapter import run_generation


def test_t6_mounts_the_filtered_snapshot_not_parent_templates(
    adapter_request: dict[str, object],
) -> None:
    skills = Path(str(adapter_request["skills_dir"]))
    hidden = skills / "osis-check-repair" / "references" / "templates" / "answer"
    hidden.mkdir(parents=True)
    (hidden / "main.py").write_text("CORRECT = 1\n", encoding="utf-8")
    agents = Path(str(adapter_request["workspace"])) / "native-agents.md"
    agents.write_text("native framework\n", encoding="utf-8")
    adapter_request["osis_agents_file"] = str(agents)

    def runtime(request, project: Path):
        mounted = project / ".agents" / "skills"
        assert not any(path.name.casefold() == "templates" for path in mounted.rglob("*"))
        assert (mounted / "osis-check-repair" / "SKILL.md").is_file()
        assert "parent_repo" not in (project / "task.json").read_text(encoding="utf-8")
        candidate = project / "candidate_project" / "py"
        (candidate / "main.py").write_text("VALUE = 66\n", encoding="utf-8")
        return {"raw": "fixed", "model_calls": 1}

    result = run_generation(adapter_request, runtime=runtime)
    workspace = Path(str(adapter_request["workspace"]))
    assert result["skill_loading"] == "template_free_snapshot"
    assert result["final_answer"] == "fixed"
    assert (workspace / "candidate_project" / "py" / "main.py").read_text(encoding="utf-8") == "VALUE = 66\n"


def test_t6_refuses_a_tree_that_still_contains_templates(adapter_request: dict[str, object]) -> None:
    from baselines.t6_osisai.adapter import _reject_templates

    skills = Path(str(adapter_request["skills_dir"]))
    (skills / "osis-check-repair" / "references" / "templates").mkdir(parents=True)
    try:
        _reject_templates(skills)
    except RuntimeError as exc:
        assert "templates" in str(exc)
    else:
        raise AssertionError("templates were accepted")
