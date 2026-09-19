"""T4: OpenHands Conversation with native progressive AgentSkills."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from baselines._framework_common import (
    BoundedTools,
    finish,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


Runtime = Callable[[dict[str, Any], str, BoundedTools, list[Any]], dict[str, Any]]


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


def build_t4_prompt(request: dict[str, Any]) -> str:
    return (
        "Repair the failed check in the staged candidate. First use InvokeSkillTool to load the "
        "relevant native AgentSkill, then inspect candidate files, make the smallest safe edit, "
        "compile the candidate, and finish with the required localizations JSON. The official "
        "verifier runs after this conversation.\n\n"
        + json.dumps(request["task"], ensure_ascii=False, indent=2)
    )


def _expose(name: str, description: str, properties: dict[str, Any], required: list[str], function: Callable[..., str]) -> Any:
    from openhands.sdk import Tool
    from openhands.sdk.tool import Action, Observation, ToolDefinition, ToolExecutor, register_tool

    action_type = Action.from_mcp_schema(
        f"{name}_action",
        {"type": "object", "properties": properties, "required": required},
    )

    class HarnessObservation(Observation):
        """Bounded harness tool output."""

    class Executor(ToolExecutor):
        def __call__(self, action, conversation=None):  # noqa: ANN001
            arguments = {key: value for key, value in action.model_dump().items() if key in properties}
            try:
                return HarnessObservation.from_text(text=str(function(**arguments)))
            except Exception as exc:  # noqa: BLE001
                return HarnessObservation.from_text(text=f"TOOL_ERROR: {type(exc).__name__}: {exc}", is_error=True)

    class Definition(ToolDefinition[action_type, HarnessObservation]):
        @classmethod
        def create(cls, conv_state=None, **kwargs):  # noqa: ANN001
            return [
                cls(
                    description=description,
                    action_type=action_type,
                    observation_type=HarnessObservation,
                    executor=Executor(),
                )
            ]

    Definition.name = name
    definition = Definition.create()[0]
    register_tool(name, definition)
    return Tool(name=name)


def _event_summary(events: list[Any]) -> tuple[list[dict[str, Any]], int, int]:
    trace: list[dict[str, Any]] = []
    response_ids: set[str] = set()
    tool_calls = 0
    for event in events:
        response_id = getattr(event, "llm_response_id", None)
        if response_id:
            response_ids.add(str(response_id))
        tool_name = getattr(event, "tool_name", None)
        if type(event).__name__ == "ActionEvent" or tool_name:
            tool_calls += 1
        trace.append(
            {
                "kind": type(event).__name__,
                "tool_name": str(tool_name or ""),
                "llm_response_id": str(response_id or ""),
            }
        )
    return trace, len(response_ids) or int(bool(events)), tool_calls


def _openhands_runtime(
    request: dict[str, Any],
    prompt: str,
    tools: BoundedTools,
    native_skills: list[Any],
) -> dict[str, Any]:
    from openhands.sdk import Agent, AgentContext, Conversation, LLM
    from openhands.sdk.conversation import get_agent_final_response

    settings = model_api_settings(request)
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
    llm = LLM(**llm_kwargs)
    exposed = [
        _expose("list_candidate_files", "List staged candidate files.", {}, [], tools.list_candidate_files),
        _expose(
            "read_candidate_file",
            "Read a staged candidate file.",
            {"relative_path": {"type": "string"}},
            ["relative_path"],
            tools.read_candidate_file,
        ),
        _expose(
            "write_candidate_file",
            "Replace one candidate text file.",
            {"relative_path": {"type": "string"}, "content": {"type": "string"}},
            ["relative_path", "content"],
            tools.write_candidate_file,
        ),
        _expose("compile_candidate", "Parse candidate Python files.", {}, [], tools.compile_candidate),
        _expose(
            "read_skill_reference",
            "Read a reference named by an invoked native skill.",
            {"skill_id": {"type": "string"}, "relative_path": {"type": "string"}},
            ["skill_id", "relative_path"],
            tools.read_skill_reference,
        ),
    ]
    agent = Agent(
        llm=llm,
        tools=exposed,
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
        workspace=str(tools.candidate.root),
        max_iteration_per_run=resolve_max_steps(request.get("max_steps")),
        visualizer=None,
        delete_on_close=False,
        stuck_detection_thresholds={
            "action_observation": 16,
            "action_error": 8,
            "monologue": 8,
            "alternating_pattern": 24,
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
        output = (runtime or _openhands_runtime)(
            request,
            build_t4_prompt(request),
            BoundedTools(request),
            native_skills,
        )
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
