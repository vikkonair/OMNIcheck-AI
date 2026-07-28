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

## Provisional configurable thresholds

The following defaults are conservative engineering defaults, not proven
Omniware policy:

- Filesystem warning: 80%
- Filesystem critical: 90%
- TxID warning: 1,000,000,000
- TxID critical: 1,500,000,000

They are stored in `config/rules.default.yaml` and can be changed without code
changes. The milestone report must label them provisional until DBA approval.
