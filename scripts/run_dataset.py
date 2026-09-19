"""Run one architecture against external seeded samples."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from check_repair.data import load_external_samples
from check_repair.runner import CheckRepairRunner, OSISNativeEvaluator
from common.paths import resolve_parent_repo, resolve_run_root


def _commit(parent: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=parent, text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    parser.add_argument("--samples")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--architecture", required=True, choices=[f"T{i}" for i in range(1, 7)])
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--osis-project")
    parser.add_argument("--osis-model-python")
    parser.add_argument("--runs-dir")
    parser.add_argument("--model", default="deepseek-v4.1-flash-expires-on-0910")
    parser.add_argument("--variant", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--label", default="formal")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parent = resolve_parent_repo(args.parent_repo)
    samples = load_external_samples(parent, args.samples)
    if args.task_id:
        selected = set(args.task_id)
        samples = [sample for sample in samples if sample.task_id in selected]
    if args.dry_run:
        print(json.dumps({"seeded_samples": len(samples), "ids": [sample.task_id for sample in samples]}))
        return 0
    if not args.osis_project or not args.osis_model_python:
        raise SystemExit("formal execution requires --osis-project and --osis-model-python")
    runner = CheckRepairRunner(
        runs_root=resolve_run_root(args.runs_dir),
        skills_dir=Path(args.skills_dir),
        native_evaluator=OSISNativeEvaluator(Path(args.osis_project), Path(args.osis_model_python)),
        parent_commit=_commit(parent),
        base_url=args.base_url,
    )
    results = [
        runner.run(
            sample,
            args.architecture,
            seed=args.seed,
            model=args.model,
            label=args.label,
            variant=args.variant,
            resume=args.resume,
        )
        for sample in samples
    ]
    print(json.dumps({"completed": sum(r["status"] == "completed" for r in results), "total": len(results)}))
    return int(any(result["status"] != "completed" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
