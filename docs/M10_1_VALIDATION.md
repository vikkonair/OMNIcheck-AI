# M10.1 驗證紀錄

日期：2026-08-10  
候選 commit：`71173de`  
使用者驗收：2026-08-10 通過；公司 App VM 候選 release `be0ca80` 的 Web、Worker、EDB health、案件 API 與介面流程正常。

## 自動化驗證

- 本機完整測試：82 passed。
- 公司 App VM 使用候選 source 完整測試：82 passed。
- V4 vendor manifest：5/5 通過。
- 完整 V4 bundle：29 項 hash 通過。

## 實際 ENGDB 資料唯讀驗證

來源使用既有失敗案件 `da61393335dc4fbeb0c0b7e8ec4e6165` 的三個 input：`ENGDB_check.txt`、`OADB15N` OS output、`OADB15-DR` OS output。輸出放在來源目錄外，驗證前後來源 path、size 與 SHA-256 完全一致。

確認設定：`OADB15N` 為 Primary、`OADB15-DR` 為 DR，`ENGDB_check.txt` 以介面等價的明確 mapping 指定為 `OADB15N`。

結果：

- Scope：3 allowed、0 excluded、0 pending。
- Primary database logical checks：由修正前 0 項提升為 17 項。
- `evidence.primary_database_present` 與 `coverage.required_checks`：passed。
- QA：8/8 passed；V4 QA：passed。
- Database version：PostgreSQL 16.6。
- DOCX 約 52 KiB；PDF 約 214 KiB、19 頁。
- PDF 逐頁檢查沒有重疊、裁切、缺字或異常空白頁。

## 已知邊界

- `read_only = off` 不是 `pg_is_in_recovery() = false` 的等價證據，不能單獨證明 Primary。
- 舊式單檔沒有 hostname 時仍必須由工程師確認來源；系統只提出候選，不自動認定。
- 未來若 Collector 能直接附上 hostname、role 或 `pg_is_in_recovery()` metadata，應優先使用明確 metadata，減少人工映射。
