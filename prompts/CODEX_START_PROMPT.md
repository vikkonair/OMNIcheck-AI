# First Codex Task

Read `AGENTS.md`, `PROJECT_BRIEF.md`, `docs/PIPELINE_SPEC.md`,
`docs/ACCEPTANCE_CRITERIA.md`, and `config/job.example.yaml`.

Build milestone M1 only:

1. Scaffold a Python 3.12 project for `omni-healthcheck`
2. Add a CLI command named `omni-healthcheck generate`
3. Load and validate the job YAML
4. Recursively inventory an input directory
5. Record path, size, extension, preliminary category, and SHA-256
6. Write `inventory.json` into the output directory
7. Report unknown files without silently dropping them
8. Add unit tests and fixtures
9. Add a Dockerfile and minimal Docker Compose configuration

Do not implement report rendering, AI, the web UI, or Google Drive in this
milestone.

Before editing, inspect the repository and propose a short implementation plan.
After implementation, run the relevant tests and show the exact commands and
results. Do not claim completion if tests have not passed.
