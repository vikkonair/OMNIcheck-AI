# M10.3.1 Backend Section Workflow Foundation

日期：2026-08-11  
狀態：功能分支完成，待公司候選部署與使用者驗收

## 目的

在不改動 M1～M10.1 Pipeline、Canonical JSON 或 V4 Renderer 的前提下，建立可供未來 Ollama 使用的版本化 Section 文字工作流。確定性規則、AI 草稿、工程師審查與正式核准內容必須分開，AI 不得直接取代規則結果。

## 新契約

Pipeline 新增 `section-workflow.json`，契約名稱為 `omnicheck.section-workflow`、schema version 為 `1.0`。每個 item 保存：

- `section_key`、`section_id`、`check_id`、`node`
- 不可由 AI 改變的 `status`、evidence references 與 rule trace
- `deterministic` 固定模板文字
- 選配 `ai_draft`
- 工程師 `reviewed` 文字
- 正式 `approved` 文字
- `workflow_status`、`revision` 與 `selected_source`

狀態順序為 `generated → ai_drafted → reviewed → approved`。AI 草稿加入後，`selected_source` 仍是 `deterministic_template`；只有工程師審查並核准後才可選擇 approved 內容。

## Renderer 與 Artifact

- 本階段 `renderer_uses_ai=false`，V4 Renderer 仍讀既有 report model，報告內容與版面不變。
- `section-workflow.json` 登錄為 `section-workflow-json` Artifact。
- 建立 `assessment-json → section-workflow-json` 衍生關係。
- AI 關閉或未安裝 Ollama時，Pipeline、QA、DOCX 與 PDF 必須正常完成。

## EDB 與 rollback

本階段不新增 migration。公司 EDB 保留一個由暫停 M11 留下的 additive revision，而正式 main 尚未包含該 migration；為避免建立衝突的 Alembic branch，Section EDB tables 與 API 延後到 schema reconciliation 後實作。

Rollback 可直接切回 `m10.1` application；不需 database downgrade。舊版本會忽略新增的 JSON Artifact。

