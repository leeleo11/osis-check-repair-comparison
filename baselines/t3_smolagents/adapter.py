"""T3: smolagents CodeAgent. File access is the interpreter, not harness tools."""

from __future__ import annotations

import html
import re
import time
from pathlib import Path
from typing import Any, Callable

from baselines._framework_common import (
    finish,
    model_api_settings,
    LIBRARY_LOOP_BOUND,
    package_version,
)


AUTHORIZED_IMPORTS = ["json", "pathlib"]
Runtime = Callable[[dict[str, Any], str], dict[str, Any]]

_DSML_TAG = r"(?:｜｜DSML｜｜|\|DSML\|)"
_DSML_PARAMETER = re.compile(
    rf"<{_DSML_TAG}\s+invoke\s+name=[\"'](?P<invoke>[^\"']+)[\"'][^>]*>"
    rf"\s*<{_DSML_TAG}\s+parameter\s+name=[\"'](?P<parameter>[^\"']+)[\"'][^>]*>"
    rf"(?P<body>.*?)</{_DSML_TAG}\s+parameter>.*?</{_DSML_TAG}\s+invoke>",
    re.DOTALL,
)


def normalize_code_agent_output(text: str) -> str:
    """Unwrap a provider DSML envelope into CodeAgent's code envelope."""

    def replace(match: re.Match[str]) -> str:
        body = html.unescape(match.group("body")).strip()
        if match.group("invoke") == "code" or match.group("parameter") == "code":
            return f"<code>\n{body}\n</code>"
        return match.group(0)

    return _DSML_PARAMETER.sub(replace, text)


def build_t3_prompt(request: dict[str, Any]) -> str:
    skills = Path(request["skills_dir"])
    candidate = Path(request["workspace"]) / "candidate_project"
    task = request["task"]
    return (
        "Repair the named failed OSIS check by executing Python.\n"
        "Use import pathlib to read the mounted skills and to edit files inside the candidate.\n"
        "Each subdirectory of the skills directory that contains SKILL.md is one skill.\n"
        "Do not inspect parent datasets, hidden answers, or other runs.\n\n"
        f"Skills directory:\n{skills}\n\n"
        f"Candidate directory:\n{candidate}\n\n"
        "When the edit is done, call final_answer with the localization JSON and the files you changed.\n\n"
        + __import__("json").dumps(task, ensure_ascii=False, indent=2)
    )


def _smolagents_runtime(request: dict[str, Any], prompt: str) -> dict[str, Any]:
    from smolagents import CodeAgent, LogLevel, OpenAIServerModel

    class _CodeActCompatibleOpenAIModel(OpenAIServerModel):
        def generate(self, messages, *args, **kwargs):  # type: ignore[no-untyped-def]
            response = super().generate(messages, *args, **kwargs)
            content = getattr(response, "content", None)
            if isinstance(content, str):
                response.content = normalize_code_agent_output(content)
            return response

    settings = model_api_settings(request)
    model_kwargs: dict[str, Any] = {
        "model_id": settings["model"],
        "api_base": settings["base_url"],
        "api_key": settings["api_key"],
        "client_kwargs": {"timeout": settings["timeout"], "max_retries": 2},
        "temperature": settings["temperature"],
    }
    if settings["max_tokens"] is not None:
        model_kwargs["max_tokens"] = settings["max_tokens"]
    agent = CodeAgent(
        tools=[],
        model=_CodeActCompatibleOpenAIModel(**model_kwargs),
        max_steps=LIBRARY_LOOP_BOUND,
        verbosity_level=LogLevel.ERROR,
        additional_authorized_imports=AUTHORIZED_IMPORTS,
        return_full_result=True,
    )
    result = agent.run(prompt)
    steps = list(getattr(result, "steps", None) or [])
    state = str(getattr(result, "state", "success"))
    return {
        "final_answer": str(getattr(result, "output", result))[-4000:],
        "agent_state": state,
        "authorized_imports": list(AUTHORIZED_IMPORTS),
        "model_calls": len(steps),
        "tool_calls": sum(1 for step in steps if getattr(step, "tool_calls", None)),
        "framework_steps": len(steps),
    }


def run_generation(request: dict[str, Any], *, runtime: Runtime | None = None) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T3",
        "framework": "smolagents",
        "framework_version": package_version("smolagents"),
        "interaction_mode": "codeact",
        "authorized_imports": list(AUTHORIZED_IMPORTS),
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _smolagents_runtime)(request, build_t3_prompt(request))
        metadata.update(output)
        failed = str(output.get("agent_state", "")).lower() == "max_steps_error"
        metadata.update(status="failed" if failed else "completed", stop_reason="max_steps" if failed else "completed")
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T3", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
