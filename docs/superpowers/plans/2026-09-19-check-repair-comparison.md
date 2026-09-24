# Check-repair Comparison Implementation Plan

当前实现以 [框架使用说明.md](../../框架使用说明.md) 为准。本文是建仓计划，其中 T6 隔离交接的步骤已经过时。

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans task by task.

**Goal:** Build a reproducible T1–T6 check-repair comparison repository whose real tasks, hidden seed data, native OSIS files, and experiment results remain external to Git.

**Architecture:** Reuse only the first line's framework entry patterns, skill reader, environment isolation, and manifest ideas. Put task sanitization, private seeded-project staging, NG verification, and scoring in a dedicated check_repair package; adapters receive only a public task object and a bounded candidate workspace.

**Tech Stack:** Python 3.13, uv, requests, httpx, PyYAML, pytest, LangGraph/LangChain, smolagents, OpenHands SDK, CrewAI, and the external parent repository's pyosis/OpenCode runtime.

## Global Constraints

- Never track real samples, seed fields, NG lists, seeded projects, OSISPost files, model responses, reports, logs, keys, databases, or native OSIS outputs.
- Model payloads contain only task_id, bridge_type, difficulty, natural_language_prompt, protocol_version, timeout, and safe metadata.
- T1–T6 share the same public task, skill snapshot, model, variant, budgets, candidate contract, verifier, and scorer.
- The common runner owns hidden references and formal NG verification.
- Verification rejects empty, NOFILE, and NOHEADER results.
- Local paths and all run, report, data, dataset, seeded, private, lcc, and OSIS output directories are ignored.

---

### Task 1: Public scaffold and boundary rules

**Files:**
- Create: .gitignore, .python-version, pyproject.toml
- Create: configs/parent_repo.example.txt and ignored configs/parent_repo.local.txt
- Create: common/__init__.py, check_repair/__init__.py, baselines/__init__.py
- Create: tasks/schema/check_repair_task.schema.json and tasks/smoke/check_repair_smoke.json
- Create: tests/conftest.py and tests/test_public_boundary.py

**Interfaces:**
- The smoke fixture contains exactly five public fields.
- The boundary test inspects tracked files and rejects native outputs, absolute machine paths, credentials, and hidden-data field names outside documentation and tests.

- [ ] Write failing smoke-schema and tracked-file boundary tests.
- [ ] Run uv run pytest -q tests/test_public_boundary.py and confirm missing-file failures.
- [ ] Add Python 3.13 project metadata, framework optional dependencies, ignore rules, example config, packages, schema, and sanitized smoke fixture.
- [ ] Run the focused tests and require all passing.
- [ ] Commit with message: chore: scaffold public check-repair repository.

### Task 2: Public task schema, external loader, and scorer

**Files:**
- Create: check_repair/schema.py, check_repair/data.py, check_repair/sanitize.py, check_repair/score.py
- Create: tests/test_check_repair_schema.py and tests/test_check_repair_score.py

**Interfaces:**
- CheckRepairTaskSpec.from_dict(data) and to_dict()
- load_external_samples(parent_repo, samples_path=None)
- ExternalSample.to_public_task() and private_reference()
- sanitize_for_model(task)
- extract_localizations(text)
- score_localization(text, expected_reason_code)
- score_repair(ng_after, target_item, ng_seeded)

- [ ] Test required fields, positive timeout, rejection of hidden keys, parent-path escape rejection, and sanitized serialization.
- [ ] Implement immutable public and private dataclasses.
- [ ] Load only external status=seeded rows; never write their private fields into source-tree files.
- [ ] Implement the new protocol: strip think blocks, scan JSON objects, keep the final localization, compare final reason_code, and require target removal with no new NG.
- [ ] Run focused tests and commit with message: feat: add sanitized check-repair contracts.

### Task 3: Fail-closed NG verifier

**Files:**
- Create: check_repair/ng.py and check_repair/verifier.py
- Create: tests/test_check_repair_ng.py and tests/test_check_repair_verifier.py

**Interfaces:**
- clear_check_results(project_root)
- parse_check_rows(project_root, run_command)
- require_complete(rows)
- item_names(rows, status="NG")
- NativeCheckVerifier.verify(project_root, post_out=None, rebuild=False)

- [ ] Test stale-file cleanup, OSISPost priority, CombinationAndCheck fallback, and incomplete-result rejection.
- [ ] Implement GBK tabular export parsing with the standard library and lazy pyosis imports.
- [ ] Implement post input plus CheckSolve, or check deletion plus CombinationAndCheck.
- [ ] Run tests without OSIS installed and commit with message: feat: add fail-closed check verifier.

### Task 4: Common framework substrate

