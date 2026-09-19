"""T5: sequential diagnoser, repairer, and read-only verifier roles."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")

from baselines._framework_common import (
    BoundedTools,
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


ROLE_ORDER = ("diagnoser", "repairer", "verifier")
Runtime = Callable[[dict[str, Any], str, dict[str, BoundedTools]], dict[str, Any]]


def build_role_tools(request: dict[str, Any]) -> dict[str, BoundedTools]:
    return {
        "diagnoser": BoundedTools(request, allow_write=False),
        "repairer": BoundedTools(request, allow_write=True),
        "verifier": BoundedTools(request, allow_write=False),
    }


def _role_budgets(max_steps: int) -> dict[str, int]:
    total = max(3, max_steps)
    diagnosis = max(1, total // 4)
    verification = max(1, total // 4)
    return {
        "diagnoser": diagnosis,
        "repairer": total - diagnosis - verification,
        "verifier": verification,
    }


def _crewai_runtime(
    request: dict[str, Any],
    prompt: str,
    role_tools: dict[str, BoundedTools],
) -> dict[str, Any]:
    from crewai import Agent, Crew, Process, Task
    from crewai.llm import LLM
    from crewai.tools import tool

    settings = model_api_settings(request)
    llm_kwargs: dict[str, Any] = {
        "model": settings["model"],
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "custom_openai": True,
        "timeout": settings["timeout"],
        "temperature": settings["temperature"],
    }
    if settings["max_tokens"] is not None:
        llm_kwargs["max_tokens"] = settings["max_tokens"]
    llm = LLM(**llm_kwargs)
    budgets = _role_budgets(resolve_max_steps(request.get("max_steps")))

    def wrapped(role: str) -> list[Any]:
        return [tool(function) for function in role_tools[role].functions()]

    policy = {"allow_delegation": False, "allow_code_execution": False, "verbose": False}
    diagnoser = Agent(
        role="Check failure diagnoser",
        goal="Use public skills and candidate files to identify the smallest plausible root cause.",
        backstory="OSIS diagnosis specialist who never edits files.",
        llm=llm,
        tools=wrapped("diagnoser"),
        max_iter=budgets["diagnoser"],
        **policy,
    )
    repairer = Agent(
        role="Candidate repair engineer",
        goal="Apply the diagnosis as a minimal bounded candidate edit and compile it.",
        backstory="OSIS engineer authorized to edit only the staged candidate.",
        llm=llm,
        tools=wrapped("repairer"),
        max_iter=budgets["repairer"],
        **policy,
    )
    verifier = Agent(
        role="Read-only repair reviewer",
        goal="Inspect and compile the candidate, then report risks and final localization JSON.",
        backstory="Independent reviewer with no write capability and no access to the official scorer.",
        llm=llm,
        tools=wrapped("verifier"),
        max_iter=budgets["verifier"],
        **policy,
    )
    diagnose_task = Task(
        description="Diagnose this public task without editing.\n\n" + prompt,
        expected_output="A concise diagnosis with evidence and a proposed edit.",
        agent=diagnoser,
    )
    repair_task = Task(
        description="Apply the prior diagnosis to the candidate, then compile all Python files.",
        expected_output="Edited file list and repair rationale.",
        agent=repairer,
        context=[diagnose_task],
    )
    verify_task = Task(
        description="Review the candidate read-only. Report compile status and final localizations JSON.",
        expected_output="Read-only verification verdict and localization JSON.",
        agent=verifier,
        context=[diagnose_task, repair_task],
    )
    result = Crew(
        agents=[diagnoser, repairer, verifier],
        tasks=[diagnose_task, repair_task, verify_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()
    outputs = getattr(result, "tasks_output", None) or []
    return {
        "final_answer": str(getattr(result, "raw", result))[-4000:],
        "role_outputs": {
            role: str(output)[-2000:]
            for role, output in zip(ROLE_ORDER, outputs, strict=False)
        },
        "model_calls": len(outputs),
        "tool_calls": 0,
        "role_budgets": budgets,
    }


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T5",
        "framework": "crewai",
        "framework_version": package_version("crewai"),
        "interaction_mode": "sequential_roles",
        "roles": list(ROLE_ORDER),
        "verifier_write_access": False,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _crewai_runtime)(request, build_prompt(request), build_role_tools(request))
        metadata.update(output)
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T5", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
