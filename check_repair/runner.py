"""Trusted orchestration boundary for one formal check-repair run."""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from common.adapters import get_adapter
from common.manifest import sha256_file
from common.skill_adapter import SkillAdapter
from common.tool_policy import CandidateWorkspace

from .data import ExternalSample
from .sanitize import sanitize_for_model
from .score import score_localization, score_repair
from .verifier import NativeCheckVerifier, VerificationResult


class NativeEvaluator(Protocol):
    def evaluate(self, candidate_project: Path, post_out: Path | None) -> VerificationResult: ...


Generator = Callable[[dict[str, Any]], dict[str, Any]]


class RunFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value).strip()).strip(".-")
    if not safe:
        raise ValueError("run path segment is empty")
    return safe


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file()
    }


def _copy_seeded(source: Path, private_root: Path, candidate_root: Path) -> None:
    source_py = source / "py"
    if not source_py.is_dir():
        raise RunFailure("SEEDED_PROJECT_MISSING", "external seeded project has no py directory")
    shutil.copytree(source_py, private_root / "py", dirs_exist_ok=False)
    shutil.copytree(source_py, candidate_root / "py", dirs_exist_ok=False)


def dispatch_generation(request: dict[str, Any]) -> dict[str, Any]:
    architecture = str(request["architecture_id"]).upper()
    module_name = {
        "T1": "baselines.t1_direct.adapter",
        "T2": "baselines.t2_langgraph.adapter",
        "T3": "baselines.t3_smolagents.adapter",
        "T4": "baselines.t4_openhands.adapter",
        "T5": "baselines.t5_crewai.adapter",
        "T6": "baselines.t6_osisai.adapter",
    }[architecture]

    python_executable = (request.get("framework_pythons") or {}).get(architecture)
    if python_executable:
        request_path = Path(request["workspace"]) / "adapter_request.json"
        serializable = {key: value for key, value in request.items() if key != "framework_pythons"}
        _write_json(request_path, serializable)
        command = [str(python_executable), "-m", module_name, "--request", str(request_path)]
        completed = subprocess.run(
            command,
            cwd=str(Path(__file__).resolve().parents[1]),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(request.get("generation_timeout_s") or request["task"]["total_timeout_s"]),
        )
        if completed.returncode != 0:
            raise RunFailure("ADAPTER_PROCESS_FAILED", completed.stderr[-1000:])
        record = Path(request["workspace"]) / f"{architecture.lower()}_generation.json"
        if not record.is_file():
            raise RunFailure("ADAPTER_RECORD_MISSING", f"adapter did not write {record.name}")
        return json.loads(record.read_text(encoding="utf-8"))

    module = __import__(module_name, fromlist=["run_generation"])
    return module.run_generation(request)


@dataclass(slots=True)
class OSISNativeEvaluator:
    """Materialize a candidate into a dedicated OSIS scratch project."""

    osis_project: Path
    model_python: Path
    verifier: NativeCheckVerifier | None = None
    timeout_s: float = 1800.0

    def __post_init__(self) -> None:
        self.osis_project = Path(self.osis_project).resolve()
        self.model_python = Path(self.model_python).resolve()
        if not self.osis_project.is_dir():
            raise NotADirectoryError(self.osis_project)
        if not self.model_python.is_file():
            raise FileNotFoundError(self.model_python)

    def evaluate(self, candidate_project: Path, post_out: Path | None) -> VerificationResult:
        candidate_py = Path(candidate_project).resolve() / "py"
        if not candidate_py.is_dir():
            raise RunFailure("CANDIDATE_PY_MISSING", "candidate has no py directory")
        target_py = self.osis_project / "py"
        if target_py.exists():
            shutil.rmtree(target_py)
        shutil.copytree(candidate_py, target_py)
        entrypoint = target_py / "prep" / "main.py"
        if not entrypoint.is_file():
            entrypoint = target_py / "main.py"
        if not entrypoint.is_file():
            raise RunFailure("CANDIDATE_ENTRYPOINT_MISSING", "candidate has no runnable main.py")
        subprocess.run(
            [str(self.model_python), str(entrypoint)],
            cwd=str(entrypoint.parent),
            check=True,
            timeout=self.timeout_s,
        )
        try:
            from pyosis import OSISEngine
        except ImportError as exc:  # pragma: no cover - native environment only
            raise RuntimeError("pyosis is required for formal verification") from exc
        OSISEngine().solve(timeout=min(600.0, self.timeout_s))
        return (self.verifier or NativeCheckVerifier()).verify(self.osis_project, post_out=post_out)


