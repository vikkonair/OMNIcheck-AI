# M14.4 證據式全 Section AI 分析

## 目標

除純資訊清冊與暫緩的圖片 Vision 項目外，每個 V4 Section 都將當期可見 Output、確定性狀態、觀察與建議基準送入 Ollama。AI 依證據產生觀察與建議初稿，工程師負責修改、覆核與核准。

## 契約

- `SectionWorkflowItem.evidence_snapshot` 保存建立 Workflow 當下的 V4 可見 Evidence。
- 欄位為 optional，既有案件沒有 snapshot 仍可讀取及使用 deterministic fallback。
- EDB 使用既有 JSON payload 保存，不新增 migration。
- 純資訊清冊不建立 Workflow，因此不送 Ollama。
- 圖片只保存 media reference；文字 Prompt 不含圖片路徑或 Base64。Vision 驗證依使用者決策暫緩。

## Prompt 安全與邊界

- 傳送前遮蔽 node、IPv4、email、password、secret、token、API key 與連線字串帳密。
- 排除 `path`、`data`、`image_base64`。
- 大型表格超過 Prompt 預算時保留前 40 筆與後 10 筆，並標記原始與納入筆數；大型文字保留前後內容並標記受控截斷。
- AI 不得改變狀態、Primary、Scope、數值、事實或確定性規則。
- 證據不足時必須標示待確認，不得猜測。
- 未通過必要事實驗證、模型失敗或 AI 關閉時，保留 deterministic 內容。
- Renderer 只使用工程師 approved 內容；未核准 AI 草稿不進正式報告。

## 驗證

台灣行動支付實際資料產生 25 個非資訊 Workflow：20 個文字 Section 與 5 個圖片 Section。25 個項目皆保存 Evidence Snapshot；20 個文字 Section 無缺漏。大型資料表、SLRU、Dead Tuple、PEM／EFM 摘要 Prompt 均包含當期可見表格。純資訊清冊仍為系統組態、版本、Extension、資料庫清單。QA／V4 QA 通過。

## Rollback

本功能沒有 migration。部署前先上線相容基準 `419d0df`，其 Workflow model 會忽略未認識的 additive JSON 欄位；正式功能版可安全回切此基準並讀取含 `evidence_snapshot` 的新案件。回切後 Evidence Snapshot 不參與 AI Prompt，但 deterministic、review／approval 與 Renderer 仍可運作；既有案件及 approved revision 不得覆寫。
