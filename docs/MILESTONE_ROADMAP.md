# OMNIcheck AI 後續 Milestone Roadmap

最後更新：2026-08-13

目前狀態：M14.5 AI 完整交付流程已完成並部署。新案件必須完成全部適用 Section 的文字／PEM Vision 草稿、最終 DOCX／PDF 與 QA 後才顯示 succeeded；初版報告使用 AI draft，個別失敗項目回退 deterministic，工程師下載後再覆核與核准。

## 固定基礎

M1～M10.1 Pipeline 與 V4 Renderer 是已驗收基礎，不得因前端或 AI 整合而重做。Canonical JSON 保持 Pipeline 契約；EDB 保存結構化資料，`/data` 保存大型原始檔與報告。

## 後續順序

| Milestone | 目標 | 主要交付物 |
|---|---|---|
| M10.2 | 完成、已合併主線 | 同仁整合式 UI 接上既有 API；保留 `/classic` fallback；Login、Knowledge/CVE、GPDB 隔離 |
| M10.3.1 | 完成 | 版本化 Section JSON、規則原文、AI 草稿、人工審查／核准狀態與 fail-closed 選文 |
| M10.3.2 | 完成、公司 E2E 通過 | 相容 0005～0007 migration chain；EDB current state＋append-only revisions；Section review／approval API；approved-only Renderer |
| M11 | 選配身份與權限 | 預設內網單一使用模式；需要時再加入 API token、登入、RBAC、客戶隔離與 Audit |
| M12 | 公司 E2E 驗收完成 | 同客戶、同系統、同產品的 immutable Canonical JSON／deterministic assessment 比較；`history-comparison.json`、V4／PDF 歷史比較章節與 QA 已通過 |
| M13.1 | 公司 Cache 同步完成 | PostgreSQL Release／Security、EDB Advisory、NVD 補強入口、來源快照、sync run 與 stale policy；公司批次 NVD 排程待補 |
| M13.2 | 公司 E2E 驗收完成 | Primary-only Product／Version Parser、確定性 matcher、fixed／pending 狀態；EPAS Golden Job 產生 46 個 CVE |
| M13.3 | 公司 E2E 驗收完成 | V4 `version_updates`、CVE metadata gate、CVE artifact；23 頁 DOCX/PDF、V4 QA 通過；無登入 UI Job 同樣產生 CVE；僅顯示同 Major minor 更新路徑可修正 CVE |
| M14 | Ollama AI Gateway | 繁中翻譯、觀察／建議草稿、主管摘要、歷史摘要、Prompt／Model／輸出稽核與 fallback |
| M14.5 | 完成、公司實機驗收 | AI batch 納入 Job 完成條件；初版報告採 approved／AI draft／deterministic；完成後才提供 PDF／DOCX |
| M14.6 | 完成、公司效能驗收 | 文字／Vision 模型分流、圖片縮圖、短 Vision timeout、正常圖略過、有限圖片並行；實測約 6 分鐘 |

M14 分段：M14.1 已完成單一 Section 草稿、安全遮蔽、稽核與 fallback；M14.2 已完成前端批次操作、EDB durable queue、逐筆 rate limit 與人工審核體驗；M14.3／M14.4 完成全 Section Evidence 與 Gemma Vision；M14.5 將 AI 納入 Job 完成條件與初版報告。主管摘要、歷史摘要及問答留在後續階段。
| M15 | 正式環境強化 | VIP／EFM、TLS、Backup／Restore、Monitoring、Reverse Proxy、資源隔離與故障演練 |

## 不可跨越的責任邊界

- 前端只能透過 API 使用系統，不得直接讀寫 EDB 或直接啟動 Worker。
- Ollama／其他 AI 不得決定或修改 Product、Version、Primary、Topology、Scope、Rule Status、CVE Match、Canonical JSON 或 V4 contract。
- AI 停用或失敗時，固定模板仍必須能產生完整可交付報告。
- 初版報告可使用 AI 草稿；人工修改後以核准內容優先。規則原文、AI 草稿與核准版必須分開保存。
