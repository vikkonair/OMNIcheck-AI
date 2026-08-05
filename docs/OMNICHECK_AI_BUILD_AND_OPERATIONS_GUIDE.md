# OMNIcheck AI 建置、部署與維運主手冊

文件編號：OMNI-OPS-001  
文件版本：0.9.3-draft.4
最後更新：2026-08-05  
適用程式基準：`feature/m9-web-job-management` / `a1d286f`
正式可回復基準：`m8.1`  
文件擁有者：Omniwaresoft Tech  
機密等級：內部使用

> 本文件是「從空白 VM 重建相同 OMNIcheck AI 系統」的權威手冊。`docs/PROJECT_RUNBOOK.md` 記錄 milestone 履歷；本文件負責套件、命令、設定、驗證、日常維運與回復。任何影響建置或操作的變更，都必須先更新本 Markdown、重建 DOCX、逐頁檢查，再與程式一併提交。

## 文件控制

| 項目 | 規則 |
|---|---|
| 權威原稿 | `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.md` |
| 交付版本 | `docs/OMNICHECK_AI_BUILD_AND_OPERATIONS_GUIDE.docx` |
| 產生工具 | `scripts/build_operations_guide.py` |
| 更新時機 | milestone、依賴、環境變數、migration、systemd、目錄、網路、備份、驗證或 rollback 改變時 |
| 合併條件 | Markdown 與 DOCX 同步、DOCX render 無截斷、命令與目前程式相符、revision table 已更新 |
| 禁止內容 | 真實密碼、私鑰、EDB repository token、客戶原始資料、未遮蔽報告 |

### 修訂紀錄

| 版本 | 日期 | 變更 | 驗證狀態 |
|---|---|---|---|
| 0.9.3-draft.4 | 2026-08-05 | 完成 SCRAM／pgpass、實際客戶資料 E2E 與 V4 摘要分頁修正 | 本機／VM 60 tests、QA、V4 QA、29 頁 PDF 與來源 hash 通過；待 merge/tag |
| 0.9.3-draft.3 | 2026-08-05 | 納入 EDB 中心化、Canonical JSON、Artifact、CVE 與 AI 責任邊界決策 | 文件與 DOCX 驗證；後續資料模型尚未實作 |
| 0.9.3-draft.2 | 2026-08-05 | 完成公司 App VM／EDB core deployment、EPAS Redwood 與 Linux fontconfig 修正 | 公司 Golden E2E 通過；TLS／密碼驗證與實際客戶資料待完成 |
| 0.9.3-draft.1 | 2026-08-05 | 首次建立可重建系統的建置與維運主手冊 | 本機驗證 |

## 1. 使用方式與責任邊界

本手冊的目標讀者是接手開發、部署或維運的工程師。完成後，讀者應能：

1. 從空白 CentOS 9 VM 安裝應用程式所需元件。
2. 建立或連接 EDB Postgres Advanced Server 17 metadata database。
3. 部署 Web 與 Worker systemd service。
4. 執行 CLI、Web 與 EDB queue 三種模式。
5. 驗證 M1～M9.3 的輸出、Golden Regression 與 PDF 字型。
6. 進行備份、復原、升級、故障排除與 rollback。

標記方式：

- **已驗證**：已在本機測試或既有實際資料唯讀流程通過。
- **公司環境待驗證**：命令與設定已準備，但尚未在 `192.168.118.77/.81` 執行。
- **範例值**：部署時必須替換，不可直接照抄至正式環境。

本文件不授權未經變更流程的 EDB failover、刪除 LVM、刪除資料庫、Alembic downgrade 或正式環境停機。

## 2. 目前版本與完成範圍

| 層次 | 正式狀態 | 說明 |
|---|---|---|
| M1～M6 | 正式完成 | 清冊、拓撲、Scope、Parser、規則、Coverage 與品質閘門 |
| M7 | 正式完成 | 九興 V4 DOCX／PDF Renderer |
| M8～M8.1 | 正式完成 | Golden Regression、Witness service、XDB、pgBackRest、Barman 架構 |
| M9.1～M9.2 | 功能分支完成 | Web API、不可覆寫上傳、圖形化案件流程 |
| M9.3 | 本機完成 | EDB metadata、queue、獨立 Worker、retry／heartbeat／lease |
| M9.3 實機 | 正式化驗證通過 | 公司 EDB、systemd、SCRAM／pgpass、Golden、實際資料、DOCX／PDF 與重啟持久性通過；待 merge/tag |
| M9.4～M15 | 已核准、待實作 | EDB 應用資料、Artifact、拓撲確認、權限、歷史、CVE、選配 AI 與生產強化 |

`main`／`m8.1` 是目前正式可回復版本。M9.3 尚未合併 `main`，重建 M9.3 時要 checkout 文件表頭所列 commit，不能把它誤稱為正式 release。

