# OMNIcheck AI 專案開發與維運手順

最後更新：2026-08-05  
適用 Repository：`codex-handoff`  
目前正式版本：M9.3
目前開發進度：M9.4 EDB Application Data Foundation 功能分支已完成本機與實際資料唯讀驗證；待公司 EDB deployment 與使用者驗收

## 1. 文件目的

本手順是 OMNIcheck AI 從 M1 至目前及後續 milestone 的持續更新紀錄，用來回答：

- 每個 milestone 為何存在
- 實際完成哪些元件
- 使用哪些工具與規則達成
- 如何驗證沒有破壞前一階段
- 哪些版本已正式完成並可 rollback
- 哪些功能仍在分支中，不能視為正式版本
- 下一步要做什麼

每個 milestone 開始、完成、驗證、合併或 rollback 時，都必須同步更新本手順。個別階段的詳細技術證據仍以 `docs/` 內的規格與 validation 文件為準。

從空白 VM 重建、套件安裝、EDB、systemd、驗證、備份、升級與復原的詳細命令，統一由 `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.md` 管理，並以 `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.docx` 交付。本文件不重複維護那些命令，以免兩份內容漂移。

## 2. 核心原則

1. 客戶原始資料永遠唯讀，不得修改或提交 Git。
2. Database、Schema、Table、Index、Role、Transaction、Bloat 等邏輯資料採 Primary-only。
3. `postgresql.conf`、`postgresql.auto.conf`、`pg_hba.conf` 是節點設定，Primary、Standby、DR 均可納入比較。
4. Witness 可承載 PEM、EFM、XDB、Barman，以及 PEM 使用的後端 PostgreSQL；不得誤認為客戶業務資料庫。
5. 無法確認節點、角色或 Scope 的資料必須標示 `pending`，不得猜測。
6. 每項正式判斷必須能追溯至可見證據。
7. 判斷狀態由確定性規則產生；AI 不得決定 Primary、Scope、狀態或報告版面。
8. 每個 milestone 完成前，都要跑自動測試、Golden Regression、實際客戶資料唯讀驗證及適用的報告 QA。
9. 功能分支驗證通過後才能合併 `main`；正式 milestone 才建立 tag。
10. 密碼、private key、客戶資料、實際輸出和本機 `.env` 不得進 Git。
11. EDB 是結構化應用資料與歷史的主要查詢來源，`/data` 保存大型檔案，Canonical JSON 保留為不可變 Pipeline／Renderer 契約與 rollback 保護。
12. AI 只能翻譯、解釋、摘要與產生文字初稿；事實、版本、Scope、規則狀態及 CVE 適用性由官方來源與確定性程式決定。

## 3. 目前整體架構

```text
使用者／Web／CLI
        ↓
案件設定與不可覆寫的原始證據
        ↓
M1 Inventory + SHA-256
        ↓
M2 Topology + Scope
        ↓
M3～M4 Parser + Canonical JSON + 設定比較
        ↓
M5 確定性規則引擎
        ↓
M6 Coverage + Security + Delivery QA
        ↓
M7 V4 Adapter + DOCX/PDF Renderer + V4 QA
        ↓
M8～M8.1 Golden Regression + Service/Backup Registry
        ↓
M9 Web、案件管理、EDB Queue、獨立 Worker
        ↓
M9.4 EDB Application Data Foundation（功能分支已驗證）
        ↓
M9.5～M9.6 Persistence Adapter、Pipeline 結果、Artifact Registry（已核准／待實作）
        ↓
M10～M15 拓撲確認、權限隔離、歷史、CVE、選配 AI、生產強化（已排定／待實作）
```

正式 M8.1 可以完全使用 CLI。M9 未設定 `OMNICHECK_DATABASE_URL` 時使用 filesystem metadata 與 Web 同程序背景工作；設定後使用 EDB metadata 與獨立 Worker。

## 4. Milestone 總覽與 rollback 點

