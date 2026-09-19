"""Serialization gate for anything sent to a model or framework process."""

from __future__ import annotations

from typing import Any

from .schema import CheckRepairTaskSpec


def sanitize_for_model(task: CheckRepairTaskSpec) -> dict[str, Any]:
    """Return a new, JSON-ready public payload."""
    if not isinstance(task, CheckRepairTaskSpec):
        raise TypeError("sanitize_for_model accepts CheckRepairTaskSpec only")
    return task.to_dict()
