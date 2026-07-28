# M6 Validation Report

## Scope

M6 adds deterministic coverage accounting and delivery quality gates. It writes
`coverage-ledger.json` and `qa-result.json`, and blocks successful delivery when
a mandatory gate fails.

## Automated verification

- Tests: 26 passed
- Statement/branch coverage: 86%
- Missing Primary database evidence is a tested failure path.
- Unmasked secret detection is a tested failure path.
- Missing non-critical coverage remains visible without blocking the job.
- A sanitized multi-node Primary/Standby/DR/Witness fixture passes all gates.

## Read-only collected-data verification

Dataset:
`/Users/omniwaresoft/Documents/台灣行動支付健檢資料/20260616 (1)`

All generated output and the temporary job configuration remained under
`/tmp`. No collected evidence was written or committed.

- Source files: 14
- Source size and SHA-256 comparison before/after: identical
- Delivery QA: passed
- Quality gates: 8 passed, 0 failed
- Invalid assessment evidence references: 0
- Unmasked secret matches: 0
- Source path mentions in assessments: 0
- Foreign configured nodes: 0
- Coverage: 44 / 76 expected items (57.9%)
- Assessments: 11 normal, 8 attention, 0 critical, 2 pending
- Scope pending: 6 (`.DS_Store` and five monitoring images without unique node mapping)
- Unknown files: 1 (`.DS_Store`)

The missing 32 coverage items are retained explicitly in the coverage ledger.
They do not represent parser failures and are not silently treated as present.

## Result

M6 validation passed. The pending image-to-node mapping remains visible and is
allowed by policy until the image-processing/report milestone.
