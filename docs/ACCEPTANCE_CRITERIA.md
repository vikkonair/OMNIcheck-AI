# Acceptance Criteria

## Core pipeline

- One CLI command completes an end-to-end job
- Every input file appears in the internal inventory
- Every file has size, type, and SHA-256
- Unknown files are reported
- Exactly one Primary is confirmed
- OS evidence from all configured nodes is eligible
- Database evidence from Standby and DR is excluded
- Normalized JSON validates against a versioned schema

## Evidence and assessment

- Every assessment has visible Output
- PEM images replace duplicate text for the same metric, node, and time range
- PEM caption contains metric, node, and visible time period
- First health checks still evaluate current configuration risks
- Observations contain an explanation followed by a newline and `結論：`
- Recommendations are concise and actionable

## Fixed report policies

- No `資料來源`, raw filename, or storage path is rendered
- Last AutoVacuum and last AutoAnalyze history is absent
- Schema privilege evidence has at most 20 rows
- Rarely used index evidence has at most 20 rows
- Zero-scan indexes are ordered first
- Current `pg_hba.conf` is complete
- Current `postgresql.auto.conf` is complete
- Section 5.2 contains every non-normal finding
- CVE rows contain score, severity, CVSS version, vector, fixed version, and source

## Layout

- Cover contains customer and optional system name
- Cover contains `歐立威資料庫工程師 <name>` or `XXX`
- Every major section starts on a new page
- Small inspection units do not split across pages
- Long tables use controlled continuation and repeated headers
- Evidence and assessment grids align
- PEM image, caption, and assessment stay together
- Traditional Chinese glyphs render correctly in DOCX and PDF

## Reliability

- AI-disabled mode passes all core acceptance tests
- AI failures do not stop deterministic report generation
- Jiuxing golden dataset produces the approved V4 structure
- GlobalWafers golden dataset correctly uses PEM evidence
- Multi-node fixture proves that DR database evidence cannot enter the report
- Test output records parser, rule, schema, and report-template versions