| 階段 | 狀態 | 正式 tag／開發 commit | 可 rollback | 摘要 |
|---|---|---|---|---|
| M1 | 正式完成 | `m1` | 是 | Inventory、SHA-256、CLI |
| M2 | 正式完成 | `m2` | 是 | Topology、Primary-only Scope |
| M2.1 | 正式完成 | `m2.1` | 是 | Witness／PEM 模型 |
| M2.2 | 正式完成 | `m2.2` | 是 | Witness／EFM 模型 |
| M3 | 正式完成 | `m3` | 是 | Canonical Schema、Parser Framework |
| M3.1 | 正式完成 | `m3.1` | 是 | 實際搜集格式適配 |
| M4 | 正式完成 | `m4` | 是 | 完整 Parser |
| M4.1 | 正式完成 | `m4.1` | 是 | 邏輯資料與節點設定 Scope 分離 |
| M5 | 正式完成 | `m5` | 是 | 確定性規則引擎 |
| M6 | 正式完成 | `m6` | 是 | Coverage、安全與交付 QA |
| M7 Legacy | 歷史 checkpoint | `m7-legacy-renderer` | 是 | 舊報告 Renderer 保留點 |
| M7 | 正式完成 | `m7` | 是 | 九興 V4 DOCX／PDF |
| M8 | 正式完成 | `m8` | 是 | Golden Dataset／Regression |
| M8.1 | 正式完成 | `m8.1` | 是 | XDB、Barman、多備份工具架構 |
| M9.1 | 功能分支完成 | `84ec2e6` | 可回到 M8.1 | Web API／JobStore 骨架 |
| M9.2 | 功能分支完成 | `6cb7ccf` | 可回到 M9.1 或 M8.1 | 圖形化操作流程 |
| M9.3 | 正式完成、目前 main | `m9.3` | 是 | EDB Queue／Worker／systemd／SCRAM／客戶 E2E／PDF QA |
| M9.4 | 功能分支驗證完成 | 尚未建立 tag | 可回到 `m9.3`；DB downgrade 需另行核准 | Customer／System／Node／Topology／Evidence／Artifact 與 tenant key |

目前 `main` 與 `m9.3` 是正式可回復基準；`m8.1` 保留為導入 Web／EDB 前的 CLI rollback 點。

## 5. 各 Milestone 手順與成果

### M1：Inventory 與 CLI

目的：建立不修改來源資料的最小可執行 Pipeline。

完成內容：

- Python 專案骨架與 `omni-healthcheck` CLI
- 遞迴掃描 input directory
- 檔案類型、大小、media type 與初步分類
- 每個檔案 SHA-256
- `inventory.json`
- Docker／設定／測試基礎

主要工具：Python 3.12、`pathlib`、`hashlib`、Pytest。

驗證重點：檔案數量正確、SHA-256 穩定、來源資料不變。

Rollback：`m1`。

### M2～M2.2：Topology、Scope、Witness

目的：決定每份證據屬於哪個節點，以及能否用於正式判斷。

完成內容：

- Primary、Standby、DR、Witness 節點模型
- 恰好一台 Primary 的設定驗證
- 路徑、hostname、文字內容與 service hint 的節點映射
- Database 邏輯證據 Primary-only
- OS 證據允許所有節點
- PEM／EFM Witness 角色
- `topology.json`
- `scope-ledger.json`
- unresolved／ambiguous 資料保留為 pending

主要工具：Pydantic、Python Regex、確定性 Scope Policy。

後續修正：PEM 監控圖片未明確標節點時，依核准政策映射到 Primary。

Rollback：`m2`、`m2.1`、`m2.2`。

### M3～M3.1：Canonical Schema 與 Parser Framework

目的：把不同客戶與不同格式的 Output 轉成同一種資料契約。

完成內容：

- Canonical JSON Schema
- Parser Registry／Parser Context
- 標準化 check、node、role、section、evidence
- OS 與 Database Parser 基礎
- 實際客戶搜集檔案命名與中英文 section 適配
- Secret masking
- `normalized.json`

