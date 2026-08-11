# OMNIcheck AI 後續 Milestone Roadmap

最後更新：2026-08-11

目前狀態：M10.3.2 已完成公司 EDB／Web／Worker E2E；下一階段可開始 Ollama Gateway Adapter，但尚未啟用 AI。既有 Pipeline 不更換。

## 固定基礎

M1～M10.1 Pipeline 與 V4 Renderer 是已驗收基礎，不得因前端或 AI 整合而重做。Canonical JSON 保持 Pipeline 契約；EDB 保存結構化資料，`/data` 保存大型原始檔與報告。

## 後續順序

| Milestone | 目標 | 主要交付物 |
|---|---|---|
| M10.2 | 完成、已合併主線 | 同仁整合式 UI 接上既有 API；保留 `/classic` fallback；Login、Knowledge/CVE、GPDB 隔離 |
| M10.3.1 | 完成 | 版本化 Section JSON、規則原文、AI 草稿、人工審查／核准狀態與 fail-closed 選文 |
| M10.3.2 | 完成、公司 E2E 通過 | 相容 0005～0007 migration chain；EDB current state＋append-only revisions；Section review／approval API；approved-only Renderer |
| M11 | 選配身份與權限 | 預設內網單一使用模式；需要時再加入 API token、登入、RBAC、客戶隔離與 Audit |
| M12 | 歷史健檢比較 | 同客戶／系統跨期差異、改善／惡化、拓撲與設定變化、歷史摘要資料 |
| M13.1 | 官方 CVE／Release Sync | 固定官方來源、排程同步、EDB Cache、來源快照與 stale policy |
| M13.2 | Version Matcher | Product／Version Parser、確定性 CVE 適用性、fixed／pending 狀態 |
| M13.3 | CVE V4 Section | 環球晶圓方向版面、Quality Gate、來源與 matcher version |
| M14 | Ollama AI Gateway | 繁中翻譯、觀察／建議草稿、主管摘要、歷史摘要、Prompt／Model／輸出稽核與 fallback |
| M15 | 正式環境強化 | VIP／EFM、TLS、Backup／Restore、Monitoring、Reverse Proxy、資源隔離與故障演練 |

## 不可跨越的責任邊界

- 前端只能透過 API 使用系統，不得直接讀寫 EDB 或直接啟動 Worker。
- Ollama／其他 AI 不得決定或修改 Product、Version、Primary、Topology、Scope、Rule Status、CVE Match、Canonical JSON 或 V4 contract。
- AI 停用或失敗時，固定模板仍必須能產生完整可交付報告。
- 正式報告使用人工核准內容；規則原文、AI 草稿與核准版必須分開保存。
