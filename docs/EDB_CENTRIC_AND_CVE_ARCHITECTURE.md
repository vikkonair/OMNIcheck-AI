# OMNIcheck AI：EDB 中心化與 CVE 自動化架構決策

狀態：已核准；M9.4 功能分支與公司 EPAS deployment 驗證完成，M9.5～M15 待分階段實作
決策日期：2026-08-05  
適用範圍：M9.4～M15  
前置基準：M1～M8.1 Pipeline 與 M9.3 Web／EDB Queue／Worker

## 1. 決策摘要

OMNIcheck AI 採用三層資料責任：

1. **EDB 是主要應用資料庫**：保存可查詢的結構化資料、執行狀態、歷史、規則結果、CVE Cache 與稽核資料。
2. **`/data` 是大型檔案儲存層**：保存客戶原始證據、圖片、壓縮檔、DOCX、PDF 與 Render 暫存檔。
3. **Canonical JSON 是版本化交換與復原契約**：保留 Pipeline 與 Renderer 的邊界、Golden Regression、除錯、重新匯入及 rollback 能力。

既有 Pipeline 不重做、不刪除，順序維持：

```text
Inventory
→ Topology
→ Scope
→ Parser
→ Rules
→ Coverage／QA
→ V4 Renderer
```

從 M9.4～M9.5 開始，在既有 Pipeline 後方增加 Persistence Adapter。M9.3 已存在的 Queue／Worker 是此架構的執行基礎，但不代表後續應用資料表已經完成。

## 2. 決策背景與非目標

### 2.1 背景

M1～M8.1 已建立可追溯、可離線運作的健檢 Pipeline；M9.3 已讓 Web 案件透過 EDB Queue 與獨立 Worker 執行。若要支援客戶／系統管理、歷史比較、CVE Cache、RBAC 與 AI 稽核，只保存案件狀態與檔案路徑不足，因此需要可查詢的應用資料模型。

### 2.2 本決策不做的事

- 不改寫 M1～M8.1 的 Inventory、Topology、Scope、Parser、Rules、QA 或 V4 Renderer。
- 不取消 Canonical JSON，也不讓 Renderer 直接依賴資料庫內部表格。
- 不把圖片、DOCX、PDF 或大型壓縮檔大量存成 EDB `BYTEA`。
- 不讓 AI 決定 Primary、Scope、規則狀態、CVE 適用性或官方來源。
- 本文件本身不取代實作與驗收。M9.4 已由 `0002_m9_4` migration 建立 foundation tables；排程器、完整 Persistence Adapter 與 AI Gateway 仍必須依後續 Milestone 驗收。

## 3. 目標架構

```text
Browser／CLI
    │
    ├── Web API ──> EDB Queue／Job／Event
    │                         │
    └────────────────────> Worker
                              │
                              v
唯讀原始證據（/data）
    → M1～M8.1 既有確定性 Pipeline
    → Canonical JSON + QA + V4 DOCX／PDF（/data）
                              │
                              v
                    Persistence Adapter
                              │
                              v
EDB：Customer／System／Node／Evidence metadata／Normalized Result／
     Assessment／QA／Artifact Index／History／CVE Cache／AI Audit
```

系統即使停用 AI，仍必須可以完成解析、判斷、CVE 適用性比對、品質閘門與固定模板報告。

## 4. 資料權威與一致性

### 4.1 權威來源

| 資料類型 | 權威來源 | 說明 |
|---|---|---|
| 客戶原始證據 | `/data` immutable input | 建檔後不可覆寫，以 SHA-256 驗證 |
| 單次 Pipeline 快照 | Canonical JSON | 完整、不可變、可攜的版本化結果 |
| 線上查詢與歷史分析 | EDB | 由 Persistence Adapter 寫入的結構化投影 |
| DOCX／PDF | `/data` artifact | EDB 只保存索引、hash、大小與保留資訊 |
| CVE／Release 事實 | EDB CVE Cache | 由固定官方來源同步，不在產報時臨時搜尋 |
| 正式判斷 | 規則引擎／Version Matcher | AI 不得覆寫 |

Canonical JSON 與 EDB 不是互相取代。Canonical JSON 是單次執行的不可變快照；EDB 是主要查詢與歷史來源。EDB 的 Pipeline 投影必須能從 Canonical JSON 重新建立。

### 4.2 每次持久化必備版本資訊

每一批 Pipeline 結果至少保存：

- `job_id`
- `schema_version`
- `pipeline_version`
- `ruleset_version`
- `canonical_sha256`
- `source_snapshot_at`
- `persisted_at`

已完成的 normalized data 與 assessment 不直接就地修改。工程師覆核、註記與核准結果應保存為獨立 review／approval 紀錄，保留原始機器判斷。

## 5. Persistence Adapter 契約

### 5.1 寫入時序

