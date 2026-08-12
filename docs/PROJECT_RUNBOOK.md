# OMNIcheck AI 專案開發與維運手順

最後更新：2026-08-12
適用 Repository：`codex-handoff`  
目前正式版本：M10.1
目前開發進度：M14.5 AI 完整交付流程開發中；Job 必須等全部適用 Section 的 Gemma 草稿、最終 DOCX／PDF 與 QA 完成後才顯示 succeeded。初版報告採 `approved → ai_draft → deterministic`，工程師下載後仍可修改、核准及重新產報

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
13. `PEM_check` 的 Database Output 是 PEM Server 後端 PostgreSQL 證據，必須映射到唯一 PEM Witness 並排除於業務 Primary 邏輯資料檢查；人工映射不得繞過此服務邊界。
14. Ruleset `2026.2`：filesystem 50%～未滿 70% 維持正常但提醒觀察量體成長，70% 以上列注意；table/index bloat Output 保留前十名，觀察／建議逐一列出其中指數 >2 的物件及 `VACUUM FULL`／`REINDEX`；罕用索引 `idx_scan=0` 優先且最多 10 筆；權限輸出排除 `pg_*`、`postgres`、`enterprisedb`。
15. Ruleset `2026.3`：pgBackRest 改為逐 stanza 解析 `status`；主要 stanza 的 `status: ok` 明確判為正常並要求持續監控與還原驗證，其他 stanza 獨立揭露，無法唯一辨識主要 stanza 時標示待確認。AI 草稿不得省略 stanza 與 status 事實。
16. 純資訊清冊（系統組態、版本、Extension、資料庫清單）只顯示 Output，不顯示狀態／觀察／建議，也不送入 AI。PEM／EFM 服務摘要沒有明確異常時維持純資訊；出現 error／failed／fatal 等明確異常時，必須產生評估並送入 AI Workflow。容量、監控、組態差異、運行狀態、權限與維護候選仍屬健檢判斷。
17. Ruleset `2026.4`：PEM Server、PEM Agent、EFM、XDB Output 出現明確異常訊號時列為注意；PEM／XDB 僅在 Witness 角色評估。5.1 服務摘要有異常時產生觀察、建議與 AI Workflow，無異常時仍為純資訊。
18. Ruleset `2026.5`：大型資料表列出前三大物件與含索引容量；SLRU 提供累積命中率與讀取量最高項目，但單次快照保守維持待確認；Dead Tuple 列出前三高物件與數量並要求複核比例及 autovacuum。三者均建立 AI Workflow，AI 省略必要事實時退回 deterministic 內容。
19. M14.4：所有非資訊型文字 Section 保存 V4 可見 Evidence Snapshot 並送入 Ollama 分析；Prompt 遮蔽敏感資訊、排除路徑與圖片內容，超長 Evidence 受控截斷。AI 仍只能產生草稿，正式報告必須經工程師核准。
20. M14.5：AI 成為 Job 完成條件。Worker 在同一 Job lease 內等待 durable batches 終止，以 AI draft 或 deterministic fallback 重新產生 DOCX／PDF；完成連結只在最終產物與 QA 完成後出現。

2026-08-12 公司修正部署：使用 Job `a1714d038a204676b88ba453ef245876` 的不可變 input 驗證 `90f9aca`，29 個可見項目中 5 個資訊清冊不含狀態／觀察／建議，24 個判斷項目進 Workflow，V4 QA、DOCX／PDF 與 116 tests 通過。公司 `current` 已切至 `90f9aca`，Web／Worker health 正常，rollback 為 `a18c7cd`。

2026-08-12 pgBackRest stanza 修正部署：`4d2097e` 將備份判斷改為逐 stanza 解析；同一 Output 的 `edb=status: ok` 與 `edbdr=error` 不再互相污染主要備份結論。公司 119 tests 通過，並以 Job `a1714d038a204676b88ba453ef245876` 的不可變 input 在獨立輸出目錄驗證 Ruleset 2026.3、QA／V4 QA 通過。公司 `current` 已切至 `4d2097e`，Web／Worker 與 AI Gateway health 正常，rollback 為 `90f9aca`；本次無 migration。

