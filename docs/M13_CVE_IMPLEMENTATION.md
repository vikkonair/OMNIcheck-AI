# M13 CVE Cache、Version Matcher 與 V4 報告

狀態：開發中（2026-08-12）

## 固定責任邊界

- CVE／Release 資料只可由 PostgreSQL 官方 Security、EDB Security Advisories 與 NVD 補充來源進入 Cache；來源 key 不在政策中即拒絕匯入。
- 報告執行時不得上網；Worker 只讀取 EDB 內已保存的來源快照。
- Product、Installed Version、CVE ID、CVSS、Fixed Version 與 Match Status 均由確定性程式產生，AI 不可改寫。
- 原始客戶資料仍在 `/data`；CVE Cache、match 與快照 metadata 在 EDB。

## M13.1：Cache Sync

既有 company migration `0006_m13`／`0007_m13_catalog` 已提供 `cve_sources`、`cve_sync_runs`、`product_releases`、`cve_entries`、`cve_product_impacts`、`job_product_versions` 與 `job_cve_matches`。本階段新增可重複執行的 `omni-healthcheck-cve-import` 入口：輸入是已下載、已驗證的 JSON snapshot，匯入時記錄 source、hash、sync run、擷取時間與資料筆數。

PostgreSQL release catalog 可直接由固定官方端點同步；下載內容可另存為不可變快照，供稽核與重現：

```bash
omni-healthcheck-cve-import --sync-postgresql-releases \
  --snapshot-output /data/omnicheck/archive/cve/postgresql-releases-$(date +%F).json
```

匯入 JSON 格式：

```json
{
  "product_id": "epas",
  "source_key": "edb_security",
  "releases": [{"version": "15.8", "source_url": "https://..."}],
  "cves": [{"cve_id": "CVE-YYYY-NNNN", "summary": "...", "affected_from": "15.0", "affected_before": "15.8", "fixed_versions": ["15.8"]}]
}
```

Production scheduler 必須先下載固定官方來源、驗證 schema 與保存原始 snapshot，再執行 importer；不得讓 Job／Renderer 直接下載資料。PostgreSQL CVE 與 EDB advisory 的結構化擷取器、NVD CVSS/CWE enrichment scheduler，會以各來源的 parser fixture 驗證後再啟用；在此之前只能透過已驗證 snapshot 匯入，不能宣稱為自動 CVE 同步。EDB advisory 優先於繼承的 PostgreSQL／NVD 資料。

目前可由維運排程呼叫的固定官方來源為：

```bash
# PostgreSQL core-server CVE affected/fixed range
omni-healthcheck-cve-import --sync-postgresql-cves \
  --snapshot-output /data/omnicheck/archive/cve/postgresql-cves-$(date +%F).json

# EDB direct EPAS advisories only（其他 EDB 產品不會被誤納入 EPAS）
omni-healthcheck-cve-import --sync-edb-advisories \
  --snapshot-output /data/omnicheck/archive/cve/edb-advisories-$(date +%F).json

# NVD 只補強既有 CVE 的 CVSS／CWE，絕不建立或改寫 applicability 範圍
omni-healthcheck-cve-import --sync-nvd --cve-id CVE-2024-4545 \
  --snapshot-output /data/omnicheck/archive/cve/nvd-CVE-2024-4545-$(date +%F).json
```

PostgreSQL 同一 CVE 在不同 Major 的 fixed minor 可不同，Cache 以 `affected_major` 分別保存，不可把 16、17、18 的 fixed version 合併成一條範圍。

## M13.2：Matcher

Parser 僅從 Primary 的 `database_version` Canonical evidence 擷取 PostgreSQL 或 EPAS 及安裝版本。它支援任意 Major／minor（例如 12、15.7、16.4、17.10），不是寫死 17。

Matcher 使用 `affected_from <= installed < affected_before`，輸出 `applicable`、`fixed`、`not_applicable`、`potentially_applicable` 或 `pending_confirmation`，並保存 `MATCHER_VERSION`、版本 evidence、來源 URL、fixed version、sync run 與 source snapshot time。EPAS 若只有 PostgreSQL 上游公告，固定輸出 `potentially_applicable`，不會因為未確認的 inheritance/backport 而誤判為 `applicable`。

## M13.3：V4 與 Gate

Worker 在 Pipeline／Persistence 後執行 matcher，將 `cve-result.json` 與 V4 `version_updates` 重新產生。每一筆 CVE 要有 CVE ID、CVSS score／version／vector／severity、官方來源、Match Status、Fixed Version。缺任一欄位時 V4 QA fail closed。

CVE cache 超過 `OMNICHECK_CVE_STALE_AFTER_DAYS`（預設 14）時，`CVE data stale` 會寫入結果並阻止 Job 成功；無法辨識客戶版本則標示 pending confirmation，但不宣稱存在漏洞。

## Rollback

本階段使用既有 additive M13 schema，不執行 downgrade。可先設定 `OMNICHECK_CVE_ENABLED=false` 並重啟 Worker，回到既有 deterministic 報告；既有 Cache／Match／Artifact 保留。正式資料修正採新的 sync run 或 forward-fix，不覆寫稽核意義。
