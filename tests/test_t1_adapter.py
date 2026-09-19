from __future__ import annotations

import json
from pathlib import Path

from baselines.t1_direct.adapter import parse_file_blocks, run_generation


def test_parse_file_blocks_handles_fenced_content() -> None:
    parsed = parse_file_blocks("### FILE: py/main.py\n```python\nVALUE = 2\n```\n")
    assert parsed == [("py/main.py", "VALUE = 2\n")]


def test_t1_is_one_call_and_writes_only_bounded_file_blocks(adapter_request: dict[str, object]) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(prompt: str, settings: dict[str, object]) -> dict[str, object]:
        calls.append({"prompt": prompt, "settings": settings})
        return {
            "text": (
                "### FILE: py/main.py\nVALUE = 2\n"
                "### FILE: ../escape.py\nBAD = True\n"
            ),
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "finish_reason": "stop",
        }

    result = run_generation(adapter_request, completion=fake_completion)
    workspace = Path(str(adapter_request["workspace"]))
    assert len(calls) == 1
    assert (workspace / "candidate_project" / "py" / "main.py").read_text() == "VALUE = 2\n"
    assert not (workspace / "escape.py").exists()
    assert result["architecture_id"] == "T1"
    assert result["model_calls"] == 1
    assert result["rejected_files"] == ["../escape.py"]
    assert json.loads((workspace / "t1_generation.json").read_text())["framework"] == "direct-one-shot"
