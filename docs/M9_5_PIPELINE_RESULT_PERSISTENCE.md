# M9.5 Pipeline Result Persistence

日期：2026-08-05
狀態：Passed；已完成公司 EDB deployment，待隨本次變更建立 `m9.5` 正式 tag

## 目的

在不改寫既有 Pipeline、Canonical JSON 或 V4 Renderer 的前提下，將成功結果投影到 EDB，供歷史、查詢、CVE 與稽核使用。

## 資料模型

- `pipeline_snapshots`：Job、tenant、版本、Canonical SHA-256、來源時間與文件 hash。
- `scope_decisions`：證據 domain、node、role、decision 與理由。
- `normalized_checks`／`normalized_unparsed`：check rows 與未解析證據。
- `configuration_comparisons`：參數與 `pg_hba` 比較。
- `pipeline_assessments`：狀態、規則、觀察與建議。
- `coverage_items`：節點、check 與 coverage。
- `quality_results`：M6 QA 與 V4 QA。

所有 child rows 都有 Customer／System／Job scope 與複合 FK。

## 寫入與冪等性

Pipeline／Renderer／QA 完成後，在單一 transaction 寫入，commit 後 Job 才 succeeded。唯一鍵為 `job_id + schema_version + canonical_sha256`；相同輸出重試不重複寫入。Persistence 失敗時走既有 retry／failed。

`OMNICHECK_PERSIST_RESULTS=true` 為預設。Legacy Job 若 Customer／System 都是 `NULL` 會跳過；只有完整 scoped Job 正式寫入。

## Migration 與 rollback

Upgrade：`alembic upgrade 0003_m9_5`。Downgrade：`alembic downgrade 0002_m9_4`，會刪除全部 M9.5 results，必須先備份、演練並核准。設定 `OMNICHECK_PERSIST_RESULTS=false` 可停用 Adapter，不影響 JSON 與報告。

## 非目標

Web Customer／System 操作待整合；Artifact lifecycle 屬 M9.6；歷史差異屬 M12。
