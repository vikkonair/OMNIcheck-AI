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
under the input directory, calculates SHA-256 hashes, and writes
`output/inventory.json`. Unknown files remain in the inventory and are also
reported on stderr.

## Docker

```bash
docker compose run --rm omni-healthcheck generate \
  --job /app/config/job.example.yaml \
  --input /data/input \
  --output /data/output
```

Mount or replace the `input` and `output` directories configured in
`compose.yaml`.

