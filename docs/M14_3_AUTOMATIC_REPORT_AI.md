# M14.3 全報告自動 AI 草稿與 PEM Vision 分流

## 目標

使用者只需執行一次案件。Pipeline 完成後，系統自動為 V4 報告中每一個可見項目建立 Section Workflow，並將所有 generated 項目分批排入既有 EDB AI Queue，不再逐項點選產生草稿。

## 執行流程

1. M1～M7 仍依既有確定性 Pipeline 產生事實、狀態、Output、觀察與建議。
2. V4 Adapter 完成後，依 V4 可見項目建立一對一 Workflow。
3. Worker 以 `OMNICHECK_AI_AUTO_DRAFT_ALL` 決定是否自動建立受控批次。
4. 文字 Section 使用 `OMNICHECK_AI_MODEL`；圖片 Section 使用 `OMNICHECK_AI_VISION_MODEL`。
5. Vision 未設定、AI 停用或模型失敗時，保留 deterministic 內容，整份報告仍可正常產生。
6. AI 草稿仍不會直接進正式報告。工程師可個別修改，或使用整批核准動作後重新產報。
7. Renderer 只選取 approved 內容；其他狀態一律使用 deterministic 內容。

## 安全與責任邊界

- AI 不得變更 Primary、Topology、Scope、規則狀態、Output 或 V4 版面。
- Prompt audit 不保存圖片的 Base64 內容；只保存最小化、遮蔽後的文字 Prompt 與雜湊。
- 圖片看不清楚時必須標示待確認，不得猜測數值。
- 膨脹項目的 AI 草稿必須保留確定性規則列出的所有物件與 `VACUUM FULL`／`REINDEX` 處置。

## 設定

```bash
OMNICHECK_AI_AUTO_DRAFT_ALL=true
OMNICHECK_AI_VISION_MODEL=<支援 OpenAI image_url 格式的 Ollama 模型名稱>
```

若沒有 Vision 模型，省略 `OMNICHECK_AI_VISION_MODEL` 即可。此時圖片項目會記錄 fallback，文字項目仍可正常產生 AI 草稿。

## 驗證與 rollback

本機與公司 VM 自動測試 115 項通過。台灣行動支付原始資料唯讀 E2E：V4 可見項目 29、Workflow 29、圖片 Workflow 5，數量一致。公司 `a18c7cd` 候選部署的 Ruleset 2026.2、QA／V4 QA、DOCX／PDF 回歸成功；待使用者以新案件驗收。舊案件保留建立當時的 Workflow／ruleset，不以重新 render 覆寫歷史。

Rollback 不需調整 EDB schema：將 `OMNICHECK_AI_AUTO_DRAFT_ALL=false` 後重啟 Worker，即回到 M14.2 的人工選取批次模式；或直接停用 `OMNICHECK_AI_ENABLED`，整套系統仍使用 deterministic 內容產報。
