# M10.3.2 驗證紀錄

日期：2026-08-11

## 本機

- 完整 Pytest：97 passed。
- Alembic：單一 head `0008_m10_3_sections`。
- Golden approved overlay：核准文字進入 report-model／V4；QA、V4 QA 允許交付。
- AI disabled：generated 可直接 review；AI draft 與未核准 review 不進 Renderer。

## 公司 App VM／EDB

- 候選 Application release：`48eac67`。
- 前一版／Application rollback：`327748d`。
- Migration 前 revision：`0007_m13_catalog`。
- Migration 後 revision：`0008_m10_3_sections`。
- Migration 前 schema-only backup：`/data/omnicheck/archive/m10-3-2-pre-0008/omnicheck-schema-0007.sql`。
- Backup SHA-256：`18601b514507cf952616a152a0b91f602cf177a3e4c65e73d74dc2283863c2c6`。
- 公司候選測試：97 tests 完成至 100%。
- Web／Worker：active；`/api/health` 回 database／external worker。

新增表：

- `omnicheck.section_workflows`
- `omnicheck.section_workflow_items`
- `omnicheck.section_workflow_revisions`

## 公司 E2E

測試 Job：`774499b66693455eb16d14f04a5fd687`

- 3 個 Golden evidence 經 Web upload、EDB Queue、Worker 完成。
- Job 狀態 succeeded，輸出 12 個 Canonical／V4 artifacts。
- AI provider disabled，建立 3 個 deterministic Section items。
- 未建立 AI draft，直接 engineer review 成功；selected source 仍為 deterministic。
- 舊 revision approval 回 HTTP 409。
- 正確 revision approval 後 selected source 為 approved。
- `/sections/render` 回 `approved_or_deterministic`。
- 核准觀察與建議已出現在 report-model。
- Revision actions：`generated → reviewed → approved`。
- 其他未核准 Section 維持 deterministic。

## Rollback／Forward-fix

Application 可把 `current` 切回 `327748d` 並重啟服務。0008 為 additive tables，舊 Application 不會使用，保留即可；正式 EDB 不執行 downgrade。若 0008 發現問題，建立後續 forward-fix migration。Revision history 不刪除；錯誤內容以新 review／approval 修正。

## 結論

M10.3.2 驗證成功。系統已準備好下一階段 Ollama Gateway Adapter，但本階段沒有安裝、呼叫或啟用 Ollama。
