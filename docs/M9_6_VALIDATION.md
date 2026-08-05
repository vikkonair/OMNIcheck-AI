# M9.6 Validation Report

日期：2026-08-05
分支：`feature/m9-6-artifact-lifecycle`
狀態：本機與實際客戶資料唯讀驗證通過；公司 `.77/.81` 尚未部署

## 自動化驗證

- 完整 regression：74 passed。
- PostgreSQL offline `0003_m9_5 ↔ 0004_m9_6`：成功。
- V4 bundle hashes 與 `git diff --check`：passed。
- 已驗證 Artifact 冪等、內容變更升版、tenant relations、事件稽核、dry-run、copy／hash、來源保留、pending delete 與取消。

## 實際客戶資料唯讀驗證

台灣行動支付 2026 上半年全部輸出、EDB 模擬與 archive preview 均位於 temporary directory。

| 項目 | 結果 |
|---|---:|
| Source files／manifest | 14／前後一致 |
| Registered artifacts／versions | 11／全部 v1 |
| Re-register | 同一組 Artifact IDs |
| Relations／events | 2／11 |
| Archive due | 0 |

## 結論

本機與實際客戶資料驗證通過；M9.5 Pipeline／Renderer 契約未修改。公司 EPAS 尚未執行 `0004_m9_6` 或 live scoped Job Artifact E2E，因此正式可回復版本仍是 `m9.5`。
