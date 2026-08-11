# M14.2 Validation

日期：2026-08-11

## 已完成（本機）

- 103 tests 全數通過。
- SQLite integration 驗證 batch API 202／queued、Worker 順序處理、兩筆 ai_drafted、EDB audit 與 deterministic selected source。
- AI disabled 時建立 batch 回應 409，deterministic Section 不變。
- Web contract 驗證審核工作台、textarea、batch endpoint 與 approved render 控制。
- 內建瀏覽器實際載入 `M14.2 candidate`，DOM 與桌面 viewport 確認 Job ID、actor、載入、批次、重新產報控制項無溢位。

## 公司環境待驗證

- 0009 schema-only backup 與 SHA-256。
- `alembic upgrade 0010_m14_2_batches`。
- 公司 Web／Worker 重啟與 health。
- 真實 `gpt-oss:20b` 2～3 Sections 批次、進度、audit、fallback／conflict。
- review→approve→render 與未核准 deterministic 對照。
- 指定實際客戶資料唯讀 Golden／PDF regression 與來源 SHA-256 不變。
- application rollback 至 `m14.1`；0010 tables 保留。

公司項目尚未執行，因此不得視為正式驗收完成。
