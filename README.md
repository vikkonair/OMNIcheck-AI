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

Database evidence from Standby and DR nodes is explicitly excluded. Evidence
whose node or domain cannot be determined is retained as `pending` and reported
on stderr rather than silently allowed.

## Docker

```bash
docker compose run --rm omni-healthcheck generate \
  --job /app/config/job.example.yaml \
  --input /data/input \
  --output /data/output
```

Mount or replace the `input` and `output` directories configured in
`compose.yaml`.
