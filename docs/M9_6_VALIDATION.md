# M9.6 Validation Report

日期：2026-08-10
分支：`feature/m9-6-artifact-lifecycle`
狀態：Passed；本機、實際客戶資料與公司 `.77/.81` 部署驗證完成

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

## 公司 `.77/.81` 部署驗證

- App release：`/data/omnicheck/app/releases/2fc2ce7`。
- 升級前 revision：`0003_m9_5`；升級後：`0004_m9_6`。
- 升級前備份：`/data/omnicheck/archive/omnicheck_app_pre_m9_6_20260810.dump`，56,609 bytes。
- Backup SHA-256：`de79b27dc6d05a04f9415d4ef91b04132bde9ea7bc29b57bd38ebf84be4877e2`；`pg_restore --list` 通過。
- 公司 VM：74 tests、V4 bundle hashes 全部通過。
- `artifacts`、`artifact_relations`、`artifact_events` 共 44 個相關 constraints 已確認。
- Scoped Golden Job：`3c600f747da84d4e92f3c86f6fd0f6d3`，attempts 1、11 outputs、succeeded。
- Snapshot：`f16ef6c31b3049dd9fd1d927fdee7597`；Artifacts 11、Relations 2、Events 11、全部 version 1。
- 相同輸出重新登錄維持相同 Artifact IDs，沒有新增版本或事件。
- Archive dry-run：0 items、`apply=false`；archive 目錄前後 SHA-256 manifest 完全一致。
- Web／Worker restart 後 enabled／active；health 為 `metadata=database`、`worker=external`；近期 Worker journal 無錯誤。

公司 VM 完整測試超過遠端單次命令約 30 秒的執行期限，前兩次前景命令在第 51 項被連線通道終止，沒有測試失敗或殘留程序。改為背景執行與結果檔輪詢後取得完整 74 tests、exit 0；此為部署通道限制，不是產品錯誤。

## 結論

M9.6 本機、實際資料唯讀、公司 EPAS migration、Scoped Artifact Registry、冪等、Archive dry-run 與重啟持久性全部通過。Application 可切回 `m9.5` 並保留 additive schema；實際 `alembic downgrade 0003_m9_5` 會刪除 M9.6 metadata 與 version 2 以上 registry rows，仍需備份、staging 演練與另行核准。
