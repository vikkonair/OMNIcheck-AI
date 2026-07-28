# Omniware On-premises Database Health-check Pipeline

## Objective

Create an internal application where a DBA creates a health-check job, uploads
OS outputs, Primary database outputs, PEM/monitoring screenshots, and optional
prior-period evidence, then receives a reviewed Omniware-format Word and PDF
report.

The system must continue to work when AI is disabled.

## Target users

- Omniware DBA engineers
- DBA reviewers
- Administrators who maintain thresholds, templates, and customer overrides

## MVP

The first usable version must:

1. Run locally from a CLI
2. Accept the existing PostgreSQL and EPAS health-check output formats
3. Inventory and hash all input files
4. Resolve nodes and require confirmation of one Primary
5. Include all OS nodes and only Primary database evidence
6. Parse common OS, PostgreSQL, and EPAS checks into versioned JSON
7. Use PEM screenshots as formal Output when applicable
8. Apply deterministic health-check rules without AI
9. Generate Jiuxing V4-style DOCX and PDF reports
10. Validate report coverage, content, and basic visual integrity
11. Save normalized data for future comparisons

## Out of scope for the first milestone

- Greenplum
- Automatic Google Drive synchronization
- Fully automatic OCR-dependent image interpretation
- Local LLM deployment
- Multi-tenant customer access
- Advanced approval workflows

## Success definition

Given the approved Jiuxing or GlobalWafers fixture set, one command produces:

- `inventory.json`
- `topology.json`
- `normalized.json`
- `coverage-ledger.json`
- `assessment.json`
- `report.docx`
- `report.pdf`
- `qa-result.json`

The output must comply with every rule in `AGENTS.md`.

## Recommended first command

```bash
omni-healthcheck generate \
  --job config/job.example.yaml \
  --input ./input \
  --output ./output
```
