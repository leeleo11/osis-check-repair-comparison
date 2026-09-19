"""The only task representation allowed to cross into framework adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


PUBLIC_FIELDS = frozenset(
    {
        "task_id",
        "bridge_type",
        "difficulty",
        "natural_language_prompt",
        "protocol_version",
        "total_timeout_s",
        "metadata",
    }
)

PRIVATE_FIELDS = frozenset(
    {
        "seed",
        "reason_code",
        "ng_baseline",
        "ng_seeded",
        "seeded_path",
        "template_path",
        "how",
        "notes",
    }
)


def _nonempty_string(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_metadata(value: object) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be an object")
    forbidden = PRIVATE_FIELDS.intersection(str(key) for key in value)
    if forbidden:
        raise ValueError(f"metadata contains private fields: {sorted(forbidden)}")
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class CheckRepairTaskSpec:
    task_id: str
    bridge_type: str
    difficulty: str
    natural_language_prompt: str
    protocol_version: str = "check-repair-v2"
    total_timeout_s: int = 1800
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CheckRepairTaskSpec":
        if not isinstance(data, Mapping):
            raise ValueError("task must be an object")
        supplied = {str(key) for key in data}
        private = supplied & PRIVATE_FIELDS
        if private:
            raise ValueError(f"private fields are forbidden: {sorted(private)}")
        unknown = supplied - PUBLIC_FIELDS
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")

        protocol_version = str(data.get("protocol_version", "check-repair-v2")).strip()
        if protocol_version != "check-repair-v2":
            raise ValueError("protocol_version must be check-repair-v2")
        timeout = data.get("total_timeout_s", 1800)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise ValueError("total_timeout_s must be a positive integer")

        return cls(
            task_id=_nonempty_string(data, "task_id"),
            bridge_type=_nonempty_string(data, "bridge_type"),
            difficulty=_nonempty_string(data, "difficulty"),
            natural_language_prompt=_nonempty_string(data, "natural_language_prompt"),
            protocol_version=protocol_version,
            total_timeout_s=timeout,
            metadata=_validate_metadata(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "bridge_type": self.bridge_type,
            "difficulty": self.difficulty,
            "natural_language_prompt": self.natural_language_prompt,
            "protocol_version": self.protocol_version,
            "total_timeout_s": self.total_timeout_s,
            "metadata": dict(self.metadata),
        }