class CheckRepairRunner:
    def __init__(
        self,
        *,
        runs_root: str | Path,
        skills_dir: str | Path,
        native_evaluator: NativeEvaluator,
        generator: Generator | None = None,
        parent_commit: str = "unknown",
        framework_pythons: Mapping[str, str | Path] | None = None,
        base_url: str = "",
    ) -> None:
        self.runs_root = Path(runs_root).resolve()
        self.skills_dir = Path(skills_dir).resolve()
        self.native_evaluator = native_evaluator
        self.generator = generator or dispatch_generation
        self.parent_commit = parent_commit
        self.framework_pythons = {
            key.upper(): str(Path(value).resolve()) for key, value in (framework_pythons or {}).items()
        }
        self.base_url = base_url

    def _run_dir(self, label: str, architecture: str, task_id: str, seed: int) -> Path:
        return (
            self.runs_root
            / _segment(label)
            / _segment(architecture.upper())
            / _segment(task_id)
            / f"seed-{int(seed)}"
        )

    def _skill_hash(self) -> str:
        return SkillAdapter(self.skills_dir).skill_bundle_hash() if self.skills_dir.is_dir() else "unavailable"

    def run(
        self,
        sample: ExternalSample,
        architecture_id: str,
        *,
        seed: int,
        model: str,
        label: str,
        variant: str = "",
        resume: bool = False,
        max_steps: int = 200,
        max_output_tokens: int = 0,
    ) -> dict[str, Any]:
        architecture = architecture_id.upper()
        spec = get_adapter(architecture)
        public_task = sample.to_public_task()
        private = sample.private_reference()
        run_dir = self._run_dir(label, architecture, public_task.task_id, seed)
        result_path = run_dir / "run_result.json"
        if resume and result_path.is_file():
            prior = json.loads(result_path.read_text(encoding="utf-8"))
            if prior.get("status") == "completed":
                return {**prior, "run_dir": str(run_dir), "resumed": True}

        if run_dir.exists():
            shutil.rmtree(run_dir)
        private_stage = run_dir / "private" / "seeded_project"
        candidate = run_dir / "candidate_project"
        run_dir.mkdir(parents=True)
        started = time.monotonic()
        random.seed(seed)
        manifest: dict[str, Any] = {
            "protocol_version": public_task.protocol_version,
            "task_id": public_task.task_id,
            "architecture_id": architecture,
            "framework": spec.framework,
            "framework_version": spec.framework_version,
            "model": model,
            "variant": variant,
            "seed": int(seed),
            "max_steps": int(max_steps),
            "max_output_tokens": int(max_output_tokens),
            "parent_commit": self.parent_commit,
            "skill_bundle_sha256": self._skill_hash(),
            "status": "running",
        }
        result: dict[str, Any] = {
            "status": "failed",
            "architecture_id": architecture,
            "task_id": public_task.task_id,
            "failure_code": None,
            "evaluation": {},
        }
        try:
            _copy_seeded(private.seeded_project, private_stage, candidate)
            if private.osis_post is not None:
                shutil.copy2(private.osis_post, private_stage / "OSISPost.out")
            _write_json(run_dir / "input.json", sanitize_for_model(public_task))
            before_hashes = _tree_hashes(candidate)

            seeded_check = self.native_evaluator.evaluate(candidate, private.osis_post)
            expected_ng = {name.strip() for name in private.ng_seeded if name.strip()}
            actual_ng = {name.strip() for name in seeded_check.ng_items if name.strip()}
            if actual_ng != expected_ng:
                raise RunFailure(
                    "SEEDED_NG_MISMATCH",
                    f"seeded NG mismatch: missing={sorted(expected_ng-actual_ng)}, unexpected={sorted(actual_ng-expected_ng)}",
                )

            request = {
                "architecture_id": architecture,
                "task": sanitize_for_model(public_task),
                "workspace": str(run_dir),
                "skills_dir": str(self.skills_dir),
                "model": model,
                "variant": variant,
                "base_url": self.base_url,
                "temperature": 0.0,
                "request_timeout_s": min(300.0, float(public_task.total_timeout_s)),
                "generation_timeout_s": float(public_task.total_timeout_s),
                "max_steps": int(max_steps),
                "max_output_tokens": int(max_output_tokens),
                "framework_pythons": self.framework_pythons,
            }
            generation = self.generator(request)
            _write_json(run_dir / "generation.json", generation)
            if generation.get("status") != "completed":
                raise RunFailure("GENERATION_FAILED", str(generation.get("error") or generation.get("status")))

            workspace = CandidateWorkspace(candidate)
            if not any(path.endswith(".py") for path in workspace.list_files()):
                raise RunFailure("CANDIDATE_EMPTY", "candidate contains no Python files")
            syntax_failures = workspace.compile_python()
            if syntax_failures:
                raise RunFailure("CANDIDATE_SYNTAX_ERROR", json.dumps(syntax_failures, ensure_ascii=False))

            repaired_check = self.native_evaluator.evaluate(candidate, private.osis_post)
            localization = score_localization(
                str(generation.get("final_answer") or ""),
                private.expected_reason_code,
            )
            repair = score_repair(repaired_check.ng_items, private.target_item, private.ng_seeded)
            evaluation = {**localization, **repair, "check_mode": repaired_check.check_mode}
            _write_json(run_dir / "evaluation.json", evaluation)
            manifest.update(
                status="completed",
                elapsed_s=round(time.monotonic() - started, 3),
                candidate_before_sha256=before_hashes,
                candidate_after_sha256=_tree_hashes(candidate),
                model_calls=int(generation.get("model_calls") or 0),
                tool_calls=int(generation.get("tool_calls") or 0),
            )
            result.update(status="completed", evaluation=evaluation)
        except RunFailure as exc:
            result.update(failure_code=exc.code, error=str(exc))
            manifest.update(status="failed", failure_code=exc.code, error=str(exc)[:800])
        except Exception as exc:  # noqa: BLE001
            result.update(failure_code="UNEXPECTED_ERROR", error=f"{type(exc).__name__}: {exc}"[:800])
            manifest.update(status="failed", failure_code="UNEXPECTED_ERROR", error=result["error"])
        finally:
            manifest.setdefault("elapsed_s", round(time.monotonic() - started, 3))
            _write_json(run_dir / "manifest.json", manifest)
            persisted = {**result, "manifest": "manifest.json"}
            _write_json(result_path, persisted)
        return {**result, "run_dir": str(run_dir), "resumed": False}
