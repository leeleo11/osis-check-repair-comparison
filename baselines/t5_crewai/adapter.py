"""T5: CrewAI native skills, delegation, and file tools. Same policy as the modeling line."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")

from baselines._framework_common import (
    build_prompt,
    finish,
    model_api_settings,
    package_version,
    LIBRARY_LOOP_BOUND,
)


ROLE_ORDER = ("diagnoser", "repairer", "verifier")
ROLE_CAN_WRITE = {"diagnoser": False, "repairer": True, "verifier": False}
# CrewAI's code interpreter is deprecated and no longer registers a tool.
AGENT_POLICY = {"allow_code_execution": False, "allow_delegation": True}
_RESOURCE_ROOTS = ("references", "scripts", "assets")
_SKILL_NAME = re.compile(r"(?m)^name:\s*(?P<name>\S+)\s*$")
Runtime = Callable[[dict[str, Any], str], dict[str, Any]]


def _find_skill_dir(skills_dir: Path, skill_name: str) -> Path | None:
    for child in Path(skills_dir).iterdir():
        skill_md = child / "SKILL.md"
        if not child.is_dir() or not skill_md.is_file():
            continue
        if child.name == skill_name:
            return child
        match = _SKILL_NAME.search(skill_md.read_text(encoding="utf-8", errors="replace"))
        if match and match.group("name") == skill_name:
            return child
    return None


def read_skill_resource(skills_dir: Path, skill_name: str, relative_path: str = "") -> str:
    """CrewAI load_skill returns only SKILL.md. This reads one resource file."""

    skill_dir = _find_skill_dir(skills_dir, skill_name)
    if skill_dir is None:
        return f"Skill {skill_name!r} is not available."
    relative = relative_path.strip().replace("\\", "/")
    if not relative:
        lines: list[str] = []
        for folder in _RESOURCE_ROOTS:
            base = skill_dir / folder
            if not base.is_dir():
                continue
            files = sorted(path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file())
            if files:
                lines.append(f"{folder}/: " + ", ".join(files))
        return "\n".join(lines) or "No resource files."
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] not in _RESOURCE_ROOTS:
        return "Path must be one file inside references/, scripts/, or assets/."
    target = (skill_dir / path).resolve()
    if not target.is_file() or not target.is_relative_to((skill_dir / path.parts[0]).resolve()):
        return f"File not found: {path.as_posix()}"
    return target.read_text(encoding="utf-8", errors="replace")


def _file_tools(root: Path, *, write: bool) -> list[Any]:
    from crewai_tools import DirectoryReadTool, FileReadTool, FileWriterTool

    tools: list[Any] = [
        DirectoryReadTool(directory=str(root)),
        FileReadTool(base_dir=str(root)),
    ]
    if write:
        tools.append(FileWriterTool(base_dir=str(root)))
    return tools


def _crewai_runtime(request: dict[str, Any], prompt: str) -> dict[str, Any]:
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
    skills_dir = Path(request["skills_dir"])
    candidate = Path(request["workspace"]) / "candidate_project"
    candidate.mkdir(parents=True, exist_ok=True)

    @tool("read_skill_resource")
    def read_skill_resource_tool(skill_name: str, relative_path: str = "") -> str:
        """List resource file names, or read one file under references, scripts, or assets."""

        return read_skill_resource(skills_dir, skill_name, relative_path)

    resource = [read_skill_resource_tool]
    diagnoser = Agent(
        role="Check failure diagnoser",
        goal="Load the mounted skills and identify the smallest plausible root cause.",
        backstory="OSIS diagnosis specialist. Uses the crew load_skill tool and does not write files.",
        llm=llm,
        tools=[*resource, *_file_tools(candidate, write=False)],
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    repairer = Agent(
        role="Candidate repair engineer",
        goal="Apply the diagnosis with CrewAI file tools inside the candidate directory.",
        backstory="OSIS engineer. Writes only through the File Writer Tool.",
        llm=llm,
        tools=[*resource, *_file_tools(candidate, write=True)],
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    verifier = Agent(
        role="Read-only repair reviewer",
        goal="Read the candidate and report the final localization JSON.",
        backstory="Independent reviewer. Reads files and does not write them.",
        llm=llm,
        tools=[*resource, *_file_tools(candidate, write=False)],
        max_iter=LIBRARY_LOOP_BOUND,
        verbose=False,
        **AGENT_POLICY,
    )
    diagnose_task = Task(
        description=(
            "Use load_skill and read_skill_resource. You may delegate or ask a coworker. "
            "Do not write files.\n\n" + prompt
        ),
        expected_output="A concise diagnosis with evidence and a proposed edit.",
        agent=diagnoser,
    )
    repair_task = Task(
        description="Apply the diagnosis by editing candidate files with the file writer.",
        expected_output="Edited file list and repair rationale.",
        agent=repairer,
        context=[diagnose_task],
    )
    verify_task = Task(
        description="Read the candidate. Do not write. Report the localization JSON.",
        expected_output="Read-only verification verdict and localization JSON.",
        agent=verifier,
        context=[diagnose_task, repair_task],
    )
    result = Crew(
        agents=[diagnoser, repairer, verifier],
        tasks=[diagnose_task, repair_task, verify_task],
        process=Process.sequential,
        verbose=False,
        skills=[skills_dir],
    ).kickoff()
    outputs = getattr(result, "tasks_output", None) or []
    return {
        "final_answer": str(getattr(result, "raw", result))[-4000:],
        "role_outputs": {
            role: str(output)[-2000:] for role, output in zip(ROLE_ORDER, outputs, strict=False)
        },
        "delegation": True,
        "model_calls": len(outputs),
        "tool_calls": 0,
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
        "allow_delegation": True,
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
    }
    try:
        output = (runtime or _crewai_runtime)(request, build_prompt(request))
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