主要工具：Pydantic、Dataclass、Regex、版本化 schema。

驗證重點：Parser 不改變 Scope；解析失敗保持可見，不以猜測補值。

Rollback：`m3`、`m3.1`。

### M4～M4.1：完整 Parser 與跨節點設定比較

目的：完成主要 OS／DB／監控／備份資料解析，並修正 Primary-only 邊界。

完成內容：

- OS hostname、memory、OS version、filesystem 等解析
- Database version、database inventory、replication、TxID、idle transaction
- Dead tuple、table/index bloat、rarely used index
- Schema／Role privilege
- EFM、PEM、pgBackRest
- `postgresql.conf`、`postgresql.auto.conf`、`pg_hba.conf`
- Primary／Standby／DR 設定差異
- `configuration-comparison.json`

M4.1 核心修正：Database 邏輯資料仍為 Primary-only，但 PostgreSQL 設定檔是 OS／節點層資料，必須保留所有資料庫節點並比較。

Rollback：`m4`、`m4.1`。

### M5：確定性健檢規則引擎

目的：不依靠 AI，對同一份資料產生一致且可追溯的判斷。

完成內容：

- 規則門檻集中於 `config/rules.default.yaml`
- `normal`、`attention`、`critical`、`pending`
- rule ID、ruleset version、證據、觀察、結論與建議
- filesystem、TxID、idle transaction、replication
- bloat、rare index、backup、privilege
- PostgreSQL 參數差異與 HBA trust 風險
- `assessment.json`

主要工具：Python 規則引擎、YAML、Golden fixtures。

AI 狀態：僅預留 `ai.enabled=false` 介面；沒有外部 AI 呼叫。

Rollback：`m5`。

### M6：Coverage、安全與交付 QA

目的：避免缺資料或錯誤 Scope 被包裝成看似正常的報告。

完成內容：

- 每個節點應有檢查項目的 coverage ledger
- Primary 唯一性與 Primary database evidence gate
- Assessment evidence reference gate
- Secret detection
- 客戶／來源路徑／節點隔離檢查
- `coverage-ledger.json`
- `qa-result.json`
- mandatory gate 失敗時禁止正式交付

當時驗證：26 tests，台灣行動支付來源前後 SHA-256 一致，QA 8/8 gate 通過。

Rollback：`m6`。

### M7：九興 V4 DOCX／PDF 報告

目的：把 M1～M6 的結構化結果接上核准 V4 Renderer，不重寫 Pipeline。

完成內容：

- Canonical／Report Model 到 V4 report JSON Adapter
- Vendor V4 Renderer hash pin
- V4 QA
- DOCX 與 LibreOffice PDF
- A4 版面、繁體中文字型與頁面 render 檢查
- 九興版面方向、環球晶圓 CVE 版面政策
- 主要章節換頁與長表格 continuation
- 每項 Output、狀態、觀察、結論、建議

核准內容調整：

- TxID 年齡前 10
- 罕用索引前 10，zero-scan 優先
- Database 清單只留名稱、owner、privilege、size
- 精簡 replication 欄位
- 設定檔小字體
- EPAS 顯示全名
- 封面 `Omniwaresoft Tech`
- 架構總覽不顯示元件欄

台灣行動支付實際報告最終為 37 頁 A4，DOCX／PDF 頁數一致並完成逐頁檢查。

Rollback：`m7`；舊 Renderer checkpoint 為 `m7-legacy-renderer`。

### M8：Golden Dataset 與 Regression

目的：不提交客戶資料，也能長期防止 Parser、Scope、規則與報告回歸。

Golden Dataset：

- `jiuxing_v4`
- `globalwafers_pem`
- `multi_node_scope`

完成內容：

- 去識別、虛構的 fixture
- manifest、schema、ruleset、template version
- expected contract
- V4 Renderer manifest hash 驗證
- Golden DOCX／PDF 與視覺檢查

當時完整測試 38 項，實際客戶資料 QA、V4 QA 與 37 頁 PDF 均通過。

