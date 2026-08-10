# M10 Validation Report

日期：2026-08-10  
分支：`feature/m10-topology-discovery`  
狀態：Passed；本機、瀏覽器與台灣行動支付實際資料唯讀驗證完成，公司 `.77/.81` 尚未部署

## 自動化驗證

- 完整 Pytest：78 passed。
- Discovery／Web／Topology targeted tests：19 passed。
- V4 bundle 29 個必要檔案與 hash：passed。
- `git diff --check`：passed。

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

## 已確認限制

- Discovery 是候選產生器，不是無人審核的自動決策器。
- 非標準檔名、缺少 OS／EFM 訊號或角色衝突時必須人工指定。
- 圖片不做 OCR；未標節點監控圖片仍依既有政策映射 Primary。
- 本次沒有新增 EDB migration；公司部署與 Queue／Worker E2E 留待使用者驗收後執行。

## 結論

M10 沒有修改 M1～M9.6 Pipeline 或 V4 Renderer。自動探索、人工確認、稽核來源、fail-closed gate 與實際資料端到端驗證均通過；目前仍是功能分支，正式 rollback 基準維持 `m9.6`。
