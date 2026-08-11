# M14.2 Validation

日期：2026-08-11

## 已完成（本機）

- 103 tests 全數通過。
- SQLite integration 驗證 batch API 202／queued、Worker 順序處理、兩筆 ai_drafted、EDB audit 與 deterministic selected source。
- AI disabled 時建立 batch 回應 409，deterministic Section 不變。
- Web contract 驗證審核工作台、textarea、batch endpoint 與 approved render 控制。
- 內建瀏覽器實際載入 `M14.2 candidate`，DOM 與桌面 viewport 確認 Job ID、actor、載入、批次、重新產報控制項無溢位。
- 維運手冊 DOCX 已重建並 render 24 頁；頁面幾何、表格與新增 13.15 區段無裁切，但本機 bundled LibreOffice 無法顯示既有 `Microsoft JhengHei` 繁中字型。此項不標示為完整視覺 gate 通過，需在具該字型的 Word／LibreOffice 環境補驗。

## 公司環境已完成

- Release：`8031088`；Web／Worker active，health 顯示 database／external worker／AI enabled。
- 0009 schema-only backup：`83f675eb69adc3e8767acba9162631f0c25d3820c84e77311f8e2a66c5524f11`。
- EDB：`0010_m14_2_batches (head)`。
- Batch：`1b954283e6734c7fa9d93e569259f71b`，queued→completed，成功 1／fallback 0／conflict 0。
- Ollama request：`c0f5cdee611047cca020b8269913246d`，`gpt-oss:20b`，10.621 秒，693 tokens，sanitized prompt 使用 `[NODE]`。
- 成功後 Section 為 ai_drafted revision 2，selected source 仍為 deterministic。
- 使用 revision 1 再建 batch 回 HTTP 409。
- 重新 render 採 `approved_or_deterministic`，report-model 未出現未核准 `[NODE]` 草稿；QA／V4 QA 均為 delivery allowed。
- 公司首頁顯示 `M14.2 candidate` 與「Section 審核工作台」；服務自部署後無 warning journal。

## 尚待驗證

- 現有 Golden Job 只有一個 eligible generated Section；需新測試 Job 才能完成同批 2～3 項及逐項間隔驗收。
- 工程師需在公司瀏覽器完成實際 textarea 修改、review、approve 與下載操作驗收。
- 本次 Golden Job 未設定 DOCX/PDF，因此沒有 PDF 頁面 regression；後續以指定實際客戶資料補做。
- application rollback 至 `m14.1` 的實際演練；設計上 0010 tables 保留。

M14.2 尚未建立正式 tag，不視為正式 milestone 完成。