```text
Pipeline 完成
→ 暫存 Canonical JSON 與 artifacts
→ QA／V4 QA 通過
→ 開始 EDB transaction
→ 依 job_id + version 進行 idempotent upsert
→ 登錄 Evidence／Artifact metadata 與 relations
→ commit
→ Job 標記 succeeded
```

若持久化失敗，不得把 Job 標成 `succeeded`。系統應使用明確的 `persistence_failed`／retry 狀態，並讓相同 `job_id`、`schema_version`、`canonical_sha256` 的重試具備冪等性，避免重複資料。

### 5.2 相容與 rollback

- Migration 採 additive-first：先新增表／欄位與雙寫能力，再切換讀取來源。
- 新 Persistence Adapter 應有 feature flag；停用後仍可由既有 Canonical JSON／filesystem 路徑產報。
- 每一個 schema migration 要有 backup、restore 與 forward-fix 計畫；不得把 Git rollback 等同資料庫 downgrade。
- Renderer 繼續吃版本化 V4 report JSON，不直接查詢 EDB table。

## 6. EDB 資料領域

M9.4 foundation 已確認實體 table；M9.5～M9.6 的 Pipeline result 與完整 Artifact lifecycle table／constraint／index 仍由各自 migration 設計確認。

### 6.1 M9.4 Application Data Foundation

- Customer：客戶識別、名稱、狀態與隔離鍵。
- System：客戶內的受檢系統／環境。
- Node：hostname、角色、產品與節點屬性。
- Topology：Primary／Standby／DR／Witness 關係與確認狀態。
- Evidence File：storage key、SHA-256、大小、media type、來源與節點映射。
- Artifact：Canonical JSON、QA JSON、DOCX、PDF 等輸出索引。

M9.4 已實作 `customers`、`systems`、`nodes`、`topology_relations`、`evidence_files`、`artifacts`，並為 `jobs` 增加 nullable tenant scope。Evidence／Artifact 目前是安全 storage metadata 基礎；衍生關係、Retention／Archive workflow 仍屬 M9.6。

`customer_id`／tenant key 必須從 M9.4 就存在於所有核心資料，不能等到 M11 才補；M11 再加入登入、政策與 Row-Level／application-level access control。

### 6.2 M9.5 Pipeline Result Persistence

- Scope decision／scope ledger
- Normalized checks
- Configuration comparison
- Assessment、狀態、觀察、結論、建議
- Evidence reference／rule provenance
- Coverage、QA、V4 QA
- Pipeline／schema／ruleset version

### 6.3 M9.6 Artifact Registry

Evidence 與 Artifact 分開建模；Artifact 還要能保存版本與衍生關係，例如 Canonical JSON 產生 V4 JSON，V4 JSON 產生 DOCX，DOCX 轉成 PDF。

每個大型檔案的 EDB metadata 至少包含：

- `storage_backend`
- `storage_key`
- `storage_root_version`
- `sha256`
- `file_size`
- `media_type`
- `created_at`
- `retention_until`
- `archive_status`

不得只保存綁死單一 VM 的絕對路徑。實體位置由 `storage_backend + storage_root_version + storage_key` 解析，才能搬遷磁碟或改用其他物件儲存。

## 7. CVE 與 Release 自動化

### 7.1 處理流程

```text
固定官方來源
→ 排程 Sync Worker
→ EDB Release／CVE Cache
→ Product Version Parser
→ Deterministic Version Matcher
→ Reviewer 狀態
→ V4 CVE Section／Quality Gate
```

CVE 資料由每日或每週排程預先同步，不在產報告時讓 AI 臨時上網搜尋。

### 7.2 來源優先順序

來源優先序是程式政策，不由 AI 選擇：

- PostgreSQL：PostgreSQL 官方 Security → NVD 補充 CVSS、CWE、CPE。
- EPAS：EDB Security Advisories／EDB PostgreSQL CVE Assessments → PostgreSQL 官方 → NVD 補充。

若來源衝突，vendor-specific assessment／backport 規則優先，並保存來源、擷取時間與衝突原因。

### 7.3 建議資料領域

- `cve_entries`
- `cve_product_impacts`
- `product_releases`
- `cve_sources`
- `cve_sync_runs`
- `job_product_versions`
- `job_cve_matches`

名稱可在 migration 設計階段調整，但必須支援來源快照、版本範圍、vendor override 與可重現比對。

### 7.4 Version Matcher

Matcher 必須處理：

- Product、major、minor／patch version
- `affected_from`、`affected_before`、fixed version
- OS、component、extension 限制
- EPAS 是否繼承 PostgreSQL CVE
- EDB backport／vendor assessment
- rejected／disputed CVE
- 客戶是否實際安裝受影響元件

輸出狀態固定為：

- `applicable`
- `fixed`
- `not_applicable`
- `potentially_applicable`
- `pending_confirmation`

資料不足時只能標示 `pending_confirmation`，不可直接宣稱客戶存在漏洞。每筆 match 必須保存 `match_reason`、比對證據、source priority、affected expression、fixed release、vendor override、review flag，以及：

