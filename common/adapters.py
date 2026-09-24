"""Frozen architecture identities for the six-way comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    architecture_id: str
    name: str
    framework: str
    framework_version: str
    mounting_mode: str
    interaction_mode: str
    max_steps: int | None
    native_runtime: bool = False


ADAPTER_SPECS: dict[str, AdapterSpec] = {
    "T1": AdapterSpec("T1", "direct-one-shot", "http", "protocol-v1", "fixed_bundle", "one_shot", 1),
    "T2": AdapterSpec("T2", "langgraph-react", "langgraph", "1.2.11", "generic_tools", "react", 200),
    "T3": AdapterSpec("T3", "smolagents-codeact", "smolagents", "1.26.0", "generic_tools", "codeact", 200),
    "T4": AdapterSpec("T4", "openhands-codeact", "openhands", "1.49.2", "native_skills", "codeact", 200),
    "T5": AdapterSpec("T5", "crewai-roles", "crewai", "1.15.22", "role_tools", "sequential", 200),
    "T6": AdapterSpec("T6", "osis-ai-native", "opencode", "parent-pinned", "native", "stateful", 200, True),
}


def get_adapter(architecture_id: str) -> AdapterSpec:
    try:
        return ADAPTER_SPECS[architecture_id.upper()]
    except KeyError as exc:
        raise KeyError(f"unknown architecture: {architecture_id}") from exc
