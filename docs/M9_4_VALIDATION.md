# M9.4 Validation Report

日期：2026-08-05  
分支：`feature/m9-4-application-data-foundation`  
狀態：Passed；已合併 `main` 並建立 `m9.4` 正式回復點

## 1. 自動化測試

- M9.4 application data + M9.3 database queue targeted tests：13 passed。
- 完整 regression：65 passed。
- `git diff --check`：passed。
- PostgreSQL Alembic offline upgrade：`0001_m9_3 → 0002_m9_4` 成功生成。
- PostgreSQL Alembic offline downgrade：`0002_m9_4 → 0001_m9_3` 成功生成。

驗證涵蓋：

- 六張 M9.4 table 與 `jobs.customer_id/system_id`。
- Customer／System／Node／Topology／Evidence／Artifact CRUD。
- 跨 tenant Node、Topology 與 Job 重新關聯拒絕。
- 相對 storage key、SHA-256、file size 與 uniqueness validation。
- M9.3 legacy Job 在 tenant scope 為 `NULL` 時仍可建立。

## 2. 實際客戶資料唯讀驗證

Dataset：台灣行動支付 2026 上半年  
來源：Repository 外部唯讀資料夾；未複製或提交 Git

驗證方法：

1. 執行前建立所有 14 個來源檔案的 relative path、size、SHA-256 manifest。
2. 使用既有 Inventory／Scope 決定 evidence domain 與節點映射。
3. 在系統 temporary directory 建立隔離 SQLite，不連線公司 EDB。
4. 建立 Customer、System、5 個 Node、4 條 Topology relation 與 M9.3 Job。
5. 將 14 個來源檔案只以 metadata 方式登錄 Evidence；不寫入來源目錄。
6. 再次計算來源 manifest 並比較。

結果：

| 項目 | 結果 |
|---|---:|
| Source files | 14 |
| Source manifest before／after | identical |
| Customer／System | 1／1 |
| Nodes | 5 |
| Topology relations | 4 |
| Evidence metadata | 14 |
| Scope allowed／excluded／pending | 11／3／0 |

5 個節點為 `twmpedbp1` Primary、`twmpedbp2` Standby、`twmpedbdr1` DR、`pemp1` Witness／PEM、`twmpedbwitness` Witness／EFM。3 筆 excluded 包含 Standby database、PEM backend database 與 `.DS_Store`；Web M9.3 沒有上傳 `.DS_Store`，因此其有效 13 inputs 結果仍是 11 allowed／2 excluded／0 pending。

## 3. 回歸判斷

- M1～M8.1 Pipeline：未修改資料契約與處理順序。
- M7 V4 Renderer：未修改。
- M9.3 Queue／Worker：既有 nullable scope 路徑與 targeted regression 均通過。
- Canonical JSON：仍是不可變 Pipeline／Renderer 契約；M9.4 沒有改 schema。
- AI：未加入，也不影響離線確定性流程。

## 4. 公司 `.77/.81` 部署驗證

環境：`omnicheck-ai-app`（CentOS Stream 9）→ EPAS 17.10 `192.168.118.81:5444`。

- 升級前 release：`a1d286f`；Alembic：`0001_m9_3`；Job：2 draft／4 succeeded。
- 升級前 logical backup：`/data/omnicheck/archive/omnicheck_app_pre_m9_4_20260805.dump`。
- Backup SHA-256：`e07edb51bcab5d71e14c4de19ad5c539186bfc6ea650e658da2c8cf07e7822df`；`pg_restore --list` 通過。
- 新 release：`/data/omnicheck/app/releases/9dc7d76`；公司 VM 完整測試 65 passed。
- Alembic：`0001_m9_3 → 0002_m9_4 (head)` 成功。
- 六張新 table、Job tenant columns 與預期 PK／FK／Unique／Check constraints 全部存在。
- 既有 6 筆 Job 完整；legacy rows 的 `customer_id/system_id` 均為 `NULL`。
- EPAS transaction smoke：建立 Customer／System／Primary／Standby／Topology 成功；rollback 後零殘留。
- Web／Worker：active；health 為 `metadata=database`、`worker=external`。
- Golden deployment Job：`cf384056cf7045878f12341324cb1852`，3 inputs、11 outputs、attempts 1、succeeded。

第一次維護命令在 Job precheck 的 shell／SQL quoting 階段失敗，`set -e` 在停止服務與 migration 前終止；確認環境完全未變後才重新執行。實際 migration 與切換成功。另一次 inline smoke script 在 Python parse 階段失敗，transaction 尚未開始；簡化後的 rollback smoke 通過。

## 5. 尚未驗證／不得誤標完成

- 尚未執行隔離環境的完整 backup restore 與實際 downgrade drill；只完成 backup archive 可讀與 offline downgrade SQL。
- Web 尚未自動建立 Customer／System／Node。
- Pipeline result persistence 與完整 Artifact lifecycle 分屬 M9.5／M9.6。

## 6. 結論

M9.4 本機、實際客戶資料唯讀、公司 EPAS migration、CRUD rollback smoke 與 live Queue／Worker Golden E2E 均通過。`main` 與 `m9.4` 為正式 Git rollback 基準；`m9.3` 保留為 foundation 前的 application rollback 點。公司 EDB schema 為 `0002_m9_4` additive state，database downgrade 仍需備份、staging 演練與獨立核准。