Rollback：`m8`。

### M8.1：Witness 元件與多備份工具

目的：把節點角色、服務元件、備份工具分開，避免 XDB 或 Barman 被錯誤建模。

完成內容：

- Service Registry：PEM、EFM、XDB、pgBackRest、Barman
- XDB 只允許 Witness
- PEM 只允許 Witness
- Backup provider 與實際 node/service 關聯
- Barman parser 與規則
- Witness 上的 Barman 不進入 Primary-only 邏輯 Scope
- pgBackRest 未指定 provider 時沿用 Primary 規則

當時完整測試 45 項，Golden PDF 9 頁、實際客戶 PDF 37 頁通過。

限制：Barman 實際客戶 wrapper 尚待取得實際去識別範本後補 fixture。

Rollback：`m8.1`。這是導入 Web／EDB 前的正式 CLI 基準。

### M9.1：Web API 與 Filesystem JobStore

目的：在不重寫 M1～M8.1 的前提下，提供 Web 案件入口。

完成內容：

- FastAPI
- 建立、列表、查看案件
- 不可覆寫的原始證據上傳
- 路徑穿越、重複檔名與半批上傳防護
- 啟動既有 `run_generate`
- 查詢狀態、列出及下載輸出
- Filesystem JobStore

開發 commit：`84ec2e6`。

### M9.2：圖形化操作流程

目的：移除手寫 JSON、Job ID、`curl` 和 Terminal 操作需求。

完成內容：

- 客戶、系統、期間、產品與報告格式表單
- 動態新增 Primary、Standby、DR、Witness
- 依角色配置 PEM、EFM、XDB、pgBackRest、Barman
- 資料夾選擇與相對路徑保留
- 一鍵建案、分批上傳、執行、輪詢與下載
- 案件列表與結果頁面

驗證：49 tests、Golden V4、台灣行動支付實際資料、DOCX／PDF、來源 SHA-256 均通過。

開發 commit：`6cb7ccf`。

已知限制：節點 hostname 與角色仍由使用者確認；系統會把證據自動映射到已配置節點，但尚未從完全未知的資料包自動決定 Primary／Standby／DR／Witness。

### M9.3：EDB Metadata、Queue 與 Worker

目的：讓 Web 重啟或多人操作時，案件與背景工作仍可持久保存、排隊及恢復。

完成內容：

- SQLAlchemy EDB／PostgreSQL metadata
- Alembic migration
- `omnicheck.jobs` 與 `omnicheck.job_events`
- `FOR UPDATE SKIP LOCKED` 原子 claim
- 獨立 `omni-healthcheck-worker`
- retry、max attempts、heartbeat、lease owner、stale recovery
- Database health 503 fail-closed
- 非 succeeded 案件禁止下載部分輸出
- Filesystem 模式向下相容
- CentOS 9 systemd、pgpass、環境範本

本機驗證：56 tests、V4 bundle 29 hashes、Alembic PostgreSQL offline SQL、台灣行動支付 DB queue → Worker → DOCX/PDF 均通過。

公司測試環境規格：

```text
Application VM：192.168.118.77
Data：/data/omnicheck
EDB：192.168.118.81:5444
Database/User：omnicheck_app
Schema：omnicheck
TLS：off（僅測試）
Service：systemd
```

公司實機驗證（2026-08-05）：`omnicheck-ai-app`（192.168.118.77）已連接 EPAS 17.10（192.168.118.81:5444），完成 `0001_m9_3` migration、Web／Worker systemd、EDB queue、retry reset、LibreOffice／Noto CJK、Golden、服務重啟與 metadata/output persistence。實機驗證揭露並修正 EPAS Redwood DateStyle、Linux fontconfig 與 V4 摘要孤立標題三項跨平台問題，部署版本為 `a1d286f`，本機與公司 VM 完整測試均為 60 項通過。

