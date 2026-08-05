# OMNIcheck AI

OMNIcheck AI 是一套針對 PostgreSQL 與 EDB Postgres Advanced Server（EPAS）的資料庫健檢自動化系統。

目前正式版本已完成至 **M8.1：Golden Regression、Witness 元件與多備份工具架構**，並正在開發 **M9：Web UI 與案件管理**。M9.3 已在公司 CentOS 9 App VM 與 EPAS 17.10 完成 core deployment、EDB queue、systemd、Golden DOCX/PDF 與重啟持久性驗證；正式安全設定與實際客戶資料驗證仍待完成。系統可以讀取客戶提供的 OS、PostgreSQL／EPAS、EFM、PEM、XDB、pgBackRest、Barman 及監控資料，辨識節點拓撲與資料範圍，將不同格式的證據轉換為統一結構，依據版本化規則產生可追溯的健檢判斷，並輸出通過品質驗證的 V4 DOCX／PDF 報告。

> `main` 與 `m8.1` tag 是目前正式可回復版本；M9 功能先在 `feature/m9-web-job-management` 分支開發與驗證。

## 目前可以做到什麼

- 掃描輸入資料夾並建立完整檔案清冊及 SHA-256 雜湊值。
- 辨識 Primary、Standby、DR 與 Witness 節點。
- 辨識各節點承載的 EFM、PEM、XDB 與備份服務。
- 解析 OS、PostgreSQL／EPAS、EFM、PEM、XDB、pgBackRest、Barman 與資料庫邏輯資料。
- 將不同來源和格式的資料轉換成統一的標準化 JSON。
- 控制不同類型資料的檢查範圍，避免錯誤使用 Standby、DR 或 PEM 後端資料庫資料。
- 比較 Primary、Standby 與 DR 的 PostgreSQL 參數和 `pg_hba.conf` 規則。
- 依據確定性規則產生「正常、注意、嚴重、待確認」四種狀態。
- 為每項判斷保留證據、觀察、結論、建議、規則編號與規則版本。
- 在輸出前遮蔽密碼等敏感資訊。
- 產生檢查覆蓋率清單，讓缺漏項目保持可見。
- 在交付前檢查 Primary 資料、證據引用、敏感資訊、來源路徑與客戶資料隔離。
- 產生九興 V4 方向的 DOCX 與 PDF 正式報告。
- 使用去識別 Golden Dataset 防止 Parser、Scope、規則與報告版面回歸。
- 透過 M9 Web API 建立案件、上傳不可覆寫的原始證據、執行既有 Pipeline、查詢狀態及下載輸出。
- 可選用 EDB／PostgreSQL 保存案件 metadata，透過獨立 Worker 與資料庫佇列可靠執行、重試及保留事件紀錄。
- 後續已核准採用 EDB 中心化架構：EDB 保存結構化應用資料與歷史、`/data` 保存大型檔案、Canonical JSON 繼續作為 Pipeline 契約與 rollback 保護層；目前仍待 M9.4～M9.6 分階段實作。

目前規則涵蓋：

- 檔案系統使用率
- Transaction ID 年齡
- Idle transaction
- Replication 狀態
- Dead tuple、Table bloat 與 Index bloat
- 低使用率索引
- pgBackRest 備份異常
- Schema 與 Role 權限
- 跨節點 PostgreSQL 參數一致性
- 非本機 `pg_hba.conf trust` 規則

## 標準架構與資料範圍

OMNIcheck AI 將節點的基礎設施角色與節點上執行的服務分開處理。

標準 EDB 架構可包含：

- **Primary**：主要業務資料庫，也是資料庫邏輯層判斷的主要依據。
- **Standby**：同步或複製節點。
- **DR**：災難復原節點。
- **Witness**：可承載 PEM、EFM、XDB、Barman，以及 PEM 使用的後端 PostgreSQL。

資料範圍採用以下原則：

- Database、Schema、Table、Role、Extension、Transaction、Bloat 等資料庫邏輯資料，只使用當前 Primary 的證據。
- `postgresql.conf`、`postgresql.auto.conf` 與 `pg_hba.conf` 屬於節點層級設定，因此會納入 Primary、Standby 與 DR，並進行跨節點比較。
- 備份 Output 使用明確指定的 provider／node；未指定時 pgBackRest 預設採 Primary。
- Witness 的 OS、PEM、EFM、XDB、Barman 與監控證據可納入檢查。
- Witness 上的 PEM 後端 PostgreSQL 不會被誤認成客戶主要業務資料庫。
- 無法確認節點或資料領域的證據不會被自動採用，而會標示為 `pending`。

## 處理流程

```text
客戶原始資料
    ↓
檔案清冊與雜湊
    ↓
節點拓撲與服務辨識
    ↓
資料範圍控制
    ↓
格式解析與標準化
    ↓
跨節點設定比較
    ↓
確定性規則判斷
    ↓
結構化健檢結果與 V4 報告
```

規則門檻及政策清單存放於 `config/rules.default.yaml`，由 Python 規則引擎執行。AI 不負責選擇 Primary、改變證據範圍、修改判斷狀態或憑空產生發現。

