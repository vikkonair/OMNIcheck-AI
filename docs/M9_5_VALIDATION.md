# M9.5 Validation Report

日期：2026-08-05
分支：`feature/m9-5-pipeline-result-persistence`
狀態：本機與實際客戶資料唯讀驗證通過；公司 `.81` 尚未部署

## 自動化驗證

- Targeted：18 passed；完整 regression：70 passed。
- PostgreSQL offline `0002_m9_4 ↔ 0003_m9_5`：成功。
- `git diff --check`：passed。

已驗證 row-level 查詢、tenant 隔離、Canonical hash 冪等、缺檔拒絕、Persistence failure 不會 succeeded，以及 legacy Job 相容。

## 實際客戶資料唯讀驗證

台灣行動支付 2026 上半年輸出與 SQLite 全部位於 temporary directory。

| 項目 | 結果 |
|---|---:|
| Source files／manifest | 14／前後一致 |
| Snapshot first write／retry | created／existing |
| Scope／Normalized／Unparsed／Config | 14／125／5／89 |
| Assessments／Coverage／QA | 19／76／2 |

Canonical SHA-256：`461ca163b98335ebf04ae7f250af7de33178f81081a00ffcf3c6e2f1091a113d`。

## 結論

本機與實際資料驗證通過；公司 EPAS 尚未執行 `0003_m9_5` 或 live scoped Job E2E，因此正式版本仍是 `m9.4`。
