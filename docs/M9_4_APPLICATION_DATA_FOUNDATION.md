# M9.4 EDB Application Data Foundation

日期：2026-08-05  
狀態：功能分支與公司 `.77/.81` 部署驗證完成，尚未合併 `main` 或建立 tag

## 1. 目的

M9.4 在 M9.3 的 EDB Job Queue 後方建立 tenant-scoped 應用資料基礎，讓後續 Pipeline 結果、歷史比較、CVE 與權限模型有穩定的 Customer／System／Node 身分可引用。

本階段不改寫 M1～M8.1 Pipeline、不取消 Canonical JSON、不改 Renderer，也不把大型原始檔、圖片、DOCX 或 PDF 存入 EDB。

## 2. 新增資料表

| Table | 用途 | Tenant 邊界 |
|---|---|---|
| `customers` | 客戶與唯一 `tenant_key` | 根實體 |
| `systems` | 客戶內受檢系統與環境 | `customer_id` |
| `nodes` | Primary／Standby／DR／Witness 與服務屬性 | `customer_id + system_id` |
| `topology_relations` | 節點間 replication、monitoring、witness 等關係 | 來源與目標節點都必須屬於同一 Customer／System |
| `evidence_files` | 原始證據的 storage key、SHA-256、大小、media type 與節點映射 | Job、Customer、System、Node 複合外鍵 |
| `artifacts` | Canonical JSON、QA、DOCX、PDF 等輸出索引 | Job、Customer、System 複合外鍵 |

`jobs` 新增 nullable `customer_id` 與 `system_id`。既有 M9.3 row 可以維持 `NULL`，新流程可在建案後關聯 Customer／System；已關聯 Job 不得改掛另一個 tenant。

## 3. 儲存契約

- 大型實體檔仍保存在 `/data`。
- EDB 只保存 `storage_backend + storage_root_version + storage_key`，不保存綁死單一 VM 的絕對路徑。
- Evidence／Artifact 都保存 SHA-256、大小、media type 與建立時間。
- `storage_key` 必須是安全相對路徑，拒絕絕對路徑與 `..` traversal。
- `customer_id` 從 M9.4 進入所有核心關聯；M11 才加入 Login、RBAC、Audit 與正式授權 enforcement。

## 4. 程式元件

- `src/omni_healthcheck/application_data.py`：SQLAlchemy tables、驗證與 tenant-scoped repository。
- `src/omni_healthcheck/database.py`：M9.3 Job 加入 nullable tenant scope，保留既有 Queue 行為。
- `migrations/versions/0002_m9_4_application_data.py`：additive upgrade 與精確 downgrade。
- `migrations/env.py`：載入完整 metadata。
- `tests/test_application_data.py`：schema、CRUD、隔離、storage 安全與 M9.3 相容性測試。

## 5. 非目標與下一階段

M9.4 只建立身分與檔案 metadata 基礎；下列功能尚未完成：

- M9.5：Scope、Normalized、Assessment、Coverage、QA 與版本資訊的冪等 Persistence Adapter。
- M9.6：Artifact 衍生關係、版本、Retention、Archive／Purge workflow。
- M10：從未知資料包提出節點／角色建議並由人確認。
- M11：登入、RBAC、Customer isolation enforcement 與 Audit。

目前 Web 表單仍可照 M9.3 操作，但尚未自動建立／選擇 Customer 與 System records。公司 EDB 已有 foundation schema；現有 legacy Job 仍維持 nullable tenant scope。

## 6. Migration 與 rollback

Upgrade：

```bash
alembic upgrade 0002_m9_4
```

Downgrade：

```bash
alembic downgrade 0001_m9_3
```

Downgrade 會刪除 M9.4 六張新表、其資料，以及 `jobs.customer_id/system_id`。正式環境執行前必須停止 Web／Worker、完成 EDB 備份與 staging restore drill，並另行取得核准。Git rollback 不等同 database rollback；若舊程式能忽略 additive schema，優先切回 `m9.3` application 或採 forward fix。

## 7. 完成條件

- M9.3 未關聯 tenant 的 Job 仍可建立與執行。
- Customer／System／Node／Topology／Evidence／Artifact 可在隔離資料庫建立與查詢。
- 跨 tenant Job、Node 與 Topology 關聯會被 repository 或 database constraint 拒絕。
- PostgreSQL upgrade／downgrade SQL 可生成。
- 實際客戶資料只讀投影後來源 manifest 不變。
- 完整 Pytest、V4 Golden／bundle、文件 DOCX render 均通過後，才可請使用者驗收並進行 `.81` staging migration。
