"""Aggregate check-repair run artifacts into tables grouped like the on-disk tree."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def collect_records(runs_root: str | Path) -> list[dict[str, Any]]:
    root = Path(runs_root).resolve()
    records: list[dict[str, Any]] = []
    if not root.is_dir():
        return records
    for evaluation_path in sorted(root.rglob("evaluation.json")):
        if "_archive" in evaluation_path.relative_to(root).parts:
            continue
        run = evaluation_path.parent
        evaluation = _read(evaluation_path)
        manifest = _read(run / "manifest.json")
        task = _read(run / "input.json")
        result = _read(run / "run_result.json")
        status = str(manifest.get("status") or result.get("status") or "")
        if status not in {"completed", "failed"}:
            continue
        records.append(
            {
                "architecture_id": str(manifest.get("architecture_id") or ""),
                "bridge_type": str(task.get("bridge_type") or ""),
                "form": "check_repair",
                "result_tree": "/".join(run.relative_to(root).parts[:-1]),
                "status": status,
                "failure_code": str(manifest.get("failure_code") or result.get("failure_code") or ""),
                "task_id": str(task.get("task_id") or manifest.get("task_id") or ""),
                "localization_score": evaluation.get("localization_score"),
                "repair_pass": bool(evaluation.get("repair_pass")),
                "elapsed_s": float(manifest.get("elapsed_s") or 0.0),
                "run_dir": str(run),
            }
        )
    return records


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    architectures: dict[str, dict[str, Any]] = {}
    for architecture in sorted({str(record.get("architecture_id") or "") for record in records}):
        selected = [record for record in records if record.get("architecture_id") == architecture]
        n = len(selected)
        repaired = sum(bool(record.get("repair_pass")) for record in selected)
        architectures[architecture] = {
            "n": n,
            "repair_pass": repaired,
            "repair_rate": round(repaired / n, 6) if n else 0.0,
            "by_bridge": {},
        }
        for record in selected:
            bridge = str(record.get("bridge_type") or "unknown")
            slot = architectures[architecture]["by_bridge"].setdefault(
                bridge, {"n": 0, "repair_pass": 0}
            )
            slot["n"] += 1
            slot["repair_pass"] += int(bool(record.get("repair_pass")))
        for slot in architectures[architecture]["by_bridge"].values():
            slot["repair_rate"] = round(slot["repair_pass"] / slot["n"], 6) if slot["n"] else 0.0
    return {"n_records": len(records), "architectures": architectures}


def write_reports(output_dir: str | Path, records: list[dict[str, Any]]) -> dict[str, Path]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "summary.json"
    records_path = output / "records.csv"
    summary_path.write_text(
        json.dumps(summarize_records(records), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fields = [
        "architecture_id",
        "bridge_type",
        "form",
        "result_tree",
        "task_id",
        "status",
        "failure_code",
        "localization_score",
        "repair_pass",
        "elapsed_s",
        "run_dir",
    ]
    with records_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})
    return {"summary": summary_path, "records": records_path}