## 3. 系統架構

```text
Browser / CLI
     │
     ├── Web :8000 ──> EDB metadata (jobs, job_events)
     │                    │
     │                    └── queued job
     │                           │
     └──────────────────── Worker process
                                  │
                                  v
Raw evidence (immutable) -> M1 Inventory/SHA-256
                         -> M2 Topology/Scope
                         -> M3-M4 Parser/Canonical JSON/config compare
                         -> M5 deterministic rules
                         -> M6 coverage/security/delivery QA
                         -> M7 V4 adapter/DOCX/LibreOffice PDF
                         -> M8-M8.1 Golden and service/backup registry
                                  │
                                  v
                         /data/omnicheck/jobs/<job_id>/output
```

### 3.1 目前 M9.3 資料責任

- 目前已實作的 EDB 只保存案件 metadata、狀態、claim、attempt 與事件。
- 客戶 input、JSON、DOCX、PDF 留在應用 VM `/data/omnicheck/jobs`。
- input 檔案建立後不可覆寫；Pipeline 以 SHA-256 保留可追溯性。
- Database／Schema／Table／Index 等邏輯證據只採 Primary。
- `postgresql.conf`、`postgresql.auto.conf`、`pg_hba.conf` 是節點設定，可比較 Primary／Standby／DR。
- Witness 可承載 PEM、EFM、XDB、Barman；PEM 後端 DB 不得被當作業務 Primary。

### 3.2 AI 邊界

目前正式路徑不需要外部 AI。Primary、Scope、狀態、證據、版面與品質閘門均為確定性程式。未來 AI 只能做已遮蔽內容的摘要、解釋或問答，不得更動證據與判斷。

### 3.3 已核准的目標資料架構（M9.4 起）

詳細權威決策為 `docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md`。實作原則如下：

- EDB 逐步成為結構化應用資料、歷史、規則結果與 CVE Cache 的主要查詢來源。
- `/data` 繼續保存原始證據、圖片、壓縮檔、Canonical JSON、DOCX、PDF 與 Render 暫存檔。
- EDB 對大型檔案只保存 `storage_backend`、`storage_key`、hash、大小、media type、保留與封存狀態。
- Canonical JSON 不取消；它是不可變 Pipeline／Renderer 契約、Golden、除錯、重建與 rollback 保護。
- Pipeline 後增加冪等 Persistence Adapter；持久化失敗時 Job 不得標成 succeeded。
- Customer／tenant key 從 M9.4 進資料模型；M11 再完成 Login／RBAC／Audit enforcement。
- CVE 由固定官方來源排程同步，Version Matcher 確定性判斷；AI 不決定漏洞適用性。

此節是核准的未來狀態，不代表 M9.4～M15 的 table、migration、sync worker 或 AI Gateway 已經存在。

## 4. 目標環境基準

### 4.1 公司測試環境

| 項目 | 值 | 狀態 |
|---|---|---|
| App VM | `omnicheck-ai-app`／`192.168.118.77`，CentOS Stream 9 x86_64 | 已部署並驗證 |
| App data | `/data/omnicheck`，約 46 GB 可用 | 已驗證 |
| EDB Primary | `192.168.118.81:5444` | EPAS protocol／SQLAlchemy／migration 已驗證 |
| EDB version | EPAS 17.10 | 使用者確認 |
| Database／User | `omnicheck_app`／`omnicheck_app` | 使用者確認 |
| Schema | `omnicheck` | 使用者確認 |
| TLS | `off` | 僅測試；正式禁止沿用 |
| HA | EFM；Primary、Standby、Witness、DR | 使用者確認 |
| Container | 不使用 Docker Compose | 使用者確認 |
| Service manager | systemd | Web／Worker enabled、active、重啟持久性通過 |

### 4.2 最低建議資源

| 資源 | 測試 | 正式起始值 | 說明 |
|---|---:|---:|---|
| vCPU | 2 | 4 | PDF 轉換與多案件可增加 |
| RAM | 4 GB | 8 GB | 大型 DOCX／圖片需保留餘裕 |
| `/data` | 50 GB | 依保留期估算 | input + 中間 JSON + DOCX/PDF + archive |
| Swap | 2 GB | 4 GB | 不能取代 RAM |

容量公式：`每日案件數 × 單案平均 input/output 大小 × 保留天數 × 1.3`。正式上線前用三個真實代表性資料包量測，不可只採估算。

## 5. 建置前輸入與核准清單

準備以下資料後才開始：

- OS 版本與 CPU architecture：`cat /etc/os-release`、`uname -m`。
- 主機名稱、IP、DNS、NTP、proxy、套件 repository。
- EDB repository 存取方式；token 不寫入本文件或 Git。
- EDB host／VIP、port、database、schema、application user。
- 測試與正式的 TLS mode、CA、client certificate（若使用）。
- 防火牆來源／目的、備份位置、保留期與 RPO/RTO。
- Git repository URL 與要部署的 tag／commit。
- 中文字型授權與標準字型檔。

