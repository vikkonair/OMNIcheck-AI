# Omni Health-check

Milestone M1 provides a deterministic command-line inventory pipeline for
PostgreSQL and EPAS health-check evidence.

## Local setup

Python 3.12 or newer is required.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/omni-healthcheck generate \
  --job config/job.example.yaml \
  --input ./input \
  --output ./output
```

The command validates the job configuration, inventories every regular file
under the input directory, calculates SHA-256 hashes, resolves configured node
identities, and writes:

- `output/inventory.json`
- `output/topology.json`
- `output/scope-ledger.json`
- `output/normalized.json`
- `output/configuration-comparison.json`
- `output/assessment.json`

Database evidence from Standby and DR nodes is explicitly excluded. Evidence
whose node or domain cannot be determined is retained as `pending` and reported
on stderr rather than silently allowed.

The node model separates infrastructure role from hosted service. A monitoring
node is configured with `role: Witness` and `services: [PEM, EFM]`. Its OS and PEM
monitoring evidence are eligible, while its PEM backend PostgreSQL evidence is
excluded from the inspected system's Primary-only database scope.

In the standard EDB architecture the Witness may host both PEM and EFM, so its
service list is normally `services: [PEM, EFM]`. EFM may also run as an agent on
Primary or Standby database nodes.

`normalized.json` uses the checked-in canonical schema version 1.0. M3 includes
the parser registry plus initial deterministic parsers for OS identity, OS and
kernel version, CPU count, total memory, total swap, and PostgreSQL/EPAS
version. Only evidence marked `allowed` by the scope ledger reaches parsers.

M4 expands deterministic parsing to OS storage, filesystems, processes,
networking, HugePages, SELinux, firewall, PEM/EFM status, backup configuration,
database inventory, connections, transaction age, extensions, roles,
privileges, SSL, replication, locks, bloat, partitioning, and index usage.
Embedded target-database configuration from Witness or PEM backend evidence is
rejected at the parser boundary. Last AutoVacuum and AutoAnalyze history is omitted, schema
privileges are capped at 20 rows, and rarely used indexes are ordered with
zero-scan rows first and capped at 20.

Database scope distinguishes logical database evidence from node-local
configuration. Logical objects and activity (databases, schemas, tables, roles,
extensions, transaction age, and bloat) use Primary evidence only.
`postgresql.conf`, `postgresql.auto.conf`, `pg_hba.conf`, and backup
configuration are collected from Primary, Standby, and DR nodes. Witness and
PEM-backend configuration remains outside the target cluster scope.
`configuration-comparison.json` records matching, different, and missing
parameters plus common and node-unique HBA rules without rendering source paths.

M5 adds the versioned deterministic rule engine. Thresholds and policy lists
live in `config/rules.default.yaml`; Python executes the rules and writes
`assessment.json`. Every assessment has visible evidence references, a versioned
rule ID, a deterministic status, an observation ending with an explicit
`結論：`, and a concise recommendation. AI is not used to select evidence,
change status, or create findings.

The initial rules cover filesystem usage, TxID age, idle transactions,
replication state, candidate bloat and index lists, backup errors, role and
schema privileges, cross-node configuration consistency, and non-local HBA
`trust`. Provisional thresholds and their report provenance are documented in
`docs/RULE_PROVENANCE.md`.

See `docs/MILESTONE_VALIDATION.md` for the required validation gate before a
milestone can be tagged as successful.

## Docker

```bash
docker compose run --rm omni-healthcheck generate \
  --job /app/config/job.example.yaml \
  --input /data/input \
  --output /data/output
```

Mount or replace the `input` and `output` directories configured in
`compose.yaml`.
