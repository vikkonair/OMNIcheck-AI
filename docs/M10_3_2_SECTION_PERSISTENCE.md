# M10.3.2 Section Persistence 與審核閘門

## 目的

在 Ollama Gateway 前完成正式文字工作流。規則事實仍由 deterministic Pipeline 產生；AI 只能提供未受信任草稿，工程師修改後必須再次核准，Renderer 才能使用。

## Schema reconciliation

公司 EDB 目前 revision 為 `0007_m13_catalog`。該版本屬於同仁 source 的完整線性 migration：

`0004_m9_6 → 0005_m11 → 0006_m13 → 0007_m13_catalog`

Repository 已原樣納入 0005～0007 migration；三個檔案 SHA-256 分別為：

- 0005：`1c7d901e65c4959d24b07bd9402b96c5a36971e524cfcacf3c62d40048630aba`
- 0006：`fbef8453c5d5705d3abf213494ce199c9cb8d97145d840c347819c3662f5ca4a`
- 0007：`39a673917fe57c849d995dc7e5b5400d089f04918b68905722f1afee88c053ce`

不得用 `alembic stamp` 偽造 reconciliation。新 migration `0008_m10_3_sections` 只新增三張表，不修改或刪除 0001～0007 物件。

## 資料表

- `section_workflows`：每個 Job 一份 workflow header。
- `section_workflow_items`：每個 section 的 current projection，包含 deterministic、AI draft、reviewed、approved 與 selected source。
- `section_workflow_revisions`：每次 generated／ai_drafted／reviewed／approved 的 append-only snapshot、actor、timestamp 與 content SHA-256。

## 狀態與 Renderer 規則

`generated → ai_drafted（選配）→ reviewed → approved`

沒有 AI 時允許 `generated → reviewed → approved`。Renderer 只接受：

1. `approved`：使用核准內容。
2. 其他狀態：使用 deterministic template。

AI draft 或未核准的 engineer review 不得進入 DOCX／PDF。Product、Topology、Scope、Status、Evidence 與 Rule Trace 不可由文字 API 修改。

## API 與並行控制

寫入 API 都要求 `expected_revision` 與 `actor`。如果資料庫 current revision 已改變，回 HTTP 409；呼叫端必須重新讀取，不可盲目覆寫。

正式重新產報呼叫 `POST /api/jobs/{job_id}/sections/render`，其策略固定為 `approved_or_deterministic`。

## Rollback

- Application rollback：切回前一個 release，0008 tables 可保留且不影響舊版。
- Database rollback：正式環境不執行 downgrade；採 forward-fix。
- Data rollback：revision history 不更新舊列，錯誤核准應建立後續修訂與重新核准，不刪除 audit evidence。
