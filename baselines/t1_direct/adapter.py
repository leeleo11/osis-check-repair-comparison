"""T1: one model request, no interactive framework tools."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

import requests

from baselines._framework_common import candidate_workspace, finish, model_api_settings, skill_reader


FILE_BLOCK = re.compile(r"^### FILE:\s*(?P<path>.+?)\s*$", re.MULTILINE)
Completion = Callable[[str, dict[str, object]], dict[str, object]]


def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(FILE_BLOCK.finditer(str(text)))
    files: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else ""
            if content.rstrip().endswith("```"):
                content = content.rstrip()[:-3]
        files.append((match.group("path").strip(), content.strip() + "\n"))
    return files


def _candidate_bundle(request: dict[str, Any], char_budget: int = 180_000) -> str:
    candidate = candidate_workspace(request)
    parts: list[str] = []
    used = 0
    for relative in candidate.list_files():
        try:
            body = candidate.read_text(relative)
        except (OSError, UnicodeError):
            continue
        block = f"\n### CURRENT FILE: {relative}\n{body}"
        if used + len(block) > char_budget:
            remaining = max(0, char_budget - used)
            parts.append(block[:remaining])
            break
        parts.append(block)
        used += len(block)
    return "".join(parts)


def build_t1_prompt(request: dict[str, Any]) -> str:
    reader = skill_reader(request)
    return (
        "You are T1, the direct one-shot baseline. You have one response and no tools.\n"
        "Diagnose and repair the named failed check by returning complete replacement files.\n"
        "For each changed file emit exactly: ### FILE: relative/path, then its full content.\n"
        "Only paths inside the candidate project are accepted. End with one localizations JSON object.\n\n"
        "PUBLIC TASK:\n"
        + json.dumps(request["task"], ensure_ascii=False, indent=2)
        + "\n\nPUBLIC SKILL SNAPSHOT:\n"
        + reader.fixed_bundle_text()
        + "\n\nSTAGED CANDIDATE:\n"
        + _candidate_bundle(request)
    )


def _http_completion(prompt: str, settings: dict[str, object]) -> dict[str, object]:
    base_url = str(settings["base_url"]).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.get("api_key"):
        headers["Authorization"] = f"Bearer {settings['api_key']}"
    payload: dict[str, object] = {
        "model": settings["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings["temperature"],
    }
    if settings.get("max_tokens") is not None:
        payload["max_tokens"] = settings["max_tokens"]
    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=float(settings["timeout"]),
    )
    response.raise_for_status()
    body = response.json()
    choice = body["choices"][0]
    return {
        "text": choice.get("message", {}).get("content", ""),
        "usage": body.get("usage", {}),
        "finish_reason": choice.get("finish_reason"),
    }


def run_generation(
    request: dict[str, Any],
    *,
    completion: Completion | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "architecture_id": "T1",
        "framework": "direct-one-shot",
        "interaction_mode": "one_shot",
        "model": request.get("model"),
        "model_calls": 0,
        "tool_calls": 0,
        "status": "failed",
        "rejected_files": [],
    }
    try:
        metadata["model_calls"] = 1
        response = (completion or _http_completion)(build_t1_prompt(request), model_api_settings(request))
        text = str(response.get("text") or "")
        accepted = 0
        candidate = candidate_workspace(request)
        for relative, content in parse_file_blocks(text):
            try:
                candidate.write_text(relative, content)
                accepted += 1
            except (ValueError, OSError):
                metadata["rejected_files"].append(relative)
        metadata.update(
            {
                "status": "completed" if accepted else "no_valid_file_blocks",
                "file_blocks": accepted,
                "final_answer": text[-4000:],
                "usage": response.get("usage", {}),
                "stop_reason": response.get("finish_reason") or "completed",
            }
        )
    except Exception as exc:  # noqa: BLE001
        metadata.update(error_type=type(exc).__name__, error=str(exc)[:500], stop_reason="error")
    return finish(Path(request["workspace"]), "T1", metadata, started)


def main() -> int:
    from baselines._framework_common import load_request

    run_generation(load_request())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
