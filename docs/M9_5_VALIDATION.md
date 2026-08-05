# M9.5 Validation Report

日期：2026-08-05
分支：`feature/m9-5-pipeline-result-persistence`
狀態：Passed；本機、實際客戶資料與公司 `.77/.81` 部署驗證完成

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

## 公司 `.77/.81` 部署驗證

- App release：`/data/omnicheck/app/releases/916adff`。
- 升級前 revision：`0002_m9_4`；升級後：`0003_m9_5`。
- 升級前備份：`/data/omnicheck/archive/omnicheck_app_pre_m9_5_20260805.dump`，26,649 bytes。
- Backup SHA-256：`b1bab16fa5c006a8832a621dd9fce0fe2ce7a18c4025d0b290a865da030e1575`；`pg_restore --list` 通過。
- 公司 VM：70 tests、V4 bundle hashes 全部通過。
- 八張 M9.5 tables 與 121 個相關 constraints 已確認存在。
- Scoped Golden Job：`fa28fea9f9d04f53bbd96f209042fe44`，attempts 1、11 outputs、succeeded。
- Snapshot：`1be99fddb5404aa8add49a89146ee339`；Scope 3、Normalized 22、Unparsed 0、Config 3、Assessment 3、Coverage 40、QA 2。
- 相同 Canonical 重寫回傳 `created=False` 與相同 Snapshot。
- Web／Worker restart 後 active；health 為 `metadata=database`、`worker=external`；近期 Worker journal 無 persistence error。

第一次 migration 命令揭露 venv editable package 仍固定指向舊 release；Alembic 在載入 M9.5 module 前停止並自動切回 M9.4，DB 保持 `0002_m9_4`。重新安裝新 release editable package 後 migration 成功。第一次 migration 後 health probe 又早於 Uvicorn ready，application 自動切回 M9.4，但 additive DB 已是 `0003_m9_5`；改用最多 30 秒 health retry 後正式切換成功。兩次事件均已確認服務可回復、資料未遺失。

## 結論

M9.5 本機、實際資料唯讀、公司 EPAS migration、Scoped Worker Persistence、冪等與重啟持久性全部通過。Application 可切回 `m9.4` 並保留 additive schema；實際 `alembic downgrade 0002_m9_4` 會刪除全部 M9.5 results，仍需備份、staging 演練與另行核准。
