# OMNIcheck AI 專案開發與維運手順

最後更新：2026-08-05  
適用 Repository：`codex-handoff`  
目前正式版本：M8.1  
目前開發進度：M9.3 本機實作完成，待公司環境驗證

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
| M8.1 | 正式完成、目前 main | `m8.1` | 是 | XDB、Barman、多備份工具架構 |
| M9.1 | 功能分支完成 | `84ec2e6` | 可回到 M8.1 | Web API／JobStore 骨架 |
| M9.2 | 功能分支完成 | `6cb7ccf` | 可回到 M9.1 或 M8.1 | 圖形化操作流程 |
| M9.3 | 本機完成、實機待驗證 | `f87cfec` | 可回到 M9.2 或 M8.1 | EDB metadata／Queue／Worker |

目前 `main` 指向 M8.1 後續 README commit；M9 位於 `feature/m9-web-job-management`。在公司環境驗證完成前，不建立 `m9.3` tag，也不合併 `main`。

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

Rollback：`m8.1`。這是目前正式基準。

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

尚待驗證：實際 EDB migration、pgpass、systemd、Worker 中斷恢復、未來 VIP／TLS、LibreOffice 與繁體中文字型。

開發 commit：`f87cfec`。未建立正式 tag。

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
git switch --detach m8.1
```

從正式版本建立可修改的 rollback／hotfix 分支：

```bash
git switch -c rollback/m8.1 m8.1
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

尚未正式排定 tag 的工作：

- 資料包自動探索 hostname、元件與角色建議，再由使用者確認
- 登入、角色權限、客戶隔離與稽核 UI
- EFM failover／VIP／TLS `verify-full`
- 歷史健檢比較
- CVE cache 與環球晶圓方向的 CVE 版面
- 實際 Barman wrapper fixtures
- 可選 AI 摘要、解釋與報告問答

未來新增或調整上述項目時，必須在本手順記錄 milestone 編號、範圍、驗證、commit、tag、rollback 與已知限制。
