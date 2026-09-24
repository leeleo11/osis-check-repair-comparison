# Release checklist

- Git status contains only intended public source and documentation.
- uv.lock was generated from pyproject.toml with Python 3.13 constraints.
- Clean uv sync completed for the test environment.
- Full pytest suite passed.
- T1 and T2 no-network public smoke completed.
- External new-protocol dry run found the expected seeded task count.
- Shared skill snapshot is a complete copy of the parent `.agents/skills` tree.
- Public boundary audit passed.
- git ls-files contains no runs, reports, data, datasets, seeded, private, candidate, native outputs, local config, credentials, or result artifacts.
- README commands match the verified commands.
- Remote repository contains source and lock file only; experiment inputs and outputs remain local.