建立變更單並記錄：執行人、覆核人、日期、目標版本、備份位置、rollback point、預計停機與驗證結果。

## 6. App VM 從空白環境建置

以下命令以 `root` 執行；明確寫 `sudo -u omnicheck` 的步驟除外。

### 6.1 蒐集基線（不異動）

```bash
date -Is
hostnamectl
cat /etc/os-release
uname -m
lscpu
free -h
df -hT
lsblk -f
getenforce
firewall-cmd --state
timedatectl
```

保存輸出於變更單。預期看到 CentOS 9、`x86_64`、`/data` 已掛載、時間同步正常。若 `/data` 不存在或不是預期 LVM，停止，不自行格式化。

### 6.2 驗證並安裝 OS 套件

先查詢，避免套件名稱因公司 mirror 不同而失敗：

```bash
dnf info git python3.12 python3.12-pip fontconfig libreoffice
dnf list available '*noto*cjk*' '*source*han*'
```

若 `python3.12` 可用：

```bash
dnf install -y git python3.12 python3.12-pip fontconfig libreoffice google-noto-sans-cjk-ttc-fonts
python3.12 --version
libreoffice --version
fc-list | head
```

公司實測版本為 Python 3.12.13、LibreOffice 7.1.8.1、Noto Sans CJK TC。若 repository 沒有上述套件，停止並由 OS 管理員提供核准 repository／RPM；不可臨時從不明網站下載，也不可用系統 Python 3.9 代替。

### 6.3 中文字型

先選公司核准字型。若 repository 有 Noto CJK，依 `dnf search noto | grep -i cjk` 顯示的實際套件名稱安裝。安裝後：

```bash
fc-cache -f -v
fc-match 'Noto Sans CJK TC'
fc-match 'Microsoft JhengHei'
fc-list :lang=zh-tw family | sort -u
```

至少要有一套繁體中文字型。若報告模板指定的字型不存在，LibreOffice 會 fallback，可能造成換行、頁數與表格寬度改變，因此必須完成第 13 章 PDF 視覺驗證。

### 6.4 建立服務帳號與目錄

```bash
getent group omnicheck || groupadd --system omnicheck
id omnicheck || useradd --system --gid omnicheck --home-dir /data/omnicheck --shell /sbin/nologin omnicheck
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/app
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/archive
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/jobs
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/logs
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/tmp
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/venv
install -d -o root -g omnicheck -m 0750 /etc/omnicheck-ai
```

驗證：

```bash
namei -l /data/omnicheck/jobs
find /data/omnicheck -maxdepth 1 -printf '%M %u:%g %p\n'
```

### 6.5 SELinux 與 firewalld

不要關閉 SELinux。若 Web 只供內網，先取得核准來源網段再開 port：

```bash
firewall-cmd --permanent --add-port=8000/tcp
firewall-cmd --reload
firewall-cmd --list-ports
```

若 SELinux 阻擋自訂 `/data` 執行或網路連線，先查看：

```bash
ausearch -m AVC -ts recent
journalctl -t setroubleshoot --since '30 minutes ago'
```

由 SELinux 管理員建立最小 policy。禁止用 `setenforce 0` 當正式解法。

## 7. EDB 17 Backend 建置

若公司已有 EDB 17.10 cluster，可跳至 7.4。以下安裝章節供從空白 EDB VM 重建；HA 複寫、EFM 與 VIP 必須依公司的 EDB 標準作業核准。

### 7.1 Repository 與 EPAS package

EDB repository 命令由 EDB Repos 入口依帳號、平台與產品產生。將命令貼入受控變更單執行，禁止把 credential／token 寫入 Git。

```bash
dnf repolist | grep enterprisedb
dnf makecache
dnf info edb-as17-server
dnf install -y edb-as17-server
```

官方套件名稱是 `edb-as17-server`。安裝會建立 `enterprisedb` OS account。

### 7.2 初始化單節點（僅新環境）

```bash
PGSETUP_INITDB_OPTIONS='-E UTF-8' /usr/edb/as17/bin/edb-as-17-setup initdb
systemctl enable --now edb-as-17
systemctl status edb-as-17 --no-pager
sudo -u enterprisedb /usr/edb/as17/bin/psql -d edb -c 'select version();'
```

預期 service 為 active，`version()` 顯示 EDB Postgres Advanced Server 17。若要指定獨立 PGDATA、port 5444 或 PostgreSQL mode，必須在 initdb 前依 EDB 官方選項建立；已初始化後不可直接重跑 setup 覆蓋。

### 7.3 EFM（HA 環境）

EFM 5.2 官方 package 範例為：

