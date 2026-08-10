# M10.1 舊格式 Database Output 分類與來源確認

日期：2026-08-10  
狀態：功能分支完成，待使用者驗收

## 目的

改善 `ENGDB_check.txt` 等舊式單檔資料庫輸出：檔名或路徑沒有 hostname 時，系統仍能辨識它是 Database Output，並要求使用者明確指定來源節點。這項功能不改變 Primary-only 規則，也不讓系統猜測 Primary。

## 判斷流程

1. Discovery 讀取文字檔前 512 KiB。
2. 內容同時命中至少兩組資料庫特徵時，將檔案列為 Database Output 候選。特徵包括資料庫版本、database list、`pg_stat_activity`、`pg_hba`、重要參數等 section。
3. 若檔案無法從路徑、檔名或內容唯一對應節點，Discovery 回傳 `evidence_candidates`，包含建議節點、信心、理由與待確認狀態。
4. Web 顯示「Database Output 來源確認」下拉選單；使用者必須選擇實際來源節點。
5. 確認結果寫入 Job config 的 `evidence_mappings`，Scope ledger 記錄來源為 `operator_confirmed_evidence_mapping`。

## Scope 保護

- 映射到 Primary：可供 Database／Schema／Table／Index／Role／Transaction 等邏輯檢查使用。
- 映射到 Standby、DR 或 Witness：檔案來源會被記錄，但邏輯資料仍由 Primary-only policy 排除。
- `postgresql.conf`、`postgresql.auto.conf`、`pg_hba.conf` 的跨節點比較規則維持不變。
- 無人工確認時保持 pending，不得用建議節點直接執行正式判斷。

## 回復

M10.1 沒有 migration、新套件或新環境變數。若發生回歸，可將 application 切回正式 `m10`；EDB 不需 downgrade，既有 Canonical JSON 與案件資料不受影響。

