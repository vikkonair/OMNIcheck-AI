# M5 Rule Provenance

The deterministic ruleset is informed by approved report examples but remains
configuration-driven and versioned.

## Corroborated report patterns

- Filesystem usage observed at 22% to 65% was reported as normal.
- TxID age near 200 million was reported within the normal range.
- Rarely used indexes require workload confirmation before removal.
- Table and index bloat candidates require maintenance-window validation before
  VACUUM FULL or REINDEX.
- Role and privilege findings require explicit review when elevated capability
  is not clearly part of the approved baseline.
- Non-local HBA `trust` rules should be reviewed and preferably replaced with
  `scram-sha-256`.
- `primary_conninfo` is an expected role-specific cross-node difference.
- Missing or different non-role-specific parameters require confirmation.

## Approved filesystem and list policies

- Filesystem usage below 50% is normal monitoring.
- Filesystem usage from 50% through less than 70% remains normal, but the
  recommendation must explicitly ask the engineer to watch volume growth.
- Filesystem usage at 70% or above is `attention`.
- Table and index bloat Output preserves the collected top 10 rows. The
  deterministic and AI observation/recommendation must enumerate every object
  within those 10 rows whose bloat indicator is greater than 2. Table objects
  map to `VACUUM FULL`; index objects map to `REINDEX`.
- Rarely used indexes sort `idx_scan = 0` first and render at most 10 rows.
- PostgreSQL predefined `pg_*` roles and bootstrap roles `postgres` and
  `enterprisedb` are omitted from role and schema privilege output.

The AI contract must preserve every listed object and its maintenance action.
If an AI response omits any object or action, the Gateway rejects it and retains
the deterministic fallback.

## Provisional configurable thresholds

The following defaults are conservative engineering defaults, not proven
Omniware policy:

- TxID warning: 1,000,000,000
- TxID critical: 1,500,000,000

They are stored in `config/rules.default.yaml` and can be changed without code
changes. The milestone report must label them provisional until DBA approval.
