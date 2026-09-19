"""T2: LangGraph create_agent with streamed ReAct tool use."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import (
    BoundedTools,
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    resolve_max_steps,
)


Runtime = Callable[[dict[str, Any], str, BoundedTools], dict[str, Any]]


def _langgraph_runtime(request: dict[str, Any], prompt: str, tools: BoundedTools) -> dict[str, Any]:
    from langchain.agents import create_agent
    from langchain_core.tools import StructuredTool
    from langchain_openai import ChatOpenAI

    settings = model_api_settings(request)
    model_kwargs: dict[str, Any] = {
        "model": settings["model"],
        "base_url": settings["base_url"],
        "api_key": settings["api_key"],
        "temperature": settings["temperature"],
        "timeout": settings["timeout"],
    }
    if settings["max_tokens"] is not None:
        model_kwargs["max_tokens"] = settings["max_tokens"]
    model = ChatOpenAI(**model_kwargs)
    tool_defs = [StructuredTool.from_function(function) for function in tools.functions()]
    agent = create_agent(model=model, tools=tool_defs)

    trace: list[dict[str, Any]] = []
    seen_messages = 0
    model_calls = 0
    tool_calls = 0
    final_answer = ""
    for state in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": resolve_max_steps(request.get("max_steps")) * 2 + 2},
        stream_mode="values",
    ):
        messages = list(state.get("messages") or []) if isinstance(state, dict) else []
        for message in messages[seen_messages:]:
            kind = type(message).__name__
            content = str(getattr(message, "content", "") or "")
            calls = list(getattr(message, "tool_calls", None) or [])
            if kind == "AIMessage":
                model_calls += 1
                final_answer = content or final_answer
            if kind == "ToolMessage":
                tool_calls += 1
            trace.append(
                {
                    "kind": kind,
                    "tool_names": [str(call.get("name", "")) for call in calls if isinstance(call, dict)],
                    "content_preview": content[:500],
                }
            )
        seen_messages = max(seen_messages, len(messages))
    return {
        "final_answer": final_answer,
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "trace": trace,
    }


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T2",
        "framework": "langgraph",
        "framework_version": package_version("langgraph"),
        "interaction_mode": "react",
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _langgraph_runtime)(request, build_prompt(request), BoundedTools(request))
        metadata.update(output)
        metadata.update(status="completed", stop_reason="completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T2", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
