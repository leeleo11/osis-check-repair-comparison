"""Trusted loader for the external parent dataset.

This module deliberately separates the public task from the private reference.
Adapters receive only :class:`CheckRepairTaskSpec`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .schema import CheckRepairTaskSpec


_TARGET = re.compile(r"本项目「([^」]+)」不通过")


def _resolve_under(root: Path, value: str | Path, *, label: str) -> Path:
    root = root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} resolves outside parent repository") from exc
    return candidate


def _strings(value: object, *, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} must be a list")
    return tuple(str(item).strip() for item in value if str(item).strip())


@dataclass(frozen=True, slots=True)
class PrivateReference:
    expected_reason_code: str
    target_item: str
    ng_baseline: tuple[str, ...]
    ng_seeded: tuple[str, ...]
    seeded_project: Path
    osis_post: Path | None
    seed_file: str
    seed_how: str


@dataclass(frozen=True, slots=True)
class ExternalSample:
    task_id: str
    bridge_type: str
    prompt: str
    difficulty: str
    protocol_version: str
    total_timeout_s: int
    _private: PrivateReference

    def to_public_task(self) -> CheckRepairTaskSpec:
        return CheckRepairTaskSpec(
            task_id=self.task_id,
            bridge_type=self.bridge_type,
            difficulty=self.difficulty,
            natural_language_prompt=self.prompt,
            protocol_version=self.protocol_version,
            total_timeout_s=self.total_timeout_s,
        )

    def private_reference(self) -> PrivateReference:
        return self._private


def _sample_from_record(parent: Path, record: Mapping[str, Any]) -> ExternalSample:
    task_id = str(record.get("id") or "").strip()
    bridge = str(record.get("bridge") or "").strip()
    prompt = str(record.get("prompt") or "").strip()
    if not task_id or not bridge or not prompt:
        raise ValueError("seeded sample requires id, bridge, and prompt")

    seeded_value = str(record.get("seeded_path") or "").strip()
    if not seeded_value:
        raise ValueError(f"{task_id}: seeded_path is required")
    seeded_project = _resolve_under(parent, seeded_value, label=f"{task_id} seeded_path")

    seed = record.get("seed")
    if not isinstance(seed, Mapping):
        raise ValueError(f"{task_id}: seed must be an object")
    expected = str(seed.get("reason_code") or "").strip()
    if not expected:
        raise ValueError(f"{task_id}: seed.reason_code is required")

    match = _TARGET.search(prompt)
    target = match.group(1).strip() if match else str(record.get("target_item") or "").strip()
    if not target:
        # Synthetic/private test datasets may omit the Chinese wrapper. The
        # verifier still requires a concrete target before formal scoring.
        target = _strings(record.get("ng_seeded"), label="ng_seeded")[0]

    post_path = seeded_project / "OSISPost.out"
    private = PrivateReference(
        expected_reason_code=expected,
        target_item=target,
        ng_baseline=_strings(record.get("ng_baseline"), label="ng_baseline"),
        ng_seeded=_strings(record.get("ng_seeded"), label="ng_seeded"),
        seeded_project=seeded_project,
        osis_post=post_path if post_path.is_file() else None,
        seed_file=str(seed.get("file") or ""),
        seed_how=str(seed.get("how") or ""),
    )
    return ExternalSample(
        task_id=task_id,
        bridge_type=bridge,
        prompt=prompt,
        difficulty=str(record.get("difficulty") or "formal").strip() or "formal",
        protocol_version="check-repair-v2",
        total_timeout_s=int(record.get("total_timeout_s") or 1800),
        _private=private,
    )


def load_external_samples(
    parent_repo: str | Path,
    samples_path: str | Path | None = None,
) -> list[ExternalSample]:
    parent = Path(parent_repo).resolve()
    source = _resolve_under(
        parent,
        samples_path or Path("datasets/check_repair/samples.json"),
        label="samples_path",
    )
    records = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("samples file must contain a JSON list")
    samples: list[ExternalSample] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("each sample must be an object")
        if str(record.get("status") or "") != "seeded":
            continue
        samples.append(_sample_from_record(parent, record))
    return samples