## 輸出內容

執行完成後會在輸出資料夾產生：

- `inventory.json`：輸入檔案清冊、分類與雜湊值。
- `topology.json`：節點角色及其承載的服務。
- `scope-ledger.json`：每項證據是否納入檢查，以及納入或排除的原因。
- `normalized.json`：解析並轉換後的標準化健檢資料。
- `configuration-comparison.json`：各資料庫節點之間的參數與 HBA 規則差異。
- `assessment.json`：規則引擎產生的狀態、觀察、結論、建議及證據引用。
- `coverage-ledger.json`：各節點應檢查項目、現有證據、缺漏項目與覆蓋率。
- `qa-result.json`：交付品質閘門的通過／失敗結果與診斷資訊。
- `report-model.json`：供報告組裝使用的標準模型。
- `v4-report.json`：V4 Renderer 的報告資料契約。
- `v4-qa-result.json`：正式報告輸出前的 V4 品質閘門。
- `report.docx`：可編輯的正式健檢報告。
- `report.pdf`：可交付的正式健檢報告。

## 本機安裝

需要 Python 3.12 或更新版本。

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

執行範例：

```bash
.venv/bin/omni-healthcheck generate \
  --job config/job.example.yaml \
  --rules config/rules.default.yaml \
  --input ./input \
  --output ./output
```

其中：

- `--job`：客戶、節點角色與服務的工作設定。
- `--rules`：規則門檻及檢查政策。
- `--input`：客戶原始健檢資料夾。
- `--output`：結構化結果的輸出資料夾。

## 使用 Docker

```bash
docker compose run --rm omni-healthcheck generate \
  --job /app/config/job.example.yaml \
  --rules /app/config/rules.default.yaml \
  --input /data/input \
  --output /data/output
```

請依照 `compose.yaml` 掛載或替換輸入與輸出資料夾。

## M9 Web 介面（開發中）

啟動本機服務：

```bash
OMNICHECK_DATA_ROOT=./data/jobs \
  .venv/bin/omni-healthcheck-web
```

開啟 `http://127.0.0.1:8000` 後，可透過圖形化表單設定客戶與節點、選取整包健檢資料、一鍵執行 Pipeline，並從結果頁下載輸出；不需手寫 JSON 或使用 Terminal。互動式 API 文件仍保留於 `http://127.0.0.1:8000/docs`。

未設定資料庫連線時，M9 使用本機檔案系統與 FastAPI 同程序背景工作；設定 `OMNICHECK_DATABASE_URL` 後，則由 EDB／PostgreSQL 保存案件狀態，並由獨立 Worker 領取及重試工作。權限控管與辨識結果確認頁面仍在後續 M9 階段。

## 開發與驗證原則

- 客戶原始資料必須維持唯讀，不得修改。
- 每個 milestone 完成後都必須使用指定的實際客戶資料進行驗證。
- 每項健檢判斷必須能追溯到可見證據。
- Primary 身分不明確或判斷缺少證據時，應停止或標示待確認，不可猜測。
- 客戶資料、輸出結果及機敏資訊不得提交至 Git 儲存庫。
- Parser 與規則必須具備自動化測試。

詳細規範請參閱：

- `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.md`：從空白 VM 重建、部署、驗證、維運與回復的權威主手冊
- `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.docx`：可傳承與交付的主手冊文件版
- `docs/PROJECT_RUNBOOK.md`：M1 至目前及後續持續更新的專案手順
- `docs/PIPELINE_SPEC.md`
- `docs/ACCEPTANCE_CRITERIA.md`
- `docs/MILESTONE_VALIDATION.md`
- `docs/RULE_PROVENANCE.md`
- `docs/REPORT_REFERENCE_POLICY.md`
- `docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md`：M9.4～M15 的 EDB 中心化、CVE 與 AI 責任邊界決策

## 專案進度

- M1：檔案清冊與基礎 CLI
- M2：節點拓撲與資料範圍控制
- M3：標準資料模型與 Parser 架構
- M4：完整資料解析與跨節點設定比較
- M5：確定性健檢規則引擎
- M6：檢查覆蓋率、安全性與交付品質驗證
- M7：正式 DOCX／PDF 健檢報告（已完成）
- M8：去識別 Golden Dataset 與端對端回歸測試（已完成）
- M8.1：Witness 元件 Registry 與多備份工具架構（已完成）
- M9.1～M9.2：Web API、案件管理與圖形化操作流程（已完成）
- M9.3：EDB metadata、可靠工作佇列與獨立 Worker（公司 core deployment 驗證完成，待安全強化與實際客戶資料驗證）
- M9.4～M9.6：EDB 應用資料、Pipeline 結果與 Artifact Registry
- M10～M12：拓撲確認、登入／RBAC／隔離／稽核、歷史比較
- M13.1～M13.3：官方 CVE／Release Cache、確定性 Version Matcher、CVE V4 Section
- M14～M15：選配 AI Gateway 與正式 HA／VIP／TLS／Backup／Monitoring 強化

報告版面將以核准的現代健檢報告方向製作；CVE 區段則以指定的環球晶圓報告樣式為主要參考。
