# Report Reference Policy

## Content and rule provenance

- The Taiwan Mobile Payment legacy report is a content-only reference for
  section findings, conclusions, and recommendations. Its page design and
  layout must not be copied.
- The approved Jiuxing and GlobalWafers reports are references for section
  content and the preferred V4 report direction.
- Rules inferred from a single report remain provisional until confirmed by a
  DBA or corroborated by additional approved reports.
- AI must not turn an inferred threshold into an authoritative rule.

## CVE layout baseline

The GlobalWafers 2026 H1 report is the required section 5.1 CVE layout baseline:

1. Version summary table with current version, recommended version, and summary.
2. A `可修正 CVE 清單` table.
3. CVE columns for CVE ID, fixed version, CVSS information, and remediation
   summary.
4. CVSS cell includes numeric score, severity, and CVSS version.
5. Continuation pages repeat the CVE table header.

The final product rules additionally require authoritative source and CVSS
vector fields even when those fields were absent from the visual reference.