```bash
dnf info edb-efm52
dnf install -y edb-efm52
java -version
```

EFM 要求 Java 11 或更新；Witness 不必安裝本機 Postgres。正式 cluster 還要設定 cluster properties、nodes、encrypted DB password、允許節點與 service。不要用本手冊的範例值覆寫現有 EFM。驗證現有 cluster：

```bash
systemctl list-units 'edb-efm*'
ls -ld /etc/edb/efm-5.* /var/log/efm-5.*
```

EFM failover 測試另開維護窗口；OMNIcheck 部署不包含擅自 promote。

### 7.4 建立 OMNIcheck database、user、schema

先以 EDB 管理帳號連線。密碼不要放入 shell history；在 psql 中互動輸入或使用核准的 secret mechanism。

```sql
CREATE ROLE omnicheck_app LOGIN;
\password omnicheck_app
CREATE DATABASE omnicheck_app OWNER omnicheck_app;
\connect omnicheck_app
CREATE SCHEMA IF NOT EXISTS omnicheck AUTHORIZATION omnicheck_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE omnicheck_app TO omnicheck_app;
GRANT USAGE, CREATE ON SCHEMA omnicheck TO omnicheck_app;
```

若 database 或 role 已存在，不要重建；改用下列查詢確認 owner：

```sql
SELECT datname, pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname='omnicheck_app';
SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname='omnicheck_app';
SELECT nspname, pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname='omnicheck';
```

Application user 不應是 superuser。

### 7.5 pg_hba.conf 與連線

只允許 App VM `/32`，不要開放整個網段：

```text
host    omnicheck_app    omnicheck_app    192.168.118.77/32    scram-sha-256
```

重新載入並驗證：

```sql
SELECT pg_reload_conf();
SELECT * FROM pg_hba_file_rules WHERE database @> ARRAY['omnicheck_app'] OR database @> ARRAY['all'];
```

測試環境目前 TLS off，因此初期 URL 使用 `sslmode=disable`。正式環境必須以 DNS/VIP、server certificate 與 CA 改為 `sslmode=verify-full`。

## 8. 取得與安裝 OMNIcheck AI

### 8.1 Checkout 可追溯版本

```bash
cd /data/omnicheck/app
install -d -o omnicheck -g omnicheck -m 0750 /data/omnicheck/app/releases
sudo -u omnicheck git clone <APPROVED_GIT_URL> releases/8faff37
cd releases/8faff37
sudo -u omnicheck git fetch --tags --prune
sudo -u omnicheck git checkout 8faff37
git status --short
git rev-parse HEAD
```

正式 release 應 checkout tag；M9.3 實機驗證期間使用固定 commit。禁止部署 floating branch HEAD。

建立 stable symlink：

```bash
ln -sfn /data/omnicheck/app/releases/8faff37 /data/omnicheck/app/current
chown -h omnicheck:omnicheck /data/omnicheck/app/current
```

實際 rollout 建議每版獨立目錄 `/data/omnicheck/app/releases/<version>`，`current` 只在驗證後原子切換。

### 8.2 Python virtual environment

```bash
python3.12 -m venv /data/omnicheck/venv
/data/omnicheck/venv/bin/python -m pip install --upgrade pip
/data/omnicheck/venv/bin/pip install -e '/data/omnicheck/app/current[dev]'
/data/omnicheck/venv/bin/python --version
/data/omnicheck/venv/bin/pip check
/data/omnicheck/venv/bin/omni-healthcheck --help
```

正式離線環境應先建立經掃描的 wheelhouse 並保存 hashes，不要在正式 VM 即時連公共 PyPI。重建時保存：

```bash
/data/omnicheck/venv/bin/pip freeze
```

目前 V4 vendor bundle 位於固定 source release 外部，不包含於 wheel，因此部署採固定 release + editable link。`pyproject.toml` 仍允許版本範圍且尚未提供完整 lock file；正式上線前應建立可攜式 package data 與受控 lock／wheelhouse。

## 9. Secret 與環境設定

### 9.1 pgpass

正式環境建立 `/etc/omnicheck-ai/pgpass`：

```text
192.168.118.81:5444:omnicheck_app:omnicheck_app:<REPLACE_WITH_PASSWORD>
```

```bash
chown omnicheck:omnicheck /etc/omnicheck-ai/pgpass
chmod 0600 /etc/omnicheck-ai/pgpass
```

公司首次測試發現前置 `host all all 0.0.0.0/0 trust` 會蓋過後方 application 規則。M9.3 正式化已在該規則前新增只匹配 database/user `omnicheck_app`、來源 `192.168.118.77/32` 的 `scram-sha-256` 規則，輪替密碼並建立 `0600` pgpass。無密碼登入已驗證拒絕；pgpass 登入成功。既有全域 trust 規則尚未移除，因其可能影響其他應用，必須另案盤點後收斂。