2026-08-12 PEM 服務摘要修正部署：`62bb5a3` 將 5.1 PEM／EFM 服務摘要改為條件式評估。公司 120 tests 通過；使用同一 Job 的不可變 input 驗證只對 Witness `pemp1` 建立 PEM Server 注意評估，辨識 46 行明確異常、建立 1 個 `pem_efm_summary` Workflow，QA／V4 QA 通過。公司 `current` 已切至 `62bb5a3`，Web／Worker 與 AI Gateway health 正常，rollback 為 `4d2097e`；本次無 migration。

2026-08-12 資料型 AI Section 部署：`956cbb0` 為大型資料表、SLRU、Dead Tuple 建立證據式 deterministic baseline 與 AI Workflow，並對 AI 草稿執行必要事實保留驗證。公司 122 tests 通過；同一 Job 的不可變 input 正確建立三個 Workflow，Ruleset 2026.5、QA／V4 QA 通過。公司 `current` 已切至 `956cbb0`，Web／Worker 與 AI Gateway health 正常，rollback 為 `62bb5a3`；本次無 migration，Vision 驗證暫緩。

2026-08-12 M14.4 前置相容部署：公司先部署 `419d0df`，只將持久化 Workflow JSON 的未知 additive 欄位改為忽略，不變更 Pipeline、功能或 schema。公司完整測試與 health 通過，讓後續含 `evidence_snapshot` 的新案件可安全 rollback 至此版本。正式 M14.4 部署後 rollback 應指向 `419d0df`，而非更舊的 strict payload release。

2026-08-12 M14.4 模型與 UI 驗收：相同 filesystem 規則測試中，`gpt-oss:20b` 文字可用但較冗長且不接受圖片，`nemotron-3-ultra:cloud` 文字可用但曾誤寫掛載點且圖片回 HTTP 400，`gemma4:26b` 文字最精簡並成功分析 CPU、Memory、Disk、Process 四張 PEM 圖。因此公司候選設定採 `OMNICHECK_AI_MODEL=gemma4:26b` 與 `OMNICHECK_AI_VISION_MODEL=gemma4:26b`。Vision 數值仍可能誤讀，必須保留「看不清楚即待確認」Prompt、deterministic fallback 與工程師核准。UI 同步調整為案件列表預設收合、正式報告只優先顯示 PDF／DOCX、JSON／QA 置於進階收合區，並在結果區直接顯示可複製 Job ID。

2026-08-12 M14.4 Gemma／UI 正式部署：公司 App VM `current` 已切至 release `4c755b7`，Web／Worker active，health 顯示 EDB metadata、external worker、AI enabled；環境檔備份為 `/etc/omnicheck-ai/omnicheck.env.pre-4c755b7`，application rollback 為 `33d02b1`。公司 release 124 tests 通過。實際 Gateway request `3ea01317c5194e4f843ffeed1da41bfd` 使用 `gemma4:26b` 將 CPU PEM 圖保存為 `ai_drafted` revision 2，selected source 仍為 deterministic。Chrome 實機驗收確認案件列表預設收合；展開後才載入案件；結果區顯示 Job ID、PDF／DOCX，12 個內部產物保持收合。

2026-08-12 M14.5 開始：使用者確認 AI 建議必須是報告生成的一環，不接受「Pipeline 先成功、AI 背景補草稿」的流程。實作方向固定為同步等待全部 AI batches、個別失敗 deterministic fallback、以 approved／AI draft／deterministic 優先順序產生初版報告，最後才將 Job 標示 succeeded。本變更不調整 Primary、Scope、Rules 或 V4 版面，也不新增 migration。規格見 `docs/M14_5_AI_COMPLETE_DELIVERY.md`。

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
M9.4 EDB Application Data Foundation（正式完成）
        ↓
M9.5 Pipeline 結果 Persistence Adapter（正式完成）；M9.6 Artifact Registry（正式完成）
        ↓
M10 Deterministic Discovery + Operator Confirmation（正式完成）
        ↓
M10.1 Legacy Database Output Classification（正式完成）
        ↓
