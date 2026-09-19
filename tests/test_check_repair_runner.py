from __future__ import annotations

import json
from pathlib import Path

from check_repair.data import ExternalSample, PrivateReference
from check_repair.ng import CheckRow
from check_repair.runner import CheckRepairRunner
from check_repair.verifier import VerificationResult


def _sample(tmp_path: Path) -> ExternalSample:
    seeded = tmp_path / "external" / "case"
    (seeded / "py").mkdir(parents=True)
    (seeded / "py" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    post = seeded / "OSISPost.out"
    post.write_text("native", encoding="utf-8")
    private = PrivateReference(
        expected_reason_code="material_grade",
        target_item="target check",
        ng_baseline=(),
        ng_seeded=("target check",),
        seeded_project=seeded,
        osis_post=post,
        seed_file="py/main.py",
        seed_how="private edit",
    )
    return ExternalSample(
        task_id="cr-test",
        bridge_type="synthetic",
        prompt="Repair target check and return localization JSON.",
        difficulty="formal",
        protocol_version="check-repair-v2",
        total_timeout_s=120,
        _private=private,
    )


class FakeNativeEvaluator:
    def __init__(self, seeded_ng=("target check",), repaired_ng=()):
        self.results = [seeded_ng, repaired_ng]
        self.calls: list[Path] = []

    def evaluate(self, candidate_project: Path, post_out: Path | None):
        self.calls.append(candidate_project)
        ng = tuple(self.results[len(self.calls) - 1])
        rows = tuple(CheckRow(f"01_{name}_case", "NG", 0, 1) for name in ng)
        if not rows:
            rows = (CheckRow("01_target check_case", "OK", 1, 0),)
        return VerificationResult(rows=rows, ng_items=ng, check_mode="fake")


def test_runner_stages_privately_verifies_scores_and_writes_manifest(tmp_path: Path) -> None:
    sample = _sample(tmp_path)
    evaluator = FakeNativeEvaluator()
    seen_request: dict[str, object] = {}

    def generator(request: dict[str, object]) -> dict[str, object]:
        seen_request.update(request)
        candidate = Path(str(request["workspace"])) / "candidate_project" / "py" / "main.py"
        candidate.write_text("VALUE = 2\n", encoding="utf-8")
        return {
            "status": "completed",
            "final_answer": '{"localizations":[{"check_item":"x","reason_code":"material_grade"}]}',
            "model_calls": 2,
            "tool_calls": 1,
        }

    runner = CheckRepairRunner(
        runs_root=tmp_path / "runs",
        skills_dir=tmp_path / "skills",
        native_evaluator=evaluator,
        generator=generator,
        parent_commit="abc123",
    )
    result = runner.run(sample, "T2", seed=7, model="test-model", label="unit")

    run_dir = Path(result["run_dir"])
    assert result["status"] == "completed"
    assert result["evaluation"]["localization_score"] == 1.0
    assert result["evaluation"]["repair_pass"] is True
    assert (run_dir / "private" / "seeded_project" / "py" / "main.py").is_file()
    public_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    assert set(public_input).isdisjoint({"seed", "reason_code", "ng_seeded", "seeded_path"})
    request_text = json.dumps(seen_request, ensure_ascii=False)
    assert "material_grade" not in request_text
    assert "private edit" not in request_text
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["parent_commit"] == "abc123"
    assert manifest["seed"] == 7
    assert "E:\\" not in json.dumps(manifest)
    assert len(evaluator.calls) == 2


def test_seeded_ng_mismatch_fails_before_model_call(tmp_path: Path) -> None:
    sample = _sample(tmp_path)
    evaluator = FakeNativeEvaluator(seeded_ng=("unexpected",))
    called = False

    def generator(request):
        nonlocal called
        called = True
        return {}

    runner = CheckRepairRunner(
        runs_root=tmp_path / "runs",
        skills_dir=tmp_path / "skills",
        native_evaluator=evaluator,
        generator=generator,
    )
    result = runner.run(sample, "T3", seed=1, model="test", label="mismatch")
    assert result["status"] == "failed"
    assert result["failure_code"] == "SEEDED_NG_MISMATCH"
    assert called is False


def test_resume_returns_existing_completed_run_without_reexecution(tmp_path: Path) -> None:
    sample = _sample(tmp_path)
    evaluator = FakeNativeEvaluator()
    calls = 0

    def generator(request):
        nonlocal calls
        calls += 1
        return {"status": "completed", "final_answer": "{}"}

    runner = CheckRepairRunner(
        runs_root=tmp_path / "runs",
        skills_dir=tmp_path / "skills",
        native_evaluator=evaluator,
        generator=generator,
    )
    runner.run(sample, "T1", seed=0, model="test", label="resume")
    second = runner.run(sample, "T1", seed=0, model="test", label="resume", resume=True)
    assert second["resumed"] is True
    assert calls == 1