### 9.2 Environment file

以 `deploy/omnicheck.env.example` 建立 `/etc/omnicheck-ai/omnicheck.env`：

```text
OMNICHECK_DATA_ROOT=/data/omnicheck/jobs
OMNICHECK_RULES_PATH=/data/omnicheck/app/current/config/rules.default.yaml
OMNICHECK_DATABASE_URL=postgresql+psycopg://omnicheck_app@192.168.118.81:5444/omnicheck_app?sslmode=disable&passfile=/etc/omnicheck-ai/pgpass
OMNICHECK_WEB_HOST=0.0.0.0
OMNICHECK_WEB_PORT=8000
OMNICHECK_WORKER_POLL_SECONDS=2
OMNICHECK_WORKER_RETRY_SECONDS=60
OMNICHECK_WORKER_HEARTBEAT_SECONDS=30
OMNICHECK_WORKER_STALE_SECONDS=3600
```

```bash
chown root:omnicheck /etc/omnicheck-ai/omnicheck.env
chmod 0640 /etc/omnicheck-ai/omnicheck.env
```

正式 TLS 範例：

```text
OMNICHECK_DATABASE_URL=postgresql+psycopg://omnicheck_app@<VIP_DNS>:5444/omnicheck_app?sslmode=verify-full&sslrootcert=/etc/omnicheck-ai/ca.crt&passfile=/etc/omnicheck-ai/pgpass
```

## 10. Database Migration

### 10.1 連線前檢查

```bash
sudo -u omnicheck env PGPASSFILE=/etc/omnicheck-ai/pgpass \
  /usr/edb/as17/bin/psql -h 192.168.118.81 -p 5444 -U omnicheck_app -d omnicheck_app \
  -c 'select current_database(), current_user, version();'
```

App VM 未必安裝 EDB client；若 `/usr/edb/as17/bin/psql` 不存在，安裝公司核准的 EPAS client 或 PostgreSQL client，再用實際路徑。

### 10.2 升級 schema

先備份、確認 revision，再升級：

```bash
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL="$(sed -n 's/^OMNICHECK_DATABASE_URL=//p' /etc/omnicheck-ai/omnicheck.env)" \
  /data/omnicheck/venv/bin/alembic \
  -c /data/omnicheck/app/current/alembic.ini current
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL="$(sed -n 's/^OMNICHECK_DATABASE_URL=//p' /etc/omnicheck-ai/omnicheck.env)" \
  /data/omnicheck/venv/bin/alembic \
  -c /data/omnicheck/app/current/alembic.ini upgrade head
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL="$(sed -n 's/^OMNICHECK_DATABASE_URL=//p' /etc/omnicheck-ai/omnicheck.env)" \
  /data/omnicheck/venv/bin/alembic \
  -c /data/omnicheck/app/current/alembic.ini current
```

預期 revision 為 `0001_m9_3 (head)`，schema 有 `jobs`、`job_events`、`alembic_version`。

```sql
SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema='omnicheck' ORDER BY 2;
SELECT version_num FROM omnicheck.alembic_version;
```

Alembic downgrade 會刪表，屬破壞性操作；只有完成 metadata backup 並取得明確核准後才能執行。

## 11. 安裝 systemd Web 與 Worker

```bash
install -o root -g root -m 0644 \
  /data/omnicheck/app/current/deploy/systemd/omnicheck-web.service \
  /etc/systemd/system/omnicheck-web.service
install -o root -g root -m 0644 \
  /data/omnicheck/app/current/deploy/systemd/omnicheck-worker.service \
  /etc/systemd/system/omnicheck-worker.service
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/omnicheck-web.service
systemd-analyze verify /etc/systemd/system/omnicheck-worker.service
systemctl enable --now omnicheck-web omnicheck-worker
systemctl status omnicheck-web omnicheck-worker --no-pager
```

健康檢查：

```bash
curl --fail --silent http://127.0.0.1:8000/api/health
journalctl -u omnicheck-web -u omnicheck-worker -n 100 --no-pager
```

預期 JSON 含 `status=ok`、`metadata=database`、`worker=external`。若是 `filesystem`，代表 `OMNICHECK_DATABASE_URL` 未生效，不是正式 M9.3 模式。

## 12. 三種操作模式

### 12.1 CLI（最小、可離線）

```bash
/data/omnicheck/venv/bin/omni-healthcheck generate \
  --job /path/to/job.yaml \
  --rules /data/omnicheck/app/current/config/rules.default.yaml \
  --input /path/to/read-only-input \
  --output /path/to/new-output
```

CLI 直接執行 M1～M8.1，不需要 EDB metadata。

### 12.2 Web filesystem mode（僅開發）

不設 `OMNICHECK_DATABASE_URL` 時，Web 使用 `job.json` 與同程序 background task。重啟可靠性較低，不建議多人正式使用。

