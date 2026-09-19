from __future__ import annotations

import json
from pathlib import Path

import pytest

from check_repair.data import load_external_samples
from check_repair.sanitize import sanitize_for_model
from check_repair.schema import CheckRepairTaskSpec


def public_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "task_id": "cr-test",
        "bridge_type": "box-girder",
        "difficulty": "formal",
        "natural_language_prompt": "Repair the named failed check and report the final localization.",
        "protocol_version": "check-repair-v2",
        "total_timeout_s": 900,
        "metadata": {"language": "zh-CN"},
    }
    payload.update(overrides)
    return payload


def test_public_task_round_trip_is_stable_and_immutable() -> None:
    task = CheckRepairTaskSpec.from_dict(public_payload())
    assert task.to_dict() == public_payload()
    assert sanitize_for_model(task) == public_payload()
    with pytest.raises(AttributeError):
        task.task_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["task_id", "bridge_type", "natural_language_prompt"])
def test_required_string_must_be_nonempty(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        CheckRepairTaskSpec.from_dict(public_payload(**{field: "  "}))


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="total_timeout_s"):
        CheckRepairTaskSpec.from_dict(public_payload(total_timeout_s=0))


@pytest.mark.parametrize("field", ["seed", "reason_code", "ng_seeded", "seeded_path", "template_path", "how"])
def test_public_task_rejects_private_fields(field: str) -> None:
    with pytest.raises(ValueError, match="private|unknown"):
        CheckRepairTaskSpec.from_dict(public_payload(**{field: "secret"}))


def test_external_loader_keeps_private_reference_out_of_public_task(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    dataset = parent / "datasets" / "check_repair"
    seeded = dataset / "seeded" / "case-1"
    seeded.mkdir(parents=True)
    (seeded / "py").mkdir()
    records = [
        {
            "id": "cr-001",
            "bridge": "cantilever-box",
            "prompt": "Repair the named failed check.",
            "seeded_path": "datasets/check_repair/seeded/case-1",
            "seed": {"reason_code": "hidden-code", "file": "py/main.py", "how": "hidden edit"},
            "ng_baseline": [],
            "ng_seeded": ["target check"],
            "status": "seeded",
        },
        {"id": "skip", "status": "example"},
    ]
    (dataset / "samples.json").write_text(json.dumps(records), encoding="utf-8")

    samples = load_external_samples(parent)
    assert [sample.task_id for sample in samples] == ["cr-001"]
    public = samples[0].to_public_task().to_dict()
    private = samples[0].private_reference()
    assert set(public).isdisjoint({"seed", "reason_code", "ng_seeded", "seeded_path"})
    assert private.expected_reason_code == "hidden-code"
    assert private.seeded_project == seeded.resolve()


def test_external_loader_rejects_path_escape(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    dataset = parent / "datasets" / "check_repair"
    dataset.mkdir(parents=True)
    records = [
        {
            "id": "escape",
            "bridge": "synthetic",
            "prompt": "repair",
            "seeded_path": "../outside",
            "seed": {"reason_code": "x"},
            "ng_seeded": ["target"],
            "status": "seeded",
        }
    ]
    (dataset / "samples.json").write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="outside parent"):
        load_external_samples(parent)
