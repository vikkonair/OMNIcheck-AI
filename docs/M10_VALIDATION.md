# M10 Validation Report

日期：2026-08-10  
分支：`feature/m10-topology-discovery`；正式合併後為 `main`／`m10`
狀態：Passed；本機、使用者驗收、實際資料與公司 `.77/.81` 部署驗證完成

## 自動化驗證

- 完整 Pytest：78 passed。
- Discovery／Web／Topology targeted tests：19 passed。
- V4 bundle 29 個必要檔案與 hash：passed。
- `git diff --check`：passed。

## 公司環境部署驗證

- App VM：CentOS 9 `.77`；EDB：EPAS 17.10 `.81`；release `6e8ee6e`。
- 部署前 EDB custom-format backup：`omnicheck_app_pre_m10_20260810.dump`，67 KiB，SHA-256 `1f4c09585a7c505fa76f563012f0b428ec9790a0a36c64f13a980cec7da502f3`；`pg_restore --list` passed。
- Release archive SHA-256：`2e8bf41e5806662e337050258d3ea9480dffe6ad51d1b1b66015353802c06cdf`，上傳前後一致。
- VM 完整 Pytest：78 passed；V4 bundle 5 項 manifest/hash checks 全數通過。
- 公司端到端 Job：`12c90aa3da354f1c83dbc42e6d57e118`，13 inputs、13 outputs、1 attempt、status `succeeded`。
- Discovery：5 nodes、1 Primary candidate、0 unresolved nodes；6 張未標節點監控圖片依既有 Primary 規則處理。
- `topology.json` confirmation source：`operator_confirmed_discovery`；QA 與 V4 QA 均 passed。
- 重啟 `omnicheck-web`／`omnicheck-worker` 後兩者均 active，health 為 database metadata／external worker，Job 與 13 outputs 可由 EDB 正常讀回，journal 無 error。
- EDB revision 維持 `0004_m9_6`；M10 不新增 migration。

## 實際客戶資料

來源：台灣行動支付 `20260616 (1)`，全程唯讀。

- 13 個有效檔案；來源與 Web upload SHA-256 manifest 完全一致。
- 自動提出 5 台節點：`twmpedbp1` Primary、`twmpedbp2` Standby、`twmpedbdr1` DR、`pemp1` Witness／PEM、`twmpedbwitness` Witness／EFM。
- Primary 候選 1；未決節點 0；6 個未標節點檔案為監控圖片，沿用既有 Primary 規則。
- 未勾選確認時，Web 正確拒絕建立案件。
- 最終確認案件 `59fc97bc093a4c96a5e1ac2100023b95` succeeded。
- 產出 13 個 outputs，包含 Canonical、QA、V4 JSON、DOCX 與 PDF。
- QA 8／8 passed；V4 QA delivery allowed。
- 正式 `topology.json` Primary 為 `twmpedbp1`，角色來源為 `operator_confirmed_discovery`。
- 2.1 架構總覽的 Database 是節點安裝清冊，不套用 Primary-only Scope：Primary／Standby／DR 均顯示 `EDB Postgres Advanced Server`，`pemp1` PEM Server 顯示 `PostgreSQL`，純 EFM Witness 留白；PDF 第 4 頁目視通過。

## 已確認限制

- Discovery 是候選產生器，不是無人審核的自動決策器。
- 非標準檔名、缺少 OS／EFM 訊號或角色衝突時必須人工指定。
- 圖片不做 OCR；未標節點監控圖片仍依既有政策映射 Primary。
- 本次沒有新增 EDB migration；若需 rollback，可切回 `m9.6` application，不需 database downgrade。

## 結論

M10 沒有重做 M1～M9.6 Pipeline，也沒有改變 V4 Renderer 契約。自動探索、人工確認、稽核來源、fail-closed gate、公司 Queue／Worker、報告與重啟持久性均通過；正式版本為 `main`／`m10`，前一個 rollback 基準為 `m9.6`。