### 12.3 Web + EDB + Worker（M9.3）

使用者開啟 `http://<APP_VM>:8000/`，建立案件、設定節點、上傳資料夾、執行、等待 Worker，再下載輸出。Primary／Standby／DR／Witness 仍由使用者確認；目前不是完全未知資料包的自動角色決策器。

## 13. 驗證與驗收

### 13.1 程式測試

```bash
cd /data/omnicheck/app/current
/data/omnicheck/venv/bin/pytest
git diff --check
```

公司實機修正後基準為 59 tests 全部通過。實際數量會隨版本增加，不應硬性只等於 59；重點是 0 failed。

### 13.2 V4 bundle 完整性

```bash
cd /data/omnicheck/app/current
sha256sum -c vendor/omni-v4-renderer/MANIFEST.sha256
```

所有項目必須 `OK`。Renderer、模板、字型或圖片 hash 不符時禁止交付。

### 13.3 Golden Regression

```bash
/data/omnicheck/venv/bin/pytest tests/test_golden_regression.py tests/test_v4_integration.py
```

三組 Golden 至少涵蓋九興 V4、環球 PEM/Witness、多節點 Scope。

### 13.4 實際客戶資料唯讀驗證

1. 對來源資料建立檔案數、size、SHA-256 manifest。
2. output 與暫存一律放在來源資料夾之外。
3. 執行 Pipeline。
4. 再次建立來源 manifest 並 `diff`。
5. 來源差異必須為零。
6. `qa-result.json` 與 `v4-qa-result.json` 必須允許交付。

### 13.5 DOCX／PDF 與字型驗證

```bash
libreoffice --headless --convert-to pdf --outdir /tmp/report-check /path/to/report.docx
pdfinfo /tmp/report-check/report.pdf
pdffonts /tmp/report-check/report.pdf
```

檢查封面、目錄、每個 major section、長表格續頁、設定檔小字、繁體中文、頁尾與最後一頁。DOCX 與 PDF 不得有文字重疊、缺字方框、截斷、空白異常頁。換 VM、LibreOffice 或字型版本後必須重新逐頁 QA。

### 13.6 M9.3 EDB queue 驗收

- 建案後 EDB 有 `created` event。
- 執行後狀態 `queued`。
- Worker claim 後為 `running`，attempts +1。
- 完成為 `succeeded`，輸出可下載。
- Pipeline 人為失敗時依設定 retry。
- Worker 中止後，在 lease 超時才 stale recovery。
- 兩個 Worker 同時啟動不得重複 claim 同一 job。
- EDB unavailable 時 `/api/health` 必須 503，不能假裝正常。

## 14. Pipeline 產物與判讀

| 檔案 | 代表意義 |
|---|---|
| `inventory.json` | 原始檔清冊、分類與 SHA-256 |
| `topology.json` | 節點角色與服務 |
| `scope-ledger.json` | 證據採用／排除／pending 的理由 |
| `normalized.json` | Parser 標準化結果 |
| `configuration-comparison.json` | Primary／Standby／DR 設定差異 |
| `assessment.json` | 規則狀態、證據、觀察、結論、建議 |
| `coverage-ledger.json` | 預期檢查、缺漏與覆蓋率 |
| `qa-result.json` | M6 交付 gate |
| `report-model.json` | 報告組裝中介模型 |
| `v4-report.json` | V4 Renderer contract |
| `v4-qa-result.json` | V4 報告 gate |
| `report.docx`／`report.pdf` | 正式交付報告 |

任何 mandatory gate 失敗，不得只拿出 PDF 交付。

## 15. 日常維運

### 15.1 每日

```bash
systemctl is-active omnicheck-web omnicheck-worker
curl --fail --silent http://127.0.0.1:8000/api/health
df -h /data
journalctl -u omnicheck-web -u omnicheck-worker --since today -p warning --no-pager
```

EDB 查詢：

```sql
SELECT status, count(*) FROM omnicheck.jobs GROUP BY status ORDER BY status;
SELECT job_id, status, attempts, claimed_by, claimed_at, updated_at
FROM omnicheck.jobs
WHERE status IN ('queued','running','failed')
ORDER BY created_at;
```

### 15.2 每週

- 抽查 failed job 與 event，不直接手改狀態。
- 檢查 `/data` 成長、最大案件與 archive。
- 驗證備份完成與最近一次 restore drill 紀錄。
- 檢查 OS／Python／LibreOffice／EDB 變更通知。

### 15.3 每月

- 在 staging 執行完整 Pytest、Golden、DOCX/PDF render。
- 進行一筆 metadata restore 與一個 job directory restore。
- 檢查 application user 權限、firewall、service hardening。
- 更新本手冊 revision 與 known limitations。

## 16. 備份與復原

### 16.1 備份範圍

