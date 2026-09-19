"""No-network adapter wiring smoke for T1 and T2."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from baselines.t1_direct.adapter import run_generation as run_t1
from baselines.t2_langgraph.adapter import run_generation as run_t2


def _request(root: Path, architecture: str) -> dict[str, object]:
    workspace = root / architecture.lower()
    if workspace.exists():
        shutil.rmtree(workspace)
    (workspace / "candidate_project" / "py").mkdir(parents=True)
    (workspace / "candidate_project" / "py" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    skills = root / "skills" / "synthetic"
    skills.mkdir(parents=True, exist_ok=True)
    (skills / "SKILL.md").write_text(
        "---\nname: Synthetic smoke\ndescription: Public no-answer smoke.\n---\nInspect before editing.\n",
        encoding="utf-8",
    )
    task = json.loads((PROJECT_ROOT / "tasks" / "smoke" / "check_repair_smoke.json").read_text(encoding="utf-8"))
    task.update(total_timeout_s=30, metadata={})
    return {
        "architecture_id": architecture,
        "task": task,
        "workspace": str(workspace),
        "skills_dir": str(skills.parent),
        "model": "no-network-smoke",
        "base_url": "",
        "max_steps": 4,
        "max_output_tokens": 100,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--architectures", nargs="+", default=["T1", "T2"])
    parser.add_argument("--runs-dir", default="runs/smoke")
    args = parser.parse_args()
    root = Path(args.runs_dir)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    results: list[dict[str, object]] = []
    for architecture in [item.upper() for item in args.architectures]:
        request = _request(root, architecture)
        if architecture == "T1":
            result = run_t1(
                request,
                completion=lambda prompt, settings: {
                    "text": "### FILE: py/main.py\nVALUE = 2\n",
                    "finish_reason": "smoke",
                    "usage": {},
                },
            )
        elif architecture == "T2":
            def runtime(req, prompt, tools):
                tools.write_candidate_file("py/main.py", "VALUE = 2\n")
                return {"final_answer": "smoke", "model_calls": 1, "tool_calls": 1, "trace": []}

            result = run_t2(request, runtime=runtime)
        else:
            raise SystemExit(f"no-network smoke supports T1 and T2 only: {architecture}")
        results.append(result)
    print(json.dumps([{"architecture_id": item["architecture_id"], "status": item["status"]} for item in results]))
    return int(any(item.get("status") != "completed" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
