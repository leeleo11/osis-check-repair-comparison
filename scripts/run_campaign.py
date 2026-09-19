"""Campaign scheduler with a dedicated serial lane for T6."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

from check_repair.data import load_external_samples
from check_repair.runner import CheckRepairRunner, OSISNativeEvaluator
from common.paths import resolve_parent_repo, resolve_run_root


def campaign_order(architectures: Iterable[str]) -> tuple[list[str], list[str]]:
    normalized = sorted({str(item).upper() for item in architectures})
    return [item for item in normalized if item != "T6"], [item for item in normalized if item == "T6"]


def run_campaign(
    *,
    runner: Any,
    samples: list[Any],
    architectures: list[str],
    seed: int,
    model: str,
    label: str,
    variant: str = "",
    resume: bool = False,
    jobs: int = 1,
) -> list[dict[str, Any]]:
    parallel, serial = campaign_order(architectures)
    results: list[dict[str, Any]] = []

    def one(sample: Any, architecture: str) -> dict[str, Any]:
        return runner.run(
            sample,
            architecture,
            seed=seed,
            model=model,
            label=label,
            variant=variant,
            resume=resume,
        )

    work = [(sample, architecture) for architecture in parallel for sample in samples]
    if jobs > 1 and work:
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = [executor.submit(one, sample, architecture) for sample, architecture in work]
            for future in as_completed(futures):
                results.append(future.result())
    else:
        results.extend(one(sample, architecture) for sample, architecture in work)

    # Native OpenCode/OSIS state is process-global. T6 is always serialized.
    for architecture in serial:
        for sample in samples:
            results.append(one(sample, architecture))
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-repo")
    parser.add_argument("--samples")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--architectures", nargs="+", default=[f"T{i}" for i in range(1, 7)])
    parser.add_argument("--skills-dir", required=True)
    parser.add_argument("--osis-project", required=True)
    parser.add_argument("--osis-model-python", required=True)
    parser.add_argument("--runs-dir")
    parser.add_argument("--model", required=True)
    parser.add_argument("--variant", default="")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--label", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    parent = resolve_parent_repo(args.parent_repo)
    samples = load_external_samples(parent, args.samples)
    if args.task_id:
        selected = set(args.task_id)
        samples = [sample for sample in samples if sample.task_id in selected]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=parent, text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unknown"
    runner = CheckRepairRunner(
        runs_root=resolve_run_root(args.runs_dir),
        skills_dir=Path(args.skills_dir),
        native_evaluator=OSISNativeEvaluator(Path(args.osis_project), Path(args.osis_model_python)),
        parent_commit=commit,
        base_url=args.base_url,
    )
    results = run_campaign(
        runner=runner,
        samples=samples,
        architectures=args.architectures,
        seed=args.seed,
        model=args.model,
        label=args.label,
        variant=args.variant,
        resume=args.resume,
        jobs=max(1, args.jobs),
    )
    print(json.dumps({"completed": sum(item["status"] == "completed" for item in results), "total": len(results)}))
    return int(any(item["status"] != "completed" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