1. EDB `omnicheck_app` database（至少 `omnicheck` schema）。
2. `/data/omnicheck/jobs`，包含 input、job.yaml、job.json、output。
3. `/etc/omnicheck-ai` 的設定；secret backup 必須加密且限制存取。
4. Git commit/tag 與 wheelhouse／lock。

### 16.2 EDB logical backup 範例

```bash
sudo -u omnicheck env PGPASSFILE=/etc/omnicheck-ai/pgpass \
  pg_dump -h 192.168.118.81 -p 5444 -U omnicheck_app \
  -d omnicheck_app -Fc -f /data/omnicheck/archive/omnicheck_app.dump
```

實際使用 `/usr/edb/as17/bin/pg_dump` 或相容 client；restore 前驗證 server/client major version。正式環境也可納入現有 pgBackRest／Barman，但 metadata database 的 restore 步驟必須實測。

### 16.3 Filesystem backup 一致性

先停止建立新案件，或使用 storage snapshot。最保守作法：

```bash
systemctl stop omnicheck-worker omnicheck-web
rsync -aHAX --numeric-ids /data/omnicheck/jobs/ <BACKUP_TARGET>/jobs/
systemctl start omnicheck-web omnicheck-worker
```

`<BACKUP_TARGET>` 必須是核准且容量足夠的位置。不要把 customer data 推到 Git。

### 16.4 復原驗證

- 先復原到隔離 staging。
- 比對 job directory SHA-256。
- restore EDB 後檢查 job counts／events／Alembic revision。
- 啟動 Web／Worker，挑一個既有 succeeded job 確認下載。
- 建立新 Golden job 確認 queue 與 Renderer。

## 17. 升級與 Rollback

### 17.1 升級前

- 確定目標 tag／commit、release notes、migration revision。
- 完成 EDB 與 `/data` backup。
- staging 完整測試與 PDF QA。
- 記錄目前 `readlink -f /data/omnicheck/app/current`、Git SHA、pip freeze。

### 17.2 Rolling application upgrade

```bash
systemctl stop omnicheck-worker omnicheck-web
# 安裝新 release 目錄與新 venv，先不要覆蓋舊版
# 執行 alembic upgrade head（若有）
ln -sfn /data/omnicheck/app/releases/<NEW_VERSION> /data/omnicheck/app/current
systemctl start omnicheck-web omnicheck-worker
curl --fail http://127.0.0.1:8000/api/health
```

### 17.3 Application rollback

若 migration 向下相容，可停止服務、把 `current` 指回舊 release、啟動並驗證。Git 操作使用 tag 建分支，不使用 `git reset --hard`：

```bash
git switch -c rollback/m8.1 m8.1
```

### 17.4 Database rollback

Git rollback 不會自動 rollback schema。若新程式已寫入新格式，直接切舊版可能不相容。優先採 forward fix；需要 downgrade 時，停止 Web／Worker、備份、在 staging 演練，再經核准執行精確 revision。`0001_m9_3` downgrade 會刪除 `jobs` 與 `job_events`。

## 18. 故障排除

### Web 回 503

```bash
journalctl -u omnicheck-web -n 200 --no-pager
sudo -u omnicheck env PGPASSFILE=/etc/omnicheck-ai/pgpass \
  psql -h 192.168.118.81 -p 5444 -U omnicheck_app -d omnicheck_app -c 'select 1'
```

檢查 DNS／routing／firewall／pg_hba／pgpass mode／TLS，不要把 health endpoint 改成永遠 200。

### Job 卡在 queued

檢查 Worker active、environment、EDB event、`available_at` 與 attempts。禁止直接把 EDB status 改成 succeeded。

### Job 卡在 running

檢查 `claimed_by`、`claimed_at`、Worker process 與 journal。stale recovery 預設 3600 秒；不要在 Worker 仍活著時手動 requeue。

### PDF 無中文或版面改變

比較 `libreoffice --version`、`fc-match`、`fc-list :lang=zh-tw`。重建 font cache，重新 render。不要用另一套未核准字型直接交付。

### Quality gate 失敗

查看 `qa-result.json`、`v4-qa-result.json`、pending scope 與 Primary identity。修正 job config 或補證據；禁止改 JSON 把 gate 改成 pass。

### 磁碟不足

先停止新案件、找出大目錄並依 retention 移到 archive。刪除 customer data 是破壞性操作，必須依核准保留政策；不可直接 `rm -rf /data/omnicheck/jobs`。

## 19. 安全基準

- App user 與 DB user 都採最小權限，不可 superuser/root 常駐。
- Secret 不進 Git、不放 command line、不顯示於 journal。
- pgpass `0600`；env `0640`；job directories `0750` 或更嚴格。
- 正式 EDB 使用 TLS `verify-full` 與 DNS/VIP。
- Web 正式對外前需 reverse proxy、TLS、登入、RBAC、稽核；目前 M9.3 UI 尚未完成這些功能，因此只能放受控內網。
- input 上傳防 path traversal、重複檔與覆寫，但仍需上傳大小／惡意檔案／防毒政策。
- 客戶資料不提交 Git，不送外部 AI。