正式化驗證：application user 已使用精確 `.77/32` SCRAM 規則與 `0600` pgpass；無密碼登入遭拒。台灣行動支付實際資料在 SCRAM 重啟後完成 E2E，13 inputs／13 outputs、Scope 11 allowed／2 excluded／0 pending、QA 8/8、V4 QA、29 頁 PDF 逐頁 QA 與來源 SHA-256 不變均通過。TLS／VIP／EFM failover 納入 M15；既有 cluster-wide trust 規則需另案盤點收斂。修正前 API 500 留下兩筆空 draft Golden 案件，未經核准不直接刪除。

正式版本：`m9.3`；Renderer 分頁修正 commit：`a1d286f`。

### M9.4：EDB Application Data Foundation

目的：在不改寫既有 Pipeline 的前提下，建立 EDB 中可查詢、具 tenant 邊界的客戶、系統、節點、拓撲與檔案 metadata 基礎。

完成內容：

- 新增 `customers`、`systems`、`nodes`、`topology_relations`、`evidence_files`、`artifacts`。
- `jobs` 增加 nullable `customer_id/system_id`，保留 M9.3 legacy rows 與 Queue 相容性。
- 每個核心 relation 使用 `customer_id` 或 Customer／System／Node 複合外鍵阻擋跨 tenant 關聯。
- Evidence／Artifact 保存可攜 storage key、SHA-256、file size、media type；大型檔案仍留在 `/data`。
- ApplicationDataStore 提供 tenant-scoped 建立、查詢、Job 關聯與登錄操作。
- Alembic `0002_m9_4` 採 additive upgrade，並提供回到 `0001_m9_3` 的 downgrade。

驗證：M9.4／M9.3 targeted tests 13 passed，完整 65 tests passed，PostgreSQL offline upgrade／downgrade SQL 生成成功。台灣行動支付 14 個來源檔案以隔離 SQLite 投影，建立 1 Customer、1 System、5 Nodes、4 Topology relations、14 Evidence records；來源前後 path／size／SHA-256 manifest 完全一致。

限制：尚未部署公司 `.81`、尚未讓 Web 自動建立 Customer／System／Node，也尚未持久化 Scope／Normalized／Assessment／QA；後者屬 M9.5。Artifact 衍生版本與 retention/archive workflow 屬 M9.6。

Rollback：目前正式 application 基準仍為 `m9.3`。`0002_m9_4 → 0001_m9_3` downgrade 會刪除 M9.4 tables／data 與 Job tenant columns，必須先停止服務、備份、完成 staging restore drill 並另行核准；優先採 forward fix 或讓舊程式忽略 additive schema。

詳細文件：`docs/M9_4_APPLICATION_DATA_FOUNDATION.md`、`docs/M9_4_VALIDATION.md`。

## 6. 標準開發手順

後續每一個 milestone 都依下列順序進行：

1. 從最新正式 `main` 或目前核准功能分支建立新分支。
2. 讀取 `AGENTS.md`、本手順、Pipeline／Acceptance／相關 milestone 文件。
3. 列出允許修改與不得修改的元件。
4. 先建立失敗案例與 Golden fixture，再實作功能。
5. 不改寫既有 Pipeline 契約，除非 milestone 明確要求 schema version change。
6. 執行相關 unit／integration tests。
7. 執行完整 `.venv/bin/pytest`。
8. 驗證 V4 bundle manifest。
9. 使用台灣行動支付實際資料唯讀端到端執行。
10. 比較來源執行前後檔案數、大小、SHA-256。
11. 報告相關變更要產生 DOCX／PDF、render page PNG 並目視檢查。
12. 更新 milestone validation 文件及本手順。
13. 執行 `git diff --check` 與 secrets／客戶資料檢查。
14. Commit 並推送功能分支。
15. 使用者驗收後才合併 `main`、重跑測試並建立 tag。

## 7. 標準驗證指令

```bash
.venv/bin/pytest
```

```bash
.venv/bin/python ../omni-healthcheck-codex-complete/scripts/verify_bundle.py
```

```bash
git diff --check
```