M10.2～M15 前端整合、Section 審核、選配權限、歷史、CVE、Ollama、生產強化
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
| M9.3 | 正式完成 | `m9.3` | 是 | EDB Queue／Worker／systemd／SCRAM／客戶 E2E／PDF QA |
| M9.4 | 正式完成 | `m9.4` | 是；DB downgrade 需另行核准 | Customer／System／Node／Topology／Evidence／Artifact 與 tenant key |
| M9.5 | 正式完成 | `m9.5` | 可回到 `m9.4` application；DB downgrade 需另行核准 | Scope／Normalized／Config／Assessment／Coverage／QA 冪等投影與公司部署 |
| M9.6 | 正式完成 | `m9.6` | 可回到 `m9.5` application；DB downgrade 需另行核准 | Artifact 版本、衍生關係、事件、Retention、Archive 與公司部署 |
| M10 | 正式完成 | `m10` | 可回到 `m9.6`；無 DB downgrade | 未知資料包節點／角色／服務候選、理由、人工確認、fail-closed gate 與公司部署 |
| M10.1 | 正式完成、目前 main | `m10.1` | 可回到 `m10`；無 DB downgrade | 舊式 Database Output 內容辨識、來源節點候選與人工 mapping |
| M10.3.1 | 公司候選完成、待使用者驗收 | `e56f043` | 可回到 `m10.1`；無 DB downgrade | Section JSON、AI draft／review／approval 分離與 Artifact 登錄 |
| M10.2 UI Adapter | 公司候選已部署、待使用者驗收 | `327748d` | 可回到 `0a6dccd`；無 DB downgrade | 同仁 UI Adapter、聯詠拓撲／格式、明確 Database Output 來源 |
| M10.3.2 | 完成、公司 E2E 通過 | `48eac67` 候選 | App 可回 `327748d`；0008 保留、forward-fix | EDB current＋revision history、review／approval API、approved-only Renderer |
| M14.1 | 完成、公司真實模型 E2E 通過 | `6b24cb5` | 關閉 AI／App 回 `48eac67`；0009 保留 | Ollama draft、遮蔽、audit、timeout/retry、deterministic fallback |
| M14.2 | 公司候選完成、待多項批次／使用者驗收 | `8031088` | 關閉 AI／App 回 `m14.1`；0010 保留 | Section 審核工作台、durable batch、逐筆限流、進度與 fallback/conflict |
| M14.3 | 公司候選已部署、待使用者驗收 | `a18c7cd` | 設定 `OMNICHECK_AI_AUTO_DRAFT_ALL=false` 或 App 回 `8bef579`；無 migration | 全 V4 Section 自動批次、PEM Vision 分流、整批核准產報與 Ruleset 2026.2 |

目前 `main` 與 `m10.1` 是正式可回復基準；`m10` 保留為 M10.1 前的 application rollback 點，且不需 database downgrade。

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

驗證：M9.4／M9.3 targeted tests 13 passed，完整 65 tests passed，PostgreSQL offline upgrade／downgrade SQL 生成成功。台灣行動支付 14 個來源檔案以隔離 SQLite 投影，建立 1 Customer、1 System、5 Nodes、4 Topology relations、14 Evidence records；來源前後 path／size／SHA-256 manifest 完全一致。公司 `.77/.81` 已由 `0001_m9_3` 升級至 `0002_m9_4`，備份 archive／hash、新表 constraints、legacy Job、transaction rollback smoke、Web／Worker health 與 Golden live Queue E2E 均通過；current release 為 `9dc7d76`。

限制：尚未讓 Web 自動建立 Customer／System／Node。Scope／Normalized／Assessment／QA 已在後續 M9.5 完成；Artifact 衍生版本與 retention/archive workflow 屬 M9.6。完整 restore／實際 downgrade drill 尚未執行。

Rollback：M9.4 正式 application 基準為 `m9.4`，目前最新基準為 `m9.5`。`0002_m9_4 → 0001_m9_3` downgrade 會刪除 M9.4 tables／data 與 Job tenant columns，必須先停止服務、備份、完成 staging restore drill 並另行核准；優先採 forward fix 或讓舊程式忽略 additive schema。

詳細文件：`docs/M9_4_APPLICATION_DATA_FOUNDATION.md`、`docs/M9_4_VALIDATION.md`。

### M9.5：Pipeline Result Persistence

目的：在既有 Pipeline 後加入冪等 Persistence Adapter，讓 Scope、Normalized、設定比較、Assessment、Coverage 與 QA 可依 Customer／System／Job 查詢，同時保留 Canonical JSON 契約。

完成內容：

