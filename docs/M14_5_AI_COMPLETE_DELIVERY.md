# M14.5 AI 完整交付流程

## 目標

使用者看到案件「健檢完成」及 PDF／DOCX 下載連結時，所有適用 Section 的 Gemma 觀察與建議必須已完成並納入初版報告。AI 不再是案件完成後的背景附加工作。

## 執行順序

1. 執行既有 Inventory、Topology、Scope、Parser、Rules、Coverage、QA 與 V4 組裝。
2. 將 Section Workflow 寫入 EDB，為全部 generated 項目建立 durable AI batches。
3. Worker 在同一個 Job lease 內逐批執行文字與 PEM Vision 分析。
4. 成功項目保存為 `ai_drafted`；失敗項目記錄 audit／fallback 並保留 deterministic。
5. 以 `approved → ai_draft → deterministic` 優先順序重新產生 DOCX／PDF。
6. 最終 QA 通過後，Job 才由 running 轉為 succeeded 並提供下載。

## 審核與安全邊界

- AI 仍不得改變 Product、Topology、Primary、Scope、Status、Evidence、Rule Trace 或門檻。
- AI draft 進入初版報告不代表工程師核准；EDB 仍分開保存 deterministic、AI、reviewed、approved revision。
- 工程師修改的 reviewed 文字只有 approval 後才取代 AI draft。
- AI disabled 時維持 deterministic-only 並正常完成案件。
- 單一 AI 項目失敗不阻斷整份報告，該項使用 deterministic fallback。
- Job retry 會沿用既有 terminal batches 與 revisions，不重複覆寫已保存的 AI／工程師內容。

## Rollback

本變更沒有 migration。Application 可回切前一版；EDB 中既有 Workflow、Batch、Audit 與 revision 保留。回切後會恢復「Pipeline 先完成、AI 背景執行、未核准草稿不進報告」的舊行為，因此 rollback 後的新案件輸出語意不同，必須在操作公告中明確說明。

## 公司實機驗收

2026-08-12 已部署 main release `e6e31f2` 至公司 App VM，application rollback 為 `4c755b7`，不需 EDB migration 或 downgrade。全新 Job `2c0d700694d4472c8c218e79d40e52a4` 在 AI batches 未終止前保持 `running`，outputs 為空且 PDF endpoint 回 HTTP 409；最終成功後才產出 DOCX／PDF。25 個可分析 V4 Section 中，21 個套用 AI draft，4 個使用 deterministic fallback；`renderer_uses_ai=true`，QA 與 V4 QA 均通過。

## M14.6 效能調校候選

- 文字預設使用 `gpt-oss:20b`；2026-08-12 無客戶資料的固定 JSON benchmark 約 12.3 秒，`gemma4:26b` 約 12.2 秒，`nemotron-3-ultra:cloud` 約 37.3 秒。兩個前者皆符合 JSON 與 `結論：` 格式，故不採 Nemotron 作為預設文字模型。
- Vision 仍使用 `gemma4:26b`，但 timeout 改為獨立預設 35 秒、最多嘗試一次；文字仍維持獨立的 timeout／retry 政策。
- Vision request 只在記憶體中把可解碼圖片縮至最長邊 1280 px、JPEG quality 75；原始 PEM 證據與 SHA-256 不修改。
- `normal` PEM 圖預設維持確定性敘述而不送 Vision；`attention`／`critical`／`pending` 才送入 Vision。每個 batch 的 Vision concurrency 預設上限為 2。
- 此調校不改變 Primary、Scope、Rules、V4 contract 或「完成後才可下載」語意。需以新 Job 在公司環境驗證實際模型吞吐與 fallback 比例。
