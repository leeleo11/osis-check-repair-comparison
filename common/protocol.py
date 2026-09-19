"""JSON request/result contracts shared with isolated framework processes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from check_repair.schema import CheckRepairTaskSpec


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    architecture_id: str
    task: CheckRepairTaskSpec
    workspace: Path
    skills_dir: Path
    model: str
    variant: str = ""
    max_steps: int = 200
    max_output_tokens: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture_id": self.architecture_id,
            "task": self.task.to_dict(),
            "workspace": str(self.workspace),
            "skills_dir": str(self.skills_dir),
            "model": self.model,
            "variant": self.variant,
            "max_steps": self.max_steps,
            "max_output_tokens": self.max_output_tokens,
            "metadata": dict(self.metadata),
        }