- `0003_m9_5` 新增 `pipeline_snapshots` 與七張 row-level child tables。
- Snapshot 以 `job_id + schema_version + canonical_sha256` 冪等；相同輸出重跑不重複寫入。
- Worker 只有在單一 transaction 完成投影後才標記 succeeded；失敗沿用 retry／failed 流程。
- `normalized_unparsed` 保存 Parser 尚未支援的證據，不讓資料靜默消失。
- Legacy unscoped Job 保持相容；`OMNICHECK_PERSIST_RESULTS=false` 可暫停 Adapter。

驗證：本機與公司 VM 70 tests、V4 hashes、PostgreSQL offline migration、台灣行動支付 14 檔唯讀投影均通過。公司 `.77/.81` 已部署 release `916adff` 並升級至 `0003_m9_5`；Scoped Golden Job `fa28fea9f9d04f53bbd96f209042fe44` 一次成功，建立 Snapshot `1be99fddb5404aa8add49a89146ee339`，冪等重寫與 Web／Worker restart 後資料仍存在。

Rollback：application 可切回 `m9.4` 並保留 additive M9.5 schema。`0003_m9_5 → 0002_m9_4` 會刪除全部 Pipeline snapshots 與 child rows，必須先備份、完成 staging restore/downgrade drill 並另行核准。

詳細文件：`docs/M9_5_PIPELINE_RESULT_PERSISTENCE.md`、`docs/M9_5_VALIDATION.md`。

### M9.6：Artifact Registry／Retention／Archive

目的：讓 `/data` 大型輸出具備可攜 metadata、版本、衍生關係與安全封存流程，不把 DOCX／PDF／圖片存成 EDB `BYTEA`。

完成內容：`0004_m9_6` 新增 Artifact version、timestamps、`artifact_relations` 與 `artifact_events`；Scoped Worker 自動登錄輸出；同檔冪等、內容改變升版。Archive Worker 預設 dry-run，apply 時先複製、驗 SHA-256、再更新 metadata，且保留來源。刪除只到可取消的 `pending_delete`，不自動刪實體檔。

驗證：本機與公司 VM 74 tests、PostgreSQL migration、V4 hashes 與台灣行動支付 14 檔唯讀驗證通過。公司 `.77/.81` 已部署 release `2fc2ce7` 並升級至 `0004_m9_6`；Scoped Golden Job `3c600f747da84d4e92f3c86f6fd0f6d3` 建立 11 artifacts、2 relations、11 events，冪等與重啟通過。Archive dry-run 為 0 items，archive manifest 不變。

Rollback：application 可回 `m9.5`。`0004_m9_6 → 0003_m9_5` 會刪除 relations、events、M9.6 欄位與 version 2 以上 registry rows，必須備份、staging 演練並另行核准；migration 不刪實體檔。

詳細文件：`docs/M9_6_ARTIFACT_LIFECYCLE.md`、`docs/M9_6_VALIDATION.md`。

### M10：自動探索與拓撲確認

目的：讓使用者選取未知資料包後，先由確定性程式提出節點、Primary／Standby／DR／Witness 與服務候選，再由工程師確認後執行既有 Pipeline。

完成內容：新增 `topology_discovery.py` 與 `/api/topology/discover`；使用檔名／路徑、EFM `bind.address`、`is.witness`、DR hostname、PEM Server 與備份訊號。Web 自動分析資料、顯示信心與理由，未確認時禁止執行；原始建議與確認狀態寫入 `job.yaml.topology_confirmation`。

驗證：本機與公司 VM 均為 78 tests；台灣行動支付 13 檔找出 5 台節點與唯一 Primary，Web 未確認 gate、確認後 13 outputs、QA 8／8、V4 QA、DOCX／PDF 及來源 SHA-256 不變均通過。2.1 Database 欄已驗證為節點安裝清冊：Primary／Standby／DR 顯示案件資料庫產品，PEM Server 顯示 PostgreSQL backend，純 EFM Witness 留白；此顯示規則不改變邏輯資料 Primary-only Scope。公司 `.77/.81` release `6e8ee6e` 的 Queue／Worker Job `12c90aa3da354f1c83dbc42e6d57e118`、重啟持久性與 journal 檢查通過；EDB revision 維持 `0004_m9_6`。

Rollback：application 可直接切回 `m9.6`，不需 Alembic downgrade。詳細文件：`docs/M10_TOPOLOGY_DISCOVERY.md`、`docs/M10_VALIDATION.md`。

### M10.1：舊格式 Database Output 分類與來源確認

