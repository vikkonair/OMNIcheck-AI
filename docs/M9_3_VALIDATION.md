# M9.3 EDB Queue 與 Worker 驗證

驗證日期：2026-08-04

## 自動化結果

- 全部測試：56 項通過
- Filesystem M9 模式：保留且通過
- Database metadata CRUD：通過
- PostgreSQL dialect：產生 `FOR UPDATE SKIP LOCKED`
- 單一案件不可被兩個 Worker 同時 claim：通過
- Worker heartbeat／lease owner 驗證：通過
- Stale worker lease recovery：通過
- 失敗退避與重新排隊：通過
- 第三次失敗後轉為 failed：通過
- Job event audit trail：通過
- Database-backed Web 不使用 in-process task：通過
- EDB 無法連線時 health endpoint 回傳 503：通過
- queued／running／failed 案件不得列出或下載部分輸出：通過
- 獨立 Worker 執行既有 Pipeline：通過
- Alembic PostgreSQL offline SQL：成功產生 schema、tables、indexes、foreign key 與 version table
- V4 bundle 29 項 hash：通過

## 台灣行動支付實際資料

實際客戶來源維持唯讀，metadata database 使用隔離的測試資料庫；未連線至公司 `.81` EDB。

- 有效上傳：13 個檔案
- Job 在 Worker 啟動前保持 queued：通過
- 獨立 Worker claim：通過
- Scope：2 excluded、0 pending
- M6 QA：`delivery_allowed = true`
- DOCX／PDF：成功產生
- Job events：created、upload updates、queued、claimed、completed
- 來源資料執行前後 14 個檔案 SHA-256 清單一致

## 尚待公司環境驗證

- 在 `192.168.118.81:5444` 執行 Alembic migration
- 從 `192.168.118.77` 使用 pgpass 連線
- systemd Web／Worker 啟停與開機自動啟動
- Worker 中斷後 stale lease recovery
- EFM failover／未來 VIP 後的重新連線
- LibreOffice 與繁體中文字型

上述遠端驗證需要使用者另行授權，且不需要將密碼貼入聊天或提交 Git。完成前不建立 `m9.3` 正式 tag，也不合併至 `main`。
