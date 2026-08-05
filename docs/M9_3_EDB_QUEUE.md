# M9.3 EDB Metadata 與可靠背景工作

## 目標架構

M9.3 不再由 Web 程序直接執行正式健檢。Web 將案件狀態寫入 EDB，獨立 Worker 使用 `FOR UPDATE SKIP LOCKED` 原子領取一筆 queued 工作，完成後更新狀態與事件紀錄。

```text
Web → EDB jobs queue ← Worker → M1～M8.1 Pipeline
           ↓                       ↓
      job_events              /data/omnicheck/jobs
```

EDB 保存案件 metadata、狀態、claim、attempt 與事件；客戶原始檔、JSON、DOCX、PDF 仍保存在應用程式 VM 的檔案系統。

## 已確認測試環境

```text
Application VM：192.168.118.77（CentOS 9）
Data root：/data/omnicheck
EDB：192.168.118.81:5444
Database：omnicheck_app
Schema：omnicheck
User：omnicheck_app
TLS：off（僅測試環境）
Service manager：systemd
Redis／Docker Compose：不使用
```

Repository 不保存實際密碼。部署時使用權限為 `0600` 且 owner 為 `omnicheck` 的 `/etc/omnicheck-ai/pgpass`。

## Migration

確認 EDB 已建立 `omnicheck` schema 且 application user 為 owner，然後在 application VM 執行：

```bash
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL='postgresql+psycopg://omnicheck_app@192.168.118.81:5444/omnicheck_app?sslmode=disable&passfile=/etc/omnicheck-ai/pgpass' \
  /data/omnicheck/venv/bin/alembic -c /data/omnicheck/app/current/alembic.ini upgrade head
```

正式環境不得沿用 `sslmode=disable`；啟用 EDB TLS 與 VIP 後，連線設定應改為 `verify-full` 和符合憑證的 DNS 名稱。

## Queue 狀態

- `draft`：可上傳原始證據
- `queued`：等待 Worker
- `running`：已由一個 Worker claim
- `succeeded`：Pipeline 與輸出完成
- `failed`：重試次數耗盡

每次 claim 會增加 `attempts`。失敗但尚未達 `max_attempts` 時，工作在退避時間後回到 queued。Worker 執行期間會定期 heartbeat 更新 lease；超過 lease 且沒有 heartbeat 的 running 工作，才會在 Worker 啟動時重新排隊。完成或失敗寫入也會確認 worker ID，失去 lease 的 Worker 不得覆寫其他 Worker 的狀態。

## 執行模式

未設定 `OMNICHECK_DATABASE_URL` 時，系統維持原有本機 filesystem metadata 與 FastAPI in-process background task，供開發與單機回歸測試使用。

設定 `OMNICHECK_DATABASE_URL` 後：

- Web 僅建立、上傳、排隊、查詢及下載
- Worker 必須以 `omni-healthcheck-worker` 獨立啟動
- `/api/health` 會顯示 `metadata=database`、`worker=external`
- `/api/jobs/{job_id}/events` 提供完整工作事件
- 只有 `succeeded` 案件可以列出或下載輸出，避免交付失敗嘗試留下的部分檔案

## CentOS 9 systemd

範本位於：

- `deploy/systemd/omnicheck-web.service`
- `deploy/systemd/omnicheck-worker.service`
- `deploy/omnicheck.env.example`
- `deploy/pgpass.example`

正式安裝前須將範本複製到 `/etc`、填入密碼、設定 owner／mode，並先執行 Alembic migration。這些遠端部署動作不會由本機開發流程自動執行。