目的：讓沒有 hostname 的 `ENGDB_check.txt` 類型舊資料可辨識為 Database Output，但仍由工程師決定它實際來自哪個節點。

完成內容：內容特徵評分、Discovery `evidence_candidates`、Web 來源節點下拉選單、Job `evidence_mappings` 與 Scope 稽核來源。映射至非 Primary 節點時，邏輯檢查仍由 Primary-only policy 排除。

驗證：本機與公司 VM 各 82 tests；實際 ENGDB 三檔唯讀驗證將 Primary logical checks 由 0 提升為 17，QA 8/8、V4 QA、19 頁 PDF 與來源 SHA-256 均通過。

Rollback：不含 migration、套件或環境變數變更，可直接切回正式 `m10`。

詳細文件：`docs/M10_1_LEGACY_DATABASE_EVIDENCE.md`、`docs/M10_1_VALIDATION.md`。

### M10.3.1：Backend Section Workflow Foundation

目的：在接 Ollama 前先建立安全且版本化的 Section 文字工作流，不讓 AI 草稿改變規則事實或直接進入正式報告。

完成內容：新增 `section-workflow.json`、`generated／ai_drafted／reviewed／approved` 狀態、確定性／AI／工程師文字分離、工程師核准前維持 deterministic selected source，以及 Artifact 登錄與衍生關係。V4 Renderer 維持不變。

驗證：本機與公司 VM 完整 85 tests；台灣行動支付 14 檔唯讀流程建立 19 個 deterministic section items；公司 ENGDB 三檔建立 9 個 items。兩者 QA 8/8、V4 QA、DOCX/PDF 與來源 manifest 均通過。公司候選 release 為 `e56f043`，Web／Worker／EDB health 正常。

限制：為避免與公司 EDB 暫停 M11 additive revision 形成 Alembic 分支衝突，本階段不新增 migration；EDB tables／API 留到 M10.3.2 schema reconciliation 後。

Rollback：application 可直接回 `m10.1`，不需 database downgrade。

詳細文件：`docs/M10_3_SECTION_FOUNDATION.md`、`docs/M10_3_VALIDATION.md`。

### M10.2：同仁 UI Adapter 整合候選

目的：採用同仁 `0.13.2.dev2` 的整合式健檢 UI，但繼續使用我們 M10.3.1 的 Pipeline、Canonical JSON、Section Workflow、EDB Queue/Persistence 與 V4 Renderer。

整合方式：`/`、`/integrated` 使用新版 UI，`/classic` 保留原介面。第一階段不帶入 Login/RBAC、Knowledge/CVE、GPDB、同仁 migration 或同仁後端。Topology discovery 無法確認時改為 fail closed，保留人工節點且禁止勾選確認。

驗證：同仁 Bundle 與 77 上保存的 `0.13.2.dev2` 185 個檔案逐檔 SHA-256 完全一致；同仁 Source 107 tests 通過；整合分支與公司候選 release `a0582a0` 各 87 tests 通過；Browser DOM／視覺驗證無 overflow，未出現 Knowledge／GPDB，傳統介面可切回。台灣行動支付既有 immutable 13 檔候選執行產生 14 outputs，QA/V4 QA、Section Workflow、DOCX/PDF 通過，來源 digest 前後相同。正式切換後 Golden Job `2a8d40b0727c41119236fd6642cd2ec2` 完成 Web → EDB Queue → Worker → 12 個 Canonical/V4 產物，QA 與 V4 QA 均允許交付；Web／Worker 重啟後案件與產物仍可讀取。

Rollback：本階段無 migration、套件或環境變數變更。畫面可切 `/classic`；Application 可切回 `e56f043`，不需 database downgrade。

部署狀態：公司 `current` 已切至 `327748d`；聯詠三檔正式 Discovery API 自動提出 `OADB15N → Primary`、`OADB15-DR → DR` 與 Database Output 來源 `OADB15N`。本機 93 tests、公司相關 28 tests、health、Web／Worker per-release process、coverage 92.5%、QA/V4 QA、29 頁 PDF 與來源 hash 通過。rollback 為 `0a6dccd`，無 migration。詳細文件：`docs/M10_2_COWORKER_UI_INTEGRATION.md`。

### M10.3.2：EDB Section persistence 與 approved-only Renderer

