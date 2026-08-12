# Omni Health-check Pipeline — Codex Instructions

## Goal

Build an on-premises data pipeline that converts PostgreSQL and EDB health-check
inputs into Omniware-format DOCX and PDF reports without requiring ChatGPT.
AI must remain optional and replaceable.

## Product rules

- Use the approved sanitized Jiuxing Holdings 2026 H1 V4 report as the primary
  visual baseline.
- Include OS evidence from every in-scope node.
- Include database evidence only from the current Primary.
- Never use Standby or DR database evidence in assessments or reports.
- Treat matching PEM or monitoring screenshots as formal Output for CPU, memory,
  process, disk, commit/rollback, transaction, and similar trends.
- Do not duplicate text Output when an image covers the same metric, node, and
  time window.
- Every reported assessment must have visible Output.
- Never display source filenames, Drive paths, or a data-source field.
- Omit last AutoVacuum and last AutoAnalyze history.
- Limit schema privilege rows to 20.
- Prioritize `idx_scan = 0` and limit rarely used indexes to 10 rows.
- Render complete current `pg_hba.conf` and `postgresql.auto.conf` inventories.
- A first health check still assesses current security and configuration risks.
- Put every non-normal result in section 5.2.
- Section 5.1 must include CVE ID, fixed version, CVSS score, severity, CVSS
  version, vector, and authoritative source.
- Render `歐立威資料庫工程師 <name>`; use `XXX` when the name is absent.
- Start each major section on a new page.
- Keep a small section's heading, Output, status, observation, and recommendation
  together. Use controlled continuation for long tables.
- Observations must briefly explain the evidence, then use a newline before an
  explicit `結論：...`.
- Recommendations must be concise and actionable.

## Engineering principles

- Implement deterministic parsing, scope control, assessment rules, report
  assembly, and QA before adding AI.
- AI must not select the Primary, alter evidence scope, invent findings, remove
  Output, or change report layout.
- Use a versioned canonical JSON schema between parsers and renderers.
- Keep thresholds and customer overrides in YAML or JSON configuration.
- Preserve immutable raw input and record SHA-256 hashes.
- Mask secrets before any external AI call.
- Fail closed when Primary identity is ambiguous or an assessment has no Output.
- Every parser and rule needs fixtures and automated tests.
- Use golden datasets for Jiuxing, GlobalWafers, and a multi-node Primary/Standby/DR case.
- Keep code changes focused, run relevant tests, and report verification results.
- Treat `docs/PROJECT_RUNBOOK.md` as a living project record. Update it whenever
  a milestone starts, completes validation, merges to `main`, receives a tag,
  changes deployment assumptions, or adds a known limitation or rollback step.
- Treat `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.md` as the authoritative
  rebuild and operations manual. Any dependency, package, environment variable,
  migration, service, directory, network, backup, validation, upgrade, or
  rollback change must update the Markdown source, regenerate the DOCX with
  `scripts/build_operations_guide.py`, and pass page-by-page render inspection
  in the same change. Never mark an unexecuted environment step as verified.

## Proposed stack

- Python 3.12
- FastAPI
- PostgreSQL metadata database
- Celery or an equivalent job worker
- Redis for the queue
- Local filesystem initially; optional MinIO later
- `python-docx` for DOCX
- LibreOffice headless for PDF
- Pillow and optional OCR for monitoring images
- Docker Compose for on-premises deployment

## Development order

1. Repository skeleton and configuration
2. CLI job runner
3. File inventory and hashing
4. Node and Primary role resolution
5. Primary-only scope controller
6. Parser framework and canonical schema
7. Deterministic rule engine
8. Coverage and security validation
9. V4 DOCX/PDF renderer
10. Golden tests for Jiuxing and GlobalWafers
11. Web UI and background worker
12. Historical comparison
13. CVE cache
14. Optional AI gateway

Read `docs/PIPELINE_SPEC.md` and `docs/ACCEPTANCE_CRITERIA.md` before
implementation. Begin with the task in `prompts/CODEX_START_PROMPT.md`.
