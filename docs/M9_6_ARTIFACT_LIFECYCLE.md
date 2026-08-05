# M9.6 Artifact Registry／Retention／Archive

日期：2026-08-05
狀態：功能分支本機與實際客戶資料唯讀驗證完成；公司 EDB 尚未部署

## 目的

把 Pipeline 大型輸出保留在 `/data`，在 EDB 建立可攜、版本化、可追溯的 Artifact Registry，並提供不直接刪除來源的安全封存流程。

## 資料模型

- `artifacts` 新增 `artifact_version`、`updated_at`、`archived_at`、`deleted_at`。
- `artifact_relations` 保存 Canonical JSON → Report Model → V4 JSON → DOCX → PDF 的衍生關係。
- `artifact_events` 保存 registered、archived、delete_requested、delete_cancelled 稽核事件。
- 唯一鍵以 Job／Artifact Type／Version 與 Job／Storage Key／SHA-256 控制版本與冪等。

## Pipeline 整合

Scoped Worker 在 M9.5 Persistence 後、自 Job succeeded 前登錄 output artifacts。相同檔案重跑不重複；同一 storage key 內容改變時建立下一個版本。Legacy unscoped Job 保持相容。

設定：

- `OMNICHECK_REGISTER_ARTIFACTS=true`
- `OMNICHECK_ARTIFACT_RETENTION_DAYS=365`
- `OMNICHECK_STORAGE_ROOT=/data/omnicheck`
- `OMNICHECK_ARCHIVE_ROOT=/data/omnicheck/archive`

## 安全封存

`omni-healthcheck-artifacts` 預設只列出到期項目。只有加 `--apply` 才會複製到 archive、驗證 SHA-256，然後更新 EDB；來源檔仍保留。Artifact 只有 archived 後才能進入 `pending_delete`，且可以取消。M9.6 不提供自動實體刪除。

## Migration 與 rollback

Upgrade：`alembic upgrade 0004_m9_6`。Downgrade 回 `0003_m9_5` 會刪除 relations、events 與 M9.6 欄位，並刪除 Artifact version 2 以上的 registry rows；必須先備份、staging 演練並另行核准，實體檔案不會由 migration 刪除。
