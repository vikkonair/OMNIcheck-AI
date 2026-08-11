# M14.2 Section 審核工作台與受控 AI 批次

## 目標

在不改動 M1～M10.1 Pipeline、Canonical JSON、規則判定與 V4 Renderer 契約的前提下，讓工程師可在 Web 介面完成 Section AI 草稿、人工修改、核准與重新產報。AI 是選配文字助理，停用或失敗時 deterministic 報告必須完整可用。

## 元件

- Web 工作台：載入 Job Sections、勾選候選、顯示批次進度、編輯 observation／recommendation、review、approve、render。
- `POST /api/jobs/{job_id}/ai-draft-batches`：驗證 actor、item、revision、狀態與單批上限後排入 EDB。
- `GET /api/jobs/{job_id}/ai-draft-batches/{batch_id}`：回傳 batch 與逐項狀態。
- `ai_draft_batches`：保存 queued／running／completed／partial／failed、計數、claim 與時間。
- `ai_draft_batch_items`：保存 ordinal、expected revision、ai_drafted／fallback／conflict、request ID 與錯誤。
- 既有 Worker：沒有 Pipeline Job 時領取一個 AI batch，單一 Worker 內依序執行，避免同時壓垮 Ollama。
- M14.1 Gateway：遮蔽 prompt、呼叫 Ollama、schema 驗證、audit 與 fallback。
- M10.3.2 Section Store／Renderer：optimistic revision、append-only history、approved-only overlay。

## 安全與一致性

- reviewed／approved Section 不得進入 AI batch。
- 建立 batch 與實際執行都檢查 revision；過期項目標記 conflict，不覆寫人工內容。
- AI 成功只建立 `ai_drafted` revision，`selected_source` 仍是 `deterministic_template`。
- AI 失敗標記 fallback；Section 本身不變。
- 每筆 Ollama 呼叫仍由 `ai_gateway_requests` 留存去識別 audit。
- 批次上限預設 5，合法範圍 1～20；逐筆間隔預設 1 秒。
- Worker 重啟後可回收逾時 running batch；revision gate 提供重複執行保護。

## Rollback

立即停用 AI：`OMNICHECK_AI_ENABLED=false` 並重啟 Web／Worker。Application 可切回 `m14.1`；0010 兩張表保留，不影響舊版。正式 EDB 不執行 downgrade，後續採 forward-fix。
