# Report JSON schema

`scripts/build_report.py` consumes UTF-8 JSON with this shape:

```json
{
  "customer": "Example Customer",
  "system_name": "db01",
  "period": "2026上半年",
  "report_date": "2026-07-16",
  "engineer_name": "王小明",
  "database_source_hostname": "db01",
  "product": {"name": "PostgreSQL", "version": "15.17"},
  "maintenance_period": "2026-01-01～2026-06-30",
  "purpose": ["確保資料庫系統正常運行", "確認備份與維運機制"],
  "nodes": [
    {
      "hostname": "db01",
      "role": "Primary",
      "os": "RHEL 8.10",
      "database": "PostgreSQL 15.17",
      "cpu": "8 cores",
      "ram": "64 GB",
      "service_ip": "10.0.0.10",
      "components": ["custom backup"]
    }
  ],
  "architecture_image": null,
  "chapters": [
    {
      "number": "3",
      "title": "作業系統健檢",
      "sections": [
        {
          "number": "3.1",
          "title": "組態設定檢查",
          "items": [
            {
              "title": "HugePage",
              "node": "db01",
              "evidence": {
                "type": "table",
                "headers": ["項目", "值"],
                "rows": [["HugePages_Total", "0"], ["Hugepagesize", "2048 kB"]]
              },
              "status": "待確認",
              "observation": "HugePages_Total 為 0。",
              "impact": "是否需要 HugePages 取決於記憶體配置與工作負載。",
              "recommendation": "比對 shared_buffers、THP 與 OS 記憶體規劃後確認。"
            }
          ]
        }
      ]
    }
  ],
  "version_updates": [
    {
      "current": "15.17",
      "recommended": "15.18",
      "summary": "Review the applicable PostgreSQL release fixes.",
      "cves": [
        {
          "id": "CVE-YYYY-NNNN",
          "cvss_score": "8.1",
          "severity": "HIGH",
          "cvss_version": "CVSS 3.1",
          "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H",
          "score_source": "NVD",
          "summary": "Concise fix description."
        }
      ]
    }
  ],
  "summary": [
    {"status": "待確認", "item": "HugePage", "finding": "HugePages_Total=0", "recommendation": "確認記憶體規劃", "reference": "3.1"}
  ]
}
```

The internal environment manifest must retain every OS raw input path and Primary database input path, plus the filenames/paths of DR/Standby database inputs marked as excluded without reading their contents. These paths do not appear in the customer-facing report. For HA/DR, set `database_source_hostname` to the one current Primary and set every database chapter item to that same node. Use per-node items only for OS-derived evidence. The builder rejects database items assigned to DR/Standby. For a standalone system, set the standalone hostname as `database_source_hostname`.

Evidence types:

- `text`: `content` string
- `table`: `headers` and `rows`
- `image`: absolute local `path`, optional `caption`, and optional `width_cm` between 8 and 16.2

Use `image` when a current PEM or equivalent monitoring screenshot clearly represents the reported metric. The image is the visible Output, not decoration. The caption must identify the metric, node, and visible time window without exposing a raw filename or path. Do not add a duplicate text Output for the same node, metric, and time window.

Optional `paragraphs` may appear on chapters or sections. Omit empty sections instead of creating placeholders.

Do not include `source`, `資料來源`, raw filenames, or Drive paths in customer-facing report JSON fields. Keep source traceability only in the separate internal coverage ledger.

The builder applies these fixed scope rules defensively:

- items/sections titled as `最後 AutoVacuum` or `最後 AutoAnalyze` history are not rendered;
- schema-privilege table evidence is limited to its first 20 data rows;
- rarely-used-index table evidence is stably reordered with `Scan`/`idx_scan`/`Index scan = 0` rows first and limited to 20 total rows;
- every remaining item must contain non-empty visible evidence/Output before its assessment.

Rarely-used-index evidence must expose a recognizable scan-count header such as `Scan`, `idx_scan`, `Index scan`, or `索引掃描次數`. The builder rejects the item if it cannot identify that column, preventing an arbitrary first-20 truncation from displacing zero-scan indexes.

`summary` is optional supplemental input, not the authoritative content of section 5.2. The builder scans every chapter/section/item and automatically creates a 5.2 row for every status other than `正常`, including node names for repeated host-level items. It also creates the version-update row when a newer recommended minor version exists. An explicit summary row is retained only when its referenced section is not already covered, preventing duplicates while ensuring no non-normal assessment is omitted.

Generated narrative fields must not end with `。` or `.`. The builder removes terminal sentence periods and changes internal Chinese full stops to semicolons when rendering prose. Evidence fields remain untouched so versions, IP addresses, filenames, SQL, logs, and configuration Output preserve their original punctuation.

`engineer_name` is optional. Use the current user's supplied name when present; when absent or blank, the builder automatically renders the exact cover string `歐立威資料庫工程師 XXX` and continues so the user can replace it during review. Never populate it from a previous report's personnel field.

When a newer minor patch exists in the same major version, populate `version_updates[].cves` with every distinct CVE identified in the official release notes. Every CVE object must include `cvss_score`, `severity`, `cvss_version`, `vector`, and `score_source`. Prefer NVD CVSS v3.1; otherwise use and name an authoritative CNA/vendor source. Use `未公布／待確認` for any authoritative value that is not published, never an estimate. Omit `cves` when no newer minor patch exists.

All statuses must be one of the six values defined in `assessment-rules.md`.