實際客戶驗證的輸出與暫存設定必須放在 `/tmp` 或其他隔離位置，不得放進來源資料夾或 Repository。

## 8. Git 與 Rollback 手順

列出正式版本：

```bash
git tag --list --sort=version:refname
```

檢查某一正式版本，不修改目前分支：

```bash
git switch --detach m9.3
```

從正式版本建立可修改的 rollback／hotfix 分支：

```bash
git switch -c rollback/m9.3 m9.3
```

回到目前 M9 開發分支：

```bash
git switch feature/m9-web-job-management
```

正式 rollback 不使用 `git reset --hard`。若 `main` 已包含後續版本，應以核准 tag 建立分支、驗證後再決定 merge／部署策略。

資料庫 migration rollback 不等同 Git rollback。執行 Alembic downgrade 會刪除或改變資料表，必須先備份並另外取得明確核准。

## 9. M9.3 公司環境部署待辦

目前只記錄步驟，不自動連線或部署：

1. `.77` 唯讀確認 Python、CPU、RAM、SELinux、LibreOffice、psql。
2. 確認 `.77 → .81:5444` 網路與 EDB 登入。
3. 將功能分支安裝到 `/data/omnicheck/app/current`。
4. 建立 `/etc/omnicheck-ai/pgpass`，owner `omnicheck`、mode `0600`。
5. 建立 `/etc/omnicheck-ai/omnicheck.env`，不得提交 Git。
6. 先執行 `alembic current`，再經核准執行 `alembic upgrade head`。
7. 安裝、啟動並檢查 Web／Worker systemd。
8. Golden Dataset 建案與 queue／worker 驗證。
9. 台灣行動支付實際資料唯讀驗證。
10. Worker 停止、重啟、retry、stale lease recovery。
11. LibreOffice、中文字型、DOCX／PDF 視覺 QA。
12. 驗證完成後更新本手順、合併 `main`、重跑測試、建立正式 tag。

## 10. 後續方向

後續架構已由 `docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md` 核准；下列項目尚未實作或建立正式 tag：

| 階段 | 預計內容 | 達成方式與主要驗收 |
|---|---|---|
| M9.3 正式化 | 完成目前公司部署 | SCRAM／pgpass、實際客戶資料唯讀 E2E、測試、merge `main`、`m9.3` tag |
| M9.4 | EDB Application Data Foundation | Additive migration；Customer／System／Node／Topology／Evidence／Artifact 與 tenant key |
| M9.5 | Pipeline Result Persistence | Pipeline 後加冪等 Persistence Adapter；保存 Scope／Normalized／Assessment／Coverage／QA，可由 Canonical JSON 重建 |
| M9.6 | Artifact Registry／Retention／Archive | `storage_backend + storage_key`、hash、版本關係、保留與封存 Worker |
| M10 | 自動探索與拓撲確認 | Parser evidence 產生角色建議與信心，使用者確認後才進正式 Pipeline |
| M11 | Login／RBAC／客戶隔離／Audit | 身份提供者、角色政策、tenant enforcement、稽核事件 |
| M12 | 歷史比較 | 依 customer／system／period 比較 normalized checks 與 assessment，產生趨勢 |
| M13.1 | CVE／Release Sync 與 Cache | 固定官方來源、排程 Worker、來源快照、freshness policy |
| M13.2 | Version Parser／Matcher | 確定性 product/version range、EDB backport、component 條件與 match reason |
| M13.3 | CVE V4 Section／Quality Gate | 環球晶圓方向版面、stale data 警告／阻擋、逐頁 QA |
| M14 | 選配 AI Gateway | 遮蔽後翻譯、摘要、觀察建議初稿與問答；完整 prompt/model/approval audit |
| M15 | 生產強化 | EFM／VIP、TLS `verify-full`、backup/restore、監控與故障演練 |

實際 Barman wrapper fixtures 仍待提供，但不阻擋 M9.3 正式化與 M9.4。未來每一階段都必須記錄範圍、migration、驗證、commit、tag、資料 rollback／forward-fix 與已知限制。