- `source_snapshot_at`
- `matcher_version`
- `cve_sync_run_id`
- `review_status`

## 8. AI 責任邊界與稽核

### 8.1 AI 可以做

- 將官方英文 CVE 摘要翻譯成繁體中文。
- 整理多筆 CVE 重點與風險影響。
- 整理同 Major 升級路徑。
- 產生工程師觀察／建議初稿與主管摘要。
- 摘要歷史報告變化。
- 對已核准、已遮蔽的報告內容進行問答。

### 8.2 AI 不得做

- 決定或修改 Product、Installed Version、CVE ID、CVSS、Severity、Vector。
- 決定 Affected Version、Fixed Version 或 Match Status。
- 決定 Primary、Topology、Scope、規則狀態或官方來源。
- 修改 Canonical／V4 report contract 或跳過 Quality Gate。

AI Request／Response 稽核至少保存 provider、model、prompt template/version、輸入／輸出 hash、資料分類、遮蔽狀態、是否送出公司邊界、reviewer／approval、retention policy。真實 secret 與不必要的客戶原文不得寫入 AI audit table。

## 9. CVE 報告與 Quality Gate

CVE Section 以既有環球晶圓報告方向為主要版面基準，至少包含：

- CVE ID、Product、客戶版本
- 影響版本、Fixed Version
- CVSS Score、Severity、CVSS Version、Vector
- Match Status、官方來源
- 觀察、建議
- CVE Cache 更新時間、Matcher Version

若 CVE Cache 超過政策期限（初始建議 14 天），報告必須顯示 `CVE data stale`。正式期限與「警告或禁止交付」政策由 M13.3 規則設定及驗收，不寫死在 Renderer。

## 10. 安全、隱私與營運要求

- M9.3 正式化前完成 application user SCRAM、受控 `pgpass`／secret、實際客戶資料唯讀驗證。
- 正式環境使用 TLS `verify-full`、DNS／VIP，不能沿用測試環境 `sslmode=disable`。
- EDB backup 與 `/data` backup 必須形成同一可追溯 recovery point，並定期 restore drill。
- Artifact retention／archive／purge 必須經政策與稽核；不得只刪 EDB row 而留下孤兒檔案，反之亦然。
- Customer／tenant 隔離鍵從 M9.4 進入資料模型；M11 補齊身份、RBAC、Audit 與正式授權流程。
- 官方資料同步與 AI Gateway 都應具備 timeout、retry、rate limit、來源快照與失敗告警。

## 11. Milestone 路線

| Milestone | 內容 | 主要驗收 |
|---|---|---|
| M9.3 | 公司實機 EDB Queue／Worker 正式化 | SCRAM、實際資料唯讀 E2E、merge、`m9.3` tag |
| M9.4 | EDB Application Data Foundation | Customer／System／Node／Topology／Evidence／Artifact 基礎與 tenant key |
| M9.5 | Pipeline Result Persistence | Scope／Normalized／Assessment／Coverage／QA 冪等持久化與重建 |
| M9.6 | Artifact Registry／Retention／Archive | 可攜 storage key、版本關係、保留與封存流程 |
| M10 | 自動探索節點與拓撲確認 | 角色建議、證據、信心與人工確認，不自動猜測 |
| M11 | 登入／RBAC／客戶隔離／Audit | 身份、權限、tenant enforcement、稽核 |
| M12 | 歷史健檢比較 | 同系統跨期差異、趨勢與可追溯摘要 |
| M13.1 | 官方 CVE／Release Sync 與 EDB Cache | 固定來源、排程、快照、freshness |
| M13.2 | Product Version Parser／Version Matcher | 確定性版本適用性與理由 |
| M13.3 | CVE V4 Section／Quality Gate | 環球晶圓方向版面、stale policy、delivery gate |
| M14 | 選配 AI Gateway | 翻譯、摘要、問答、遮蔽、稽核；停用仍可產報 |
| M15 | 正式 HA／VIP／TLS／Backup／Monitoring | 生產強化、故障演練與 RPO／RTO 驗證 |

## 12. 回歸保護與完成條件

每一個 Milestone 都必須：

1. 保留 M1～M8.1 CLI／filesystem 路徑與既有 Pipeline 輸出契約，除非有明確 schema version 升級。
2. 執行 unit、integration、完整 Pytest、Golden Regression、V4 QA。
3. 使用指定實際客戶資料唯讀驗證，前後比對來源 SHA-256。
4. Migration 先在測試資料庫驗證 backup／restore／重跑冪等性。
5. 報告變更產生 DOCX／PDF 並逐頁目視 QA。
6. 更新本決策、專案手順、主手冊、validation、commit、tag 與 rollback point。

此決策的核心完成判準是：EDB 故障或 AI 停用時，仍可由保留的證據與 Canonical JSON 重建可驗證結果；EDB 正常時，則可提供一致、隔離、可查詢且可稽核的應用資料與歷史能力。