**Files:**
- Create: common/paths.py, common/skill_adapter.py, common/tool_policy.py, common/manifest.py, common/protocol.py, common/adapters.py
- Create: baselines/_framework_common.py
- Create: tests/test_paths.py, tests/test_skill_adapter.py, tests/test_adapters.py

**Interfaces:**
- resolve_parent_repo(explicit=None)
- SkillAdapter.skill_index(), read_skill(), read_reference(), skill_bundle_hash()
- AdapterSpec, ADAPTER_SPECS, and get_adapter()
- artifact_hashes(run_dir)

- [ ] Test parent resolution precedence, traversal rejection, deterministic skill hash, and six-architecture registration.
- [ ] Implement portable parent lookup and bounded snapshot reads.
- [ ] Implement common candidate tools and the shared check-repair prompt.
- [ ] Run focused tests and commit with message: feat: add common framework substrate.

### Task 5: Framework-specific T1 through T5 adapters

**Files:**
- Create: baselines/t1_direct/adapter.py
- Create: baselines/t2_langgraph/adapter.py
- Create: baselines/t3_smolagents/adapter.py
- Create: baselines/t4_openhands/adapter.py
- Create: baselines/t5_crewai/adapter.py
- Create: tests/test_t1_adapter.py through tests/test_t5_adapter.py

**Interfaces:**
- Every adapter exports run_generation(request) and writes tN_generation.json.
- T1 performs one request.
- T2 uses LangGraph create_agent and stream.
- T3 uses smolagents CodeAgent.
- T4 uses OpenHands AgentContext, native skill invocation, and Conversation.
- T5 uses diagnoser, repairer, and verifier roles; verifier has no write tool.

- [ ] Write fake-SDK identity, metadata, and path-escape tests.
- [ ] Implement T1 one-shot file-block output.
- [ ] Implement T2 message/tool streaming and transcript capture.
- [ ] Implement T3 CodeAct with bounded candidate operations.
- [ ] Implement T4 native progressive skill loading with a concise task hand-off.
- [ ] Implement T5 sequential context with enforced role tool boundaries.
- [ ] Run adapter tests and commit with message: feat: add T1-T5 check-repair adapters.

### Task 6: T6, unified runner, and campaign CLI

**Files:**
- Create: baselines/t6_osisai/adapter.py
- Create: check_repair/runner.py
- Create: scripts/run_dataset.py and scripts/run_campaign.py
- Create: tests/test_check_repair_runner.py and tests/test_run_campaign.py

**Interfaces:**
- CheckRepairRunner.run(task, architecture_id, seed, ...)
- run_dataset supports architecture, task id, parent repo, smoke, and runs directory.
- run_campaign supports labels, IDs, architectures, resume, jobs, and a serial T6 lane.

- [ ] Test private staging, candidate gates, fake generation, fake verification, scoring, manifest creation, and resume behavior.
- [ ] Implement staging of only the external seeded py tree into an ignored run.
- [ ] Dispatch T1/T2 in the main environment, T3/T4/T5 in framework venvs, and T6 in the parent venv.
- [ ] Implement T6 isolated native hand-off without private data in its prompt.
- [ ] Write evaluation, trace, failure codes, and parent commit identifiers without absolute paths.
- [ ] Run focused tests and commit with message: feat: add unified six-framework runner.

### Task 7: Reproduction tools and documentation

**Files:**
- Create: scripts/setup_framework_envs.py, scripts/export_repro_workspace.py, scripts/audit_public_boundary.py
- Create: README.md, REPRODUCIBILITY.md, ENVIRONMENT.md, baselines/README.md
- Create: docs/框架使用说明.md and docs/数据边界与发布审计.md
- Create: tests/test_public_audit.py and tests/test_export_repro_workspace.py

**Interfaces:**
- audit_public_boundary exits nonzero and lists relative paths for violations.
- export_repro_workspace copies only public source and creates an ignored local parent config.

- [ ] Test audit violations and export exclusions.
- [ ] Implement tracked-file audit and an explicit export ignore list.
- [ ] Document uv setup, two Python environments, external OSIS/OpenCode, parent commit pinning, smoke, formal execution, and no-data/no-results publishing.
- [ ] Run tests and audit, then commit with message: docs: add reproducibility and release audit.

### Task 8: Full verification

**Files:**
- Create: docs/release-checklist.md
- Modify: README.md only if verified commands differ

- [ ] Run uv lock.
- [ ] Run uv sync --python 3.13.
- [ ] Run uv run pytest -q.
- [ ] Run no-network smoke for T1 and T2 under ignored runs/smoke.
- [ ] Run the public audit and verify Git tracks no result/data/native-output paths.
- [ ] Commit with message: chore: verify reproducible public release.
