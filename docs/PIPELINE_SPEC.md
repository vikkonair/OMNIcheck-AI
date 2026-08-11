# Pipeline Specification

## Stages

| Stage | Responsible component | Inputs | Outputs | Purpose |
|---|---|---|---|---|
| Job creation | Job service | Customer, period, product, engineer, options | Job record | Isolate each health-check run |
| Ingestion | Ingestion service | Text, SQL output, images, prior reports | Immutable raw files | Preserve evidence |
| Inventory | Inventory service | Raw files | File manifest and SHA-256 | Detect duplicates and unknown files |
| Classification | Evidence classifier | Manifest and sampled content | Evidence categories | Separate OS, DB, images and documents |
| Node resolution | Node resolver | Hostname, IP, paths, output content | Node registry | Identify distinct systems |
| Role resolution | Topology resolver | Recovery state, replication, EFM, operator overrides | Primary/Standby/DR topology | Establish authoritative roles |
| Scope control | Scope controller | Topology and classified evidence | Allowed/excluded evidence | Enforce all-OS and Primary-only DB |
| Parsing | Parser engine | Allowed text evidence | Structured check results | Remove model dependency from extraction |
| Image mapping | Image processor | PEM/monitoring images | Image evidence metadata | Map metric, node and time window |
| Normalization | Normalizer | Parsed checks and images | Versioned canonical JSON | Decouple analysis from rendering |
| Secret filtering | Security filter | Raw and normalized data | Redacted analysis data | Protect credentials and tokens |
| Coverage validation | Coverage validator | Expected checks and evidence | Coverage ledger | Ensure every assessment has Output |
| Historical comparison | Comparison engine | Current and prior normalized snapshots | Added/removed/changed values | Support recurring health checks |
| Assessment | Rule engine | Normalized evidence and comparisons | Status, observation and recommendation | Produce deterministic findings |
| Section workflow | Section workflow builder | Deterministic assessments | Versioned template, AI draft, review and approval contract | Keep AI text separate and fail closed |
| Version/CVE | CVE service | Product and installed version | Patch and CVE records | Populate section 5.1 |
| AI enrichment | Optional AI gateway | Redacted evidence and rule result | Optional prose refinement | Improve ambiguous or complex explanations |
| Report assembly | Report assembler | Evidence and assessments | Report model | Build ordered report content |
| Diagram generation | Diagram service | Topology | SVG/PNG | Create section 2.2 |
| DOCX rendering | DOCX renderer | Report model and V4 assets | DOCX | Produce editable customer report |
| PDF rendering | PDF renderer | DOCX | PDF | Produce distributable report |
| Content QA | QA engine | Report model and files | QA result | Detect scope and content violations |
| Visual QA | Render inspection | PDF page images | Page findings | Detect splits, overflow and missing glyphs |
| Review | Review UI or CLI approval | Draft report and QA | Approved version | Keep DBA accountable for delivery |
| Publishing | Publishing service | Approved files | Download, NAS or optional Drive copy | Deliver and archive reports |

## Canonical data contract

Every check result must contain:

```json
{
  "schema_version": "1.0",
  "check_id": "transaction_id_age",
  "section_id": "3.4",
  "node": "db-primary",
  "node_role": "Primary",
  "product": "PostgreSQL",
  "collected_at": "2026-07-08T10:00:00+08:00",
  "evidence": {
    "type": "table",
    "headers": ["Database", "Age"],
    "rows": [["appdb", "12034567"]]
  },
  "assessment": null,
  "trace": {
    "parser_id": "postgresql.txid.v1",
    "rule_id": null
  }
}
```

Trace metadata is internal and must not appear in the customer report.

## Required parsers for MVP

### OS

- Hostname and IP
- OS and kernel version
- CPU
- Memory and swap
- Filesystem and disk usage
- PostgreSQL/EPAS process state
- Network listeners
- Kernel and THP settings

### PostgreSQL and EPAS

- Product and version
- Recovery/Primary role
- Database inventory
- Connections
- Transaction ID age
- Database size
- Extensions
- Roles and privileges
- Schema privileges
- `pg_hba.conf`
- `postgresql.auto.conf`
- Bloat
- Rarely used indexes
- Replication state when collected from Primary

## Required execution gates

Stop the job when:

- no Primary is confirmed
- more than one Primary remains
- Primary database evidence is missing
- an assessment lacks visible evidence
- customer data appears mixed
- secret filtering cannot safely complete
- DOCX or PDF generation fails

Continue with `待確認` when:

- a non-critical check is missing
- a PEM image has an incomplete period
- image node identity is ambiguous
- topology labels are incomplete
- CVSS has not been authoritatively published
- there is no prior baseline
- optional AI is unavailable

## AI boundary

AI may draft observation and recommendation prose or suggest a label for
previously unknown evidence. Suggestions never alter topology or scope without
deterministic validation and operator confirmation. AI cannot:

- select the Primary
- alter scope
- invent measurements
- replace visible Output
- change thresholds
- alter report layout
- publish a report without deterministic QA