公司 EDB 的 `0007_m13_catalog` 已與同仁 source 逐檔核對。Repository 原樣納入 `0005_m11`、`0006_m13`、`0007_m13_catalog`，再新增 additive `0008_m10_3_sections`；不得使用 stamp 或正式環境 downgrade。

Worker 在 PipelineResult persistence 後將 `section-workflow.json` 寫入 EDB。current projection 與 append-only revisions 分開保存，所有人工／AI 寫入要求 actor 與 expected revision。AI 關閉時 deterministic 可直接 review；Renderer 僅選 approved，其他狀態一律 deterministic。API、schema、rollback 與驗收方式詳見 `docs/M10_3_2_SECTION_PERSISTENCE.md`。

公司驗證：migration 前 schema-only backup SHA-256 為 `18601b514507cf952616a152a0b91f602cf177a3e4c65e73d74dc2283863c2c6`；EDB 已由 0007 升至 0008。Job `774499b66693455eb16d14f04a5fd687` 完成 AI-disabled direct review、stale revision 409、approval、approved-only render 與 revision audit。詳細證據見 `docs/M10_3_2_VALIDATION.md`。

### M14.1：Ollama Section Draft Gateway

App VM `192.168.118.77` 已以不含客戶資料的 prompt 成功呼叫 `http://192.168.68.39:11434/v1/chat/completions`，模型 `gpt-oss:20b` 回覆正常。程式新增預設關閉的 Gateway、最小化 prompt、node／IP／email／credential 遮蔽、固定 JSON schema、timeout／retry、EDB request/response audit，以及失敗時不修改 Section 的 deterministic fallback。Migration `0009_m14_ai_gateway` 只新增 audit table。完整規格見 `docs/M14_1_OLLAMA_GATEWAY.md`。

公司驗證：0008 schema backup SHA-256 `1056f00a8653b89c3d8acd5766f5a666b3d3f07300ac82294ccd1902130c09b8`；EDB 0009、公司 101 tests、Web／Worker、AI Gateway enabled 均正常。Job `774499b66693455eb16d14f04a5fd687` 使用真實 `gpt-oss:20b` 完成 ai_drafted→reviewed→approved→render，核准前 AI 文字未進報告，核准後 approved 文字進入 report-model。詳見 `docs/M14_1_VALIDATION.md`。

### M14.2：Section 審核工作台與受控 AI 批次

新增 `0010_m14_2_batches` additive migration，保存 batch 與逐項狀態。Web 只負責驗證並排入 EDB；既有 Worker 使用 `FOR UPDATE SKIP LOCKED` 領取一個 batch，依 ordinal 逐筆呼叫 M14.1 Gateway，並以 `OMNICHECK_AI_BATCH_MAX_ITEMS` 與 `OMNICHECK_AI_MIN_INTERVAL_SECONDS` 控制單批數量和呼叫間隔。Web 工作台提供載入、勾選、進度、工程師修改、核准與 approved render。AI disabled／失敗／revision conflict 均不覆寫 deterministic。完整設計見 `docs/M14_2_SECTION_REVIEW_AND_BATCH.md`。

本機驗證：103 tests 通過；瀏覽器確認桌面版工作台欄位、按鈕與 M14.2 版本正常。

### M14.3：全 V4 Section 自動 AI 草稿與 PEM Vision

新案件完成既有 Pipeline 後，Worker 依 V4 最終可見項目建立一對一 Section Workflow，並透過 `OMNICHECK_AI_AUTO_DRAFT_ALL` 自動將全部 generated 項目拆成受控批次。文字項目沿用 `gpt-oss:20b`；有圖片證據的 PEM 項目只在設定 `OMNICHECK_AI_VISION_MODEL` 時送往 Vision 模型，否則安全回退 deterministic。UI 新增整批核准並重新產報，但 Renderer 的 approved-only 原則不變。

本機／公司驗證：115 tests 通過；台灣行動支付原始資料唯讀 E2E 產生 29 個 V4 可見項目、29 個 Workflow 項目及 5 個圖片項目。公司以最近案件不可變 input 在獨立暫存輸出回歸：Ruleset 2026.2、QA／V4 QA、DOCX／PDF 通過；65% 的 `pemp1` 與 Witness 正確要求隨時觀察量體成長，table/index bloat 正確逐項列出 `VACUUM FULL`／`REINDEX`。公司 `current` 已切至 `a18c7cd`，rollback 為 `8bef579`；舊 Job Workflow 保留舊 ruleset，使用者驗收必須建立新案件。Vision 模型尚未提供，因此不得標示 Vision 驗收完成。完整設計與 rollback 見 `docs/M14_3_AUTOMATIC_REPORT_AI.md`。