## 20. 開發者重建與變更流程

```bash
git clone <APPROVED_GIT_URL>
cd codex-handoff
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

每個 milestone：

1. 讀 `AGENTS.md`、本手冊、`PROJECT_RUNBOOK.md`、Pipeline／Acceptance。
2. 先新增 fixture／失敗測試，再改程式。
3. 跑相關測試與完整測試。
4. 跑 V4 manifest 與 Golden。
5. 用指定實際客戶資料唯讀驗證，前後比對 hash。
6. 報告變更產生 DOCX/PDF 並逐頁檢查。
7. 更新 validation、runbook 與本手冊。
8. 執行 `git diff --check` 與 secret/customer-data review。
9. 功能分支 push；驗收後才 merge main、重跑、tag。

## 21. 主手冊維運流程

任何下列變更都必須更新本文件：依賴或 package、Python／LibreOffice／EDB 版本、目錄、port、environment variable、migration、service、Pipeline 產物、操作畫面、備份、監控、權限、驗證、rollback、milestone 狀態。

更新步驟：

```bash
# 1. 修改 Markdown 與修訂紀錄
# 2. 重新產生 DOCX
.venv/bin/python scripts/build_operations_guide.py
# 3. 依 documents skill render DOCX，逐頁檢查
# 4. 確認 Markdown/DOCX/程式同一 commit 提交
git diff --check
```

Reviewer 必須抽查至少一條全新建置路徑、一條升級路徑、一條 rollback 路徑，以及所有新增命令。尚未實機執行的內容要標示「待驗證」，不得改寫成「已完成」。

## 22. 已知限制與後續工作

- M9.3 已在公司 `.77/.81` 通過 migration、systemd、EDB queue、retry、SCRAM／pgpass、DOCX/PDF、重啟持久性、Golden 與實際客戶資料 E2E。
- 台灣行動支付實際資料在 SCRAM 重啟後通過 13 inputs／13 outputs、QA 8/8、V4 QA、29 頁 PDF 與來源 SHA-256 不變。
- `.81` 的 OMNIcheck 精確規則已要求 SCRAM；cluster-wide `host all all 0.0.0.0/0 trust` 仍是其他連線的安全風險，需另案收斂。
- 兩次修正前 API 500 留下兩筆空的 draft Golden 測試案件；尚未執行破壞性清除。
- 正式 TLS/VIP、EFM failover、reverse proxy、登入／RBAC 尚未完成。
- 完全未知資料包尚不能自動決定節點角色，仍需使用者確認。
- Barman 真實 wrapper fixture 待提供。
- Python dependency 目前為 version ranges，正式 reproducible build 尚需 lock／wheelhouse。
- 歷史比較、CVE cache、可選 AI gateway 尚未實作。
- EDB 中心化與 CVE 自動化方向已核准，但 Persistence Adapter、Application Data tables、Artifact Registry 與 CVE tables 尚未實作。

## 附錄 A：官方與專案依據

- EDB EPAS 17 Linux 安裝：<https://www.enterprisedb.com/docs/epas/17/installing/>
- EDB EPAS 17 RHEL 9 安裝（依 CPU architecture 選頁面）：<https://www.enterprisedb.com/docs/epas/17/installing/linux_x86_64/>
- EDB Failover Manager 安裝與操作：<https://www.enterprisedb.com/docs/efm/latest/installing/>、<https://www.enterprisedb.com/docs/efm/latest/05_using_efm/>
- Python venv：<https://docs.python.org/3/library/venv.html>
- 專案規範：`AGENTS.md`、`docs/PIPELINE_SPEC.md`、`docs/ACCEPTANCE_CRITERIA.md`
- M9.3：`docs/M9_3_EDB_QUEUE.md`、`docs/M9_3_VALIDATION.md`
- M9.4～M15 架構決策：`docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md`

## 附錄 B：交付驗收簽核表

| 檢查 | 結果／證據 |
|---|---|
| OS／CPU／disk／time baseline 保存 | |
| Package 與版本符合手冊 | |
| App commit/tag 固定 | |
| DB user 非 superuser、schema owner 正確 | |
| pgpass/env 權限正確 | |
| Alembic at head | |
| Web／Worker active | |
| `/api/health` database/external | |
| Pytest 0 failed | |
| V4 manifest 全部 OK | |
| Golden Regression 通過 | |
| 實際資料來源 hash 無異動 | |
| QA/V4 QA delivery allowed | |
| DOCX/PDF 逐頁通過 | |
| Backup 與 restore drill 通過 | |
| Rollback point 記錄 | |
