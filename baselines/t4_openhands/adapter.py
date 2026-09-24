"""T4: OpenHands native skills plus the SDK's default terminal and file editor."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from baselines._framework_common import (
    finish,
    model_api_settings,
    LIBRARY_LOOP_BOUND,
    package_version,
)


Runtime = Callable[[dict[str, Any], str, list[Any]], dict[str, Any]]


def load_native_skills(skills_dir: Path, loader: Callable[[Path], Any] | None = None) -> list[Any]:
    if loader is None:
        from openhands.sdk.skills import load_skills_from_dir

        loader = load_skills_from_dir
    groups = loader(Path(skills_dir))
    result: list[Any] = []
    for group in groups:
        if isinstance(group, dict):
            result.extend(group.values())
    return result


def native_tool_specs() -> list[Any]:
    """OpenHands default exec tools. Browser stays off, matching the modeling line."""

    from openhands.tools.preset.default import get_default_tools

    return get_default_tools(enable_browser=False)


def build_t4_prompt(request: dict[str, Any]) -> str:
    return (
        "Repair the failed check in the staged candidate. Use the native invoke_skill tool "
        "(OpenHands InvokeSkillTool) first to load the relevant AgentSkill. Then use the "
        "framework terminal and file editor in the candidate workspace. Do not reconstruct "
        "skill bodies from an injected inventory. Finish with FinishTool and the localization JSON.\n\n"
        + json.dumps(request["task"], ensure_ascii=False, indent=2)
    )


def _event_summary(events: list[Any]) -> tuple[list[dict[str, Any]], int, int]:
    trace: list[dict[str, Any]] = []
    response_ids: set[str] = set()
    tool_calls = 0
    for event in events:
        tool_name = str(getattr(event, "tool_name", None) or "")
        response_id = getattr(event, "llm_response_id", None)
        if response_id:
            response_ids.add(str(response_id))
        if tool_name:
            tool_calls += 1
        trace.append(
            {
                "event_type": type(event).__name__,
                "tool_name": tool_name,
                "llm_response_id": str(response_id or ""),
            }
        )
    return trace, len(response_ids) or int(bool(events)), tool_calls


def _openhands_runtime(request: dict[str, Any], prompt: str, native_skills: list[Any]) -> dict[str, Any]:
    from openhands.sdk import Agent, AgentContext, Conversation, LLM
    from openhands.sdk.conversation import get_agent_final_response

    settings = model_api_settings(request)
    tools = native_tool_specs()
    llm_kwargs: dict[str, Any] = {
        "model": f"openai/{settings['model']}",
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "timeout": int(settings["timeout"]),
        "num_retries": 2,
        "api_mode": "chat",
        "temperature": settings["temperature"],
        "usage_id": "t4-check-repair",
    }
    if settings["max_tokens"] is not None:
        llm_kwargs["max_output_tokens"] = settings["max_tokens"]
    workspace = Path(request["workspace"]) / "candidate_project"
    workspace.mkdir(parents=True, exist_ok=True)
    agent = Agent(
        llm=LLM(**llm_kwargs),
        tools=tools,
        agent_context=AgentContext(
            skills=native_skills,
            load_user_skills=False,
            load_public_skills=False,
            load_project_skills=False,
            load_memory=False,
        ),
    )
    conversation = Conversation(
        agent=agent,
        workspace=str(workspace),
        max_iteration_per_run=LIBRARY_LOOP_BOUND,
        visualizer=None,
        delete_on_close=False,
        stuck_detection_thresholds={
            "action_observation": 24,
            "action_error": 12,
            "monologue": 12,
            "alternating_pattern": 40,
        },
    )
    try:
        conversation.send_message(prompt)
        conversation.run()
        events = list(getattr(conversation.state, "events", []) or [])
        trace, model_calls, tool_calls = _event_summary(events)
        status = str(getattr(conversation.state, "execution_status", ""))
        return {
            "final_answer": (get_agent_final_response(events) or "")[-4000:],
            "execution_status": status,
            "framework_tools": [tool.name for tool in tools],
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "framework_steps": len(events),
            "events": trace,
        }
    finally:
        conversation.close()


def run_generation(
    request: dict[str, Any],
    *,
    runtime: Runtime | None = None,
    skill_loader: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T4",
        "framework": "openhands",
        "framework_version": package_version("openhands-sdk"),
        "interaction_mode": "codeact",
        "skill_loading": "openhands_native_progressive",
        "native_skill_count": 0,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "framework_steps": 0,
        "status": "failed",
    }
    try:
        native_skills = load_native_skills(Path(request["skills_dir"]), loader=skill_loader)
        metadata["native_skill_count"] = len(native_skills)
        output = (runtime or _openhands_runtime)(request, build_t4_prompt(request), native_skills)
        metadata.update(output)
        execution = str(output.get("execution_status", "")).upper()
        failed = "ERROR" in execution or "STUCK" in execution
        metadata.update(status="failed" if failed else "completed", stop_reason=execution.lower() or "completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T4", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