公司候選：release `8031088`，0009 schema backup SHA-256 `83f675eb69adc3e8767acba9162631f0c25d3820c84e77311f8e2a66c5524f11`，EDB 已升至 `0010_m14_2_batches`，Web／Worker active。Batch `1b954283e6734c7fa9d93e569259f71b` 由 Worker `omnicheck-ai-app-57555` 完成，真實 request `c0f5cdee611047cca020b8269913246d` 使用 `gpt-oss:20b`，10.621 秒、693 tokens、fallback 0／conflict 0；Section 只變為 ai_drafted revision 2，selected source 仍 deterministic。舊 revision 建立 batch 回 409，未核准文字未進 report-model，QA／V4 QA 均允許交付。該 Golden Job 未設定 DOCX/PDF，因此本輪沒有 PDF regression；多項批次與使用者 UI 驗收仍待執行。

### PEM backend Database Output Scope 回歸修正

原因：Discovery 曾將 `20260616_PEM_check/20260616_DB_check.txt` 當成未映射 Database Output，預設建議業務 Primary；人工 mapping 又優先於既有 service path，導致 PEM backend 與業務 Primary 兩份不同 Database Output 同時解析為同一節點，最後在 EDB `uq_section_items_key` 發生重複。

修正：Discovery 在唯一 PEM Server 節點存在時自動建議該 Witness；Scope controller 以 `policy.pem_backend_database_scope` 防止舊的錯誤 Primary mapping 繞過；Section Workflow 在 persistence 前檢查 key 唯一性並提供明確錯誤。不得合併兩份內容不同的 Database Output。

驗證：commit／company release `8bef579`；本機與公司 VM 均 106 tests、V4 manifest 5/5 通過。原失敗 Job `871079e5936f4035bf975a241fb401a1` 未修改 `job.yaml` 或 13 個 input，保留錯誤 mapping 直接重跑後成功；PEM DB evidence 解析為 `pemp1 / Witness / excluded`，20/20 Section keys 唯一並持久化，QA／V4 QA delivery allowed，DOCX／PDF 產生完成。來源 aggregate SHA-256 前後皆為 `551d2498af7f456ad0b8f6550aad7b2356fd9e085787fb17ddd47c0eecea77aa`；Web／Worker active，warning journal 為零。Rollback 只需將 application symlink 指回 `8031088`，沒有 migration 或 EDB downgrade。

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

後續架構由 `docs/MILESTONE_ROADMAP.md` 與 `docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md` 核准；M10.1 已完成，下列項目為後續方向：

| 階段 | 預計內容 | 達成方式與主要驗收 |
|---|---|---|
| M10.2 | 同仁 UI Adapter | 新版 UI 接既有 API、`/classic` fallback、登入／Knowledge／GPDB 隔離、公司 E2E 與使用者驗收 |
| M10.3 | Section API 與審核 | 規則原文、固定模板、AI 草稿、人工修改／核准、版本與稽核紀錄 |
| M11 | 選配 Login／RBAC／客戶隔離／Audit | 現階段維持內網單一模式；需要時再加入 token、身份提供者、tenant enforcement 與稽核事件 |
| M12 | 歷史比較 | 依 customer／system／period 比較 normalized checks 與 assessment，產生趨勢 |
| M13.1 | CVE／Release Sync 與 Cache | 固定官方來源、排程 Worker、來源快照、freshness policy |
| M13.2 | Version Parser／Matcher | 確定性 product/version range、EDB backport、component 條件與 match reason |
| M13.3 | CVE V4 Section／Quality Gate | 環球晶圓方向版面、stale data 警告／阻擋、逐頁 QA |
| M14 | Ollama AI Gateway | 遮蔽後翻譯、摘要、觀察建議初稿與問答；完整 prompt/model/approval audit；AI 失敗時固定模板 fallback |
| M15 | 生產強化 | EFM／VIP、TLS `verify-full`、backup/restore、監控與故障演練 |

實際 Barman wrapper fixtures 仍待提供，但不阻擋 M10.2。未來每一階段都必須記錄範圍、migration、驗證、commit、tag、資料 rollback／forward-fix 與已知限制。
