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
