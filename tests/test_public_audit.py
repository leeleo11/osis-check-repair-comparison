from __future__ import annotations

from pathlib import Path

from scripts.audit_public_boundary import audit_paths


def test_audit_reports_private_artifacts_secrets_paths_and_payloads(tmp_path: Path) -> None:
    files = {
        "runs/result.json": "{}",
        "native/check.lcc": "binary-ish",
        "tasks/bad.json": '{"seed":{"reason_code":"answer"},"ng_seeded":["x"]}',
        "config.txt": "C:\\Users\\person\\private",
        "secret.txt": "token = sk-example-secret-value-1234567890",
    }
    paths: list[Path] = []
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        paths.append(path)

    violations = audit_paths(tmp_path, paths)
    rules = {item.rule for item in violations}
    assert {"private-path", "native-output", "hidden-json", "machine-path", "credential"} <= rules


def test_current_repository_passes_public_audit(repo_root: Path) -> None:
    from scripts.audit_public_boundary import tracked_paths

    assert audit_paths(repo_root, tracked_paths(repo_root)) == []
