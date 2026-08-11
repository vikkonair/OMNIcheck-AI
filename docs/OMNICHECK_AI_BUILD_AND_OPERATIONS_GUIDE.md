# OMNIcheck AI 建置、部署與維運主手冊

文件編號：OMNI-OPS-001  
文件版本：0.10.3-draft.1
最後更新：2026-08-10
適用程式基準：`feature/m10-3-section-foundation`；正式基準仍為 `main` / `m10.1`
正式可回復基準：`m10.1`；前一個 application rollback 點為 `m10`
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
| 0.10.3-draft.4 | 2026-08-11 | 聯詠 walsender／walreceiver topology、OS／DB 標題相容、zero-row 與 coverage ID | release `327748d`；本機 93 tests、公司相關 28 tests、Discovery API、health、PDF 與來源 hash 通過 |
| 0.10.3-draft.3 | 2026-08-11 | 修正無 Primary 時 Database Output 誤顯示 DR、人工修正後重新開放確認 | 本機 88 tests、公司 VM targeted 11 tests、health／UI marker／per-release process 通過；rollback `a0582a0` |
| 0.10.3-draft.2 | 2026-08-11 | 同仁 UI Adapter 公司候選部署、per-release venv、systemd release isolation、deploy lock／owner | 公司 release `a0582a0` 87 tests；Golden Web → EDB Queue → Worker → V4、QA、重啟持久性通過；待使用者驗收 |
| 0.10.3-draft.1 | 2026-08-11 | AI-optional Section Workflow JSON、draft／review／approval 分離、Artifact 關係與無 migration rollback | 本機／公司 VM 85 tests；台灣行動支付 14 檔／19 sections、公司 ENGDB 3 檔／9 sections、QA/V4 QA、DOCX/PDF 與來源 hash 通過；待使用者驗收 |
| 0.10.3-draft.2 | 2026-08-11 | 0007 schema reconciliation、EDB Section current/revision persistence、review/approval API、approved-only Renderer | 本機 97 tests；Alembic 單一 head `0008_m10_3_sections`；Golden approved overlay、QA/V4 QA 通過；待公司 migration/E2E |
| 0.10.1 | 2026-08-10 | 舊式 Database Output 內容分類、來源節點候選、人工 evidence mapping、Scope 稽核與使用者驗收 | 本機／公司 VM 82 tests；實際 ENGDB 3 檔、17 項 Primary checks、QA/V4 QA、19 頁 PDF、來源 hash 與公司 Web 驗收通過 |
| 0.10.0 | 2026-08-10 | M10 deterministic topology discovery、人工確認、稽核來源、Web gate、2.1 節點 Database 清冊與公司正式部署 | 本機／公司 VM 78 tests；台灣行動支付 13 檔、5 節點、QA/V4 QA、DOCX/PDF、來源 hash、Queue/Worker、EDB 持久性與重啟通過 |
| 0.9.6 | 2026-08-10 | M9.6 公司 EDB deployment、Scoped Artifact E2E 與正式回復點 | Backup/hash、VM 74 tests、`0004_m9_6`、冪等、archive dry-run 與 restart 通過 |
| 0.9.6-draft.1 | 2026-08-05 | Artifact version、derivation、event、Retention 與 copy-verify archive | 本機 74 tests、offline migration 與實際資料唯讀驗證通過；公司 EDB 待驗證 |
| 0.9.5 | 2026-08-05 | M9.5 公司 EDB deployment、Scoped Golden Persistence 與正式回復點 | Backup/hash、VM 70 tests、`0003_m9_5`、冪等、restart persistence 與 health 通過 |
| 0.9.5-draft.1 | 2026-08-05 | 新增 M9.5 scoped Pipeline snapshot、row-level persistence、冪等與 failure gate | 本機 70 tests、offline migration 與實際資料唯讀投影通過；公司 EDB 待驗證 |
| 0.9.4 | 2026-08-05 | M9.4 合併 main 並建立正式回復點 | 合併後 tests、V4 manifest 與文件 render 通過 |
| 0.9.4-draft.2 | 2026-08-05 | 完成公司 `.77/.81` M9.4 migration、release 切換與 live Queue 驗收 | Backup/hash、VM 65 tests、`0002_m9_4`、constraints、rollback smoke、health 與 Golden Job 通過 |
| 0.9.4-draft.1 | 2026-08-05 | 新增 M9.4 Customer／System／Node／Topology／Evidence／Artifact、tenant scope 與 `0002_m9_4` migration 手順 | 本機 65 tests、offline upgrade/downgrade、實際資料隔離投影與來源 hash 通過；公司 EDB 待驗證 |
| 0.9.3 | 2026-08-05 | M9.3 合併 main 並建立正式回復點 | 合併後 60 tests、V4 manifest 與文件 render 通過 |
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
5. 驗證 M1～M9.3 的輸出、Golden Regression 與 PDF 字型，以及 M9.4 application data foundation。
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
| M9.3 實機 | 正式完成 | 公司 EDB、systemd、SCRAM／pgpass、Golden、實際資料、DOCX／PDF 與重啟持久性通過 |
| M9.4 | 正式完成 | Customer／System／Node／Topology／Evidence／Artifact、tenant key、公司部署與 live Queue 驗收 |
| M9.5 | 正式完成 | Scope／Normalized／Config／Assessment／Coverage／QA 冪等 EDB 投影與公司部署 |
| M9.6 | 正式完成 | Artifact version、derivation、events、Retention、copy-verify archive 與公司部署 |
| M10 | 正式完成 | 未知資料包的確定性節點／角色／服務候選、人工確認、fail-closed gate 與公司部署 |
| M10.1 | 正式完成 | 舊式 Database Output 內容辨識、來源節點候選、人工 mapping 與 Primary-only 保護 |
| M10.2 | 完成、已合併主線 | 同仁新版 UI 接既有 API 與後端；保留 `/classic` fallback；per-release venv／deploy lock |
| M10.3.1 | 完成 | Section Workflow JSON、AI 草稿／人工審查／核准與 fail-closed selected source |
| M10.3.2 | 程式完成、待公司 E2E | 相容 migration chain、EDB current/revision persistence、Section API、approved-only Renderer |
| M11～M15 | 已核准、待實作 | 選配權限、歷史、CVE、Ollama AI Gateway 與生產強化 |

`main`／`m10.1` 是目前正式可回復版本；`m10` 保留為 M10.1 前的 application rollback 點。正式重建應 checkout `m10.1`，不得部署 floating branch HEAD。

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

### 3.3 M9.4 起的目標資料架構

詳細權威決策為 `docs/EDB_CENTRIC_AND_CVE_ARCHITECTURE.md`。實作原則如下：

- EDB 逐步成為結構化應用資料、歷史、規則結果與 CVE Cache 的主要查詢來源。
- `/data` 繼續保存原始證據、圖片、壓縮檔、Canonical JSON、DOCX、PDF 與 Render 暫存檔。
- EDB 對大型檔案只保存 `storage_backend`、`storage_key`、hash、大小、media type、保留與封存狀態。
- Canonical JSON 不取消；它是不可變 Pipeline／Renderer 契約、Golden、除錯、重建與 rollback 保護。
- Pipeline 後增加冪等 Persistence Adapter；持久化失敗時 Job 不得標成 succeeded。
- Customer／tenant key 從 M9.4 進資料模型；M11 再完成 Login／RBAC／Audit enforcement。
- CVE 由固定官方來源排程同步，Version Matcher 確定性判斷；AI 不決定漏洞適用性。

M9.4 已建立 `customers`、`systems`、`nodes`、`topology_relations`、`evidence_files`、`artifacts`，並為 `jobs` 加入 nullable tenant scope；M9.5 已完成 Pipeline Persistence，M9.6 已完成 Artifact lifecycle。通用排程器與 AI Gateway 尚未完成。

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
OMNICHECK_PERSIST_RESULTS=true
OMNICHECK_REGISTER_ARTIFACTS=true
OMNICHECK_ARTIFACT_RETENTION_DAYS=365
OMNICHECK_STORAGE_ROOT=/data/omnicheck
OMNICHECK_ARCHIVE_ROOT=/data/omnicheck/archive
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

正式 `m9.3` revision 為 `0001_m9_3`。M9.4 為 `0002_m9_4`，並新增 application foundation；M9.5 為 `0003_m9_5`。M9.6 正式 revision 為 `0004_m9_6 (head)`。

```sql
SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema='omnicheck' ORDER BY 2;
SELECT version_num FROM omnicheck.alembic_version;
```

Alembic downgrade 會刪表，屬破壞性操作；只有完成 metadata backup 並取得明確核准後才能執行。

### 10.3 M9.4 migration 手順

公司 `.77/.81` 已依下列流程完成；新環境或後續升級仍必須重做：

1. 停止 Web／Worker，記錄目前 app commit 與 `alembic current`。
2. 使用 `pg_dump -Fc` 備份 `omnicheck_app`，並確認備份檔大小與 checksum。
3. 在隔離 staging restore，演練 `upgrade 0002_m9_4`、基本 CRUD 與回復。
4. 公司測試 EDB 執行 `alembic upgrade 0002_m9_4`。
5. 查核六張新表、Job nullable tenant columns、FK／unique／check constraints。
6. 重啟 Web／Worker，確認既有 M9.3 Job 可讀、新 Job Queue／Worker E2E 通過。

需要回到 M9.3 schema 時，`alembic downgrade 0001_m9_3` 會刪除六張 M9.4 table、其中全部資料及 Job tenant columns。必須另行取得破壞性變更核准；通常優先保留 additive schema、切回 `m9.3` application 或採 forward fix。

公司驗證結果：升級前先保存 `/data/omnicheck/archive/omnicheck_app_pre_m9_4_20260805.dump`，SHA-256 為 `e07edb51bcab5d71e14c4de19ad5c539186bfc6ea650e658da2c8cf07e7822df`，且 `pg_restore --list` 可讀。Release `9dc7d76` 在 VM 通過 65 tests，schema 升至 `0002_m9_4 (head)`；六張新表、constraints、legacy Job、transaction rollback smoke、Web／Worker 與 live Golden Queue 均通過。完整 restore 與實際 downgrade drill 尚未執行。

### 10.4 M9.5 migration

`0003_m9_5` 新增 `pipeline_snapshots`、`scope_decisions`、`normalized_checks`、`normalized_unparsed`、`configuration_comparisons`、`pipeline_assessments`、`coverage_items`、`quality_results`。部署前先備份目前 `0002_m9_4`；升級後以完整 scoped Job 驗證 snapshot 與 child row counts。`alembic downgrade 0002_m9_4` 會刪除全部 M9.5 results，必須另行核准。

公司驗證結果：release `916adff` 在 VM 通過 70 tests 與 V4 hashes；備份 `/data/omnicheck/archive/omnicheck_app_pre_m9_5_20260805.dump` 的 SHA-256 為 `b1bab16fa5c006a8832a621dd9fce0fe2ce7a18c4025d0b290a865da030e1575`，且 `pg_restore --list` 可讀。Schema 升至 `0003_m9_5`，Scoped Golden Job `fa28fea9f9d04f53bbd96f209042fe44` succeeded 並建立 Snapshot `1be99fddb5404aa8add49a89146ee339`；冪等重寫、Web／Worker restart 與 health 均通過。Release 切換時必須同步重新安裝 editable package；health probe 應允許 Uvicorn 最多 30 秒啟動。

### 10.5 M9.6 migration

`0004_m9_6` 擴充 `artifacts` 並新增 `artifact_relations`、`artifact_events`。部署前先備份 `0003_m9_5`；升級後以 scoped Job 驗證 11 或 13 個輸出 Artifact、版本、relations、events 與冪等。Downgrade 會刪除 M9.6 metadata 與 version 2 以上 registry rows，必須另行核准；實體檔案不由 migration 刪除。

先用 dry-run 查看已到期項目，人工確認後才 apply：

```bash
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL="$(sed -n 's/^OMNICHECK_DATABASE_URL=//p' /etc/omnicheck-ai/omnicheck.env)" \
  OMNICHECK_STORAGE_ROOT=/data/omnicheck \
  OMNICHECK_ARCHIVE_ROOT=/data/omnicheck/archive \
  /data/omnicheck/venv/bin/omni-healthcheck-artifacts

# 經核准後才執行；只 copy + verify，不刪來源
sudo -u omnicheck env \
  OMNICHECK_DATABASE_URL="$(sed -n 's/^OMNICHECK_DATABASE_URL=//p' /etc/omnicheck-ai/omnicheck.env)" \
  OMNICHECK_STORAGE_ROOT=/data/omnicheck \
  OMNICHECK_ARCHIVE_ROOT=/data/omnicheck/archive \
  /data/omnicheck/venv/bin/omni-healthcheck-artifacts --apply
```

M9.6 不提供自動實體刪除。`pending_delete` 只代表已提出刪除申請，仍可取消；未經獨立備份、legal hold 檢查與明確核准，不得手動刪檔。

公司驗證結果：release `2fc2ce7` 在 VM 通過 74 tests 與 V4 hashes；備份 `/data/omnicheck/archive/omnicheck_app_pre_m9_6_20260810.dump` 的 SHA-256 為 `de79b27dc6d05a04f9415d4ef91b04132bde9ea7bc29b57bd38ebf84be4877e2`，且 `pg_restore --list` 可讀。Schema 升至 `0004_m9_6`，Scoped Golden Job `3c600f747da84d4e92f3c86f6fd0f6d3` 建立 11 artifacts、2 relations、11 events；冪等、Archive dry-run、archive manifest、Web／Worker restart 與 health 均通過。

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

使用者開啟 `http://<APP_VM>:8000/`，選取資料夾後由 M10 確定性 Discovery 提出 hostname、Primary／Standby／DR／Witness、服務、信心與理由。使用者必須核對並勾選確認，系統才建立案件、上傳不可覆寫資料、交由 Worker 執行並提供下載。Discovery 不取代 DBA 決策；Primary 候選不唯一、未知或衝突時必須人工修正。

Discovery API 只取文字檔前 512 KiB 作樣本；圖片不解析內容。確認紀錄保存在 `job.yaml.topology_confirmation`，`topology.json` 會標記 `operator_confirmed_discovery`。此功能不新增 migration、package 或環境變數；回復至 `m9.6` 不需 database downgrade。

M10.1 對沒有 hostname 的 `ENGDB_check.txt` 類型文字檔進行 Database Output 內容分類。若不能唯一對應節點，畫面會在「Database Output 來源確認」列出候選並要求使用者選擇；結果保存於 `job.yaml.evidence_mappings`，Scope ledger 記錄 `operator_confirmed_evidence_mapping`。候選不等於自動採用，未確認時保持 pending；映射到 Standby／DR／Witness 也不會繞過 Database logical Primary-only policy。

報告 2.1 的 Database 欄是節點軟體清冊，不是邏輯資料 Scope：Primary／Standby／DR 都顯示案件的 PostgreSQL／EPAS 產品；承載 PEM Server 的 Witness 顯示 `PostgreSQL` backend；只有 EFM 且沒有資料庫服務證據的 Witness 留白。Database／Schema／Table 等後續判斷仍只採 Primary。

## 13. 驗證與驗收

### 13.1 程式測試

```bash
cd /data/omnicheck/app/current
/data/omnicheck/venv/bin/pytest
git diff --check
```

公司 M9.3 正式基準為 60 tests、M9.4 為 65 tests、M9.5 為 70 tests、M9.6 為 74 tests、M10 為 78 tests、M10.1 為 82 tests；M10.3.1 候選為 85 tests。實際數量會隨版本增加，不應硬性只等於固定數字；重點是 0 failed。

M10.2 UI Adapter 公司候選為 88 tests，新增 UI Adapter、路由、fail-closed 畫面行為與 deployment contract tests，未增加 migration 或更換 Pipeline。`/` 與 `/integrated` 為新版介面，`/classic` 為原介面 fallback。第一階段不得部署同仁版本的 Login/RBAC、Knowledge/CVE、GPDB、`0005`～`0007` migration 或整份 `web.py`。Database Output 沒有 Primary suggestion 時，UI 必須顯示「請選擇來源節點」，不得預選排序第一台 DR；人工修正為唯一 Primary 並完成全部來源映射後，確認 checkbox 才可啟用。公司 release `a0582a0` 使用獨立 `.venv`，Web／Worker systemd 已改用 `current/.venv`；切換時持有 `/data/omnicheck/app/deploy.lock` 並保存 owner／commit／previous／rollback metadata。Golden Job `2a8d40b0727c41119236fd6642cd2ec2` 已完成 Web → EDB Queue → Worker → 12 個 Canonical/V4 產物，QA/V4 QA 均允許交付，服務重啟後案件仍可由 EDB 讀回。公司 EDB revision `0007_m13_catalog` 並非本分支 migration head，本次未執行 migration 或 downgrade；待 schema reconciliation 後才進行 Section persistence/API。

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

### 13.7 M9.4 application data 驗收

- Legacy M9.3 Job 在 `customer_id/system_id` 為 `NULL` 時仍可運作。
- Customer 內可建立 System 與 Primary／Standby／DR／Witness Node。
- Topology source／target 必須屬於同一 Customer／System。
- 已關聯 Job 不得改掛另一個 tenant。
- Evidence／Artifact 只能使用安全相對 storage key，且保存 SHA-256、size、media type。
- 大型原始檔與報告留在 `/data`，EDB 不存 `BYTEA`。
- 實際客戶資料只讀投影前後 manifest 必須一致。

### 13.8 M9.5 Pipeline persistence 驗收

- Scoped Job 完成後必須有且只有一個 `pipeline_snapshots` row。
- Scope、Normalized、Unparsed、Config、Assessment、Coverage、QA child rows 必須可依 tenant 查詢。
- 相同 Job、schema 與 Canonical SHA-256 重跑必須回傳既有 Snapshot。
- Persistence 失敗時 Job 不得標為 succeeded；Legacy unscoped Job 仍可執行。
- Web／Worker restart 後 Snapshot、Job status 與 output 必須仍存在。

### 13.9 M9.6 Artifact lifecycle 驗收

- Scoped Job 每個 output 必須登錄一筆 Artifact，並保存 version、SHA-256、size、media type 與 retention。
- 相同檔案重跑不得重複；內容變更必須升版並建立 `supersedes` relation。
- Canonical、Report Model、V4、DOCX、PDF 的衍生關係與事件必須可查。
- Archive 預設 dry-run；未到期時 count 必須為 0，archive manifest 不得改變。
- Apply 必須 copy、驗 hash、保留來源；M9.6 不自動實體刪除。
- Web／Worker restart 後 Artifact、relations、events 與 Job status 必須仍存在。

### 13.10 M10 拓撲探索驗收

- 未知資料包必須先顯示節點、角色、服務、信心與判斷理由；未人工確認不得建立案件。
- Primary 候選不唯一、角色衝突或無法解析時必須要求修正，不得由 AI 猜測。
- `topology.json` 必須記錄 `operator_confirmed_discovery`，並維持邏輯資料 Primary-only 與設定檔跨節點比較規則。
- 2.1 Database 清冊須顯示 Primary／Standby／DR 的案件產品及 PEM Server 的 PostgreSQL backend，不得用 Primary-only Scope 隱藏節點安裝資訊。
- 公司基準為 release `6e8ee6e`、78 tests；Job `12c90aa3da354f1c83dbc42e6d57e118` 的 13 inputs／13 outputs、QA、V4 QA、來源 manifest 與重啟持久性均通過。
- M10 不新增 migration；EDB revision 維持 `0004_m9_6`，application rollback 使用 `m9.6`。

### 13.11 M10.1 舊格式 Database Output 驗收

- 沒有 hostname 的舊式 Database Output 必須依內容列為候選，不得誤分類成一般 misc 後靜默略過。
- 使用者未選擇來源節點前不得把候選當成正式 Primary evidence。
- `evidence_mappings` 必須使用安全相對路徑、已配置節點與 database domain；重複路徑或未知節點必須拒絕。
- 映射至非 Primary 節點時仍要遵守 Database logical Primary-only。
- 實際 ENGDB 基準為 3 allowed、0 pending、17 項 Primary checks、QA 8/8、V4 QA、19 頁 PDF；來源 hash 不變。
- M10.1 不新增 migration、套件或環境變數；application rollback 使用 `m10`。

### 13.12 M10.3.1 Section Workflow 驗收

- `section-workflow.json` 必須使用 `omnicheck.section-workflow`／schema `1.0`。
- 初始 item 必須全部為 `generated`，selected source 為 deterministic template。
- 加入 AI draft 不得改變 status、evidence、rule trace 或 selected source。
- 未經 engineer review 不得 approve；未 approve 不得選用 AI／人工文字。
- `renderer_uses_ai=false`，既有 V4 report 與版面不得改變。
- 實際資料來源 manifest、QA、V4 QA、DOCX／PDF 必須通過。
- 本階段無 migration；application rollback 使用 `m10.1`。

### 13.13 M10.3.2 EDB Section persistence 部署與驗收

部署前先確認 migration head 與公司 current：

```bash
.venv/bin/alembic heads
PGPASSFILE=/etc/omnicheck-ai/pgpass /usr/edb/as17/bin/psql \
  -h 192.168.118.81 -p 5444 -U omnicheck_app -d omnicheck_app \
  -X -Atc "select version_num from omnicheck.alembic_version"
```

預期分別為 `0008_m10_3_sections` 與部署前的 `0007_m13_catalog`。先建立 schema-only 備份與 Alembic／新表清冊；備份檔保存於 `/data/omnicheck/archive/`，記錄 SHA-256。確認 0005～0007 migration 與同仁 source SHA-256 完全一致後，才允許：

```bash
cd /data/omnicheck/app/current
set -a
. /etc/omnicheck-ai/omnicheck.env
set +a
.venv/bin/alembic upgrade 0008_m10_3_sections
```

migration 只應新增 `section_workflows`、`section_workflow_items`、`section_workflow_revisions`。不得執行 `stamp`、`downgrade` 或刪除 0005～0007 tables。

API 驗收順序：

1. 建立並完成一個測試 Job，確認 Worker 自動保存 generated baseline。
2. `GET /api/jobs/{job_id}/sections` 取得 `item_id` 與 revision 1。
3. 不建立 AI draft，直接呼叫 review；確認 revision 2、selected source 仍為 deterministic。
4. 用舊 revision 核准，預期 HTTP 409。
5. 用 revision 2 核准，預期 revision 3、selected source 為 approved。
6. 呼叫 `/sections/render`，確認核准文字出現在 report-model/V4/DOCX/PDF。
7. 另選未核准 section，確認報告仍使用 deterministic 內容。
8. 查 revisions，確認 generated/reviewed/approved、actor、timestamp、content SHA-256 均存在。

Rollback 原則：Application 可切回上一 release；0008 tables留在 EDB 不影響舊程式。正式環境採 forward-fix，不執行 Alembic downgrade。誤核准內容以新 revision 修正並重新核准，不刪除歷史。

## 14. Pipeline 產物與判讀

| 檔案 | 代表意義 |
|---|---|
| `inventory.json` | 原始檔清冊、分類與 SHA-256 |
| `topology.json` | 節點角色與服務 |
| `scope-ledger.json` | 證據採用／排除／pending 的理由 |
| `normalized.json` | Parser 標準化結果 |
| `configuration-comparison.json` | Primary／Standby／DR 設定差異 |
| `assessment.json` | 規則狀態、證據、觀察、結論、建議 |
| `section-workflow.json` | 固定模板、AI 草稿、工程師審查／核准、版本及 selected source |
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
- M9.4 起另檢查 Customer／System／Node／Topology／Evidence／Artifact row counts 與孤兒外鍵。
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
git switch -c rollback/m9.3 m9.3
```

### 17.4 Database rollback

Git rollback 不會自動 rollback schema。若新程式已寫入新格式，直接切舊版可能不相容。優先採 forward fix；需要 downgrade 時，停止 Web／Worker、備份、在 staging 演練，再經核准執行精確 revision。`0003_m9_5 → 0002_m9_4` 會刪除全部 Pipeline snapshots 與 child rows；`0002_m9_4 → 0001_m9_3` 會刪除 M9.4 tables／data 與 Job tenant columns；`0001_m9_3 → base` 會刪除 `jobs` 與 `job_events`。

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
- M9.4 已正式化並部署公司 `.77/.81`：部署 release `9dc7d76`、Alembic `0002_m9_4`、Web／Worker active、Golden Job `cf384056cf7045878f12341324cb1852` succeeded。完整 restore／downgrade drill 尚待安排。
- M9.5 已部署公司 `.77/.81`：release `916adff`、Alembic `0003_m9_5`、70 tests、Scoped Golden Persistence、冪等與服務重啟均通過。
- M9.6 已部署公司 `.77/.81`：release `2fc2ce7`、Alembic `0004_m9_6`、74 tests、Scoped Artifact E2E、Archive dry-run、冪等與服務重啟均通過。
- M10 已部署公司 `.77/.81`：release `6e8ee6e`、EDB revision 維持 `0004_m9_6`，本機／VM 78 tests；台灣行動支付 13 檔自動提出 5 節點與唯一 Primary，人工確認 gate、Queue／Worker Job `12c90aa3da354f1c83dbc42e6d57e118`、13 outputs、QA、V4 QA、DOCX/PDF、來源 hash 與重啟持久性均通過。
- M10.1 已通過公司 Web 使用者驗收：候選 release `be0ca80`、本機／VM 82 tests；實際 ENGDB 來源確認後得到 17 項 Primary checks、QA/V4 QA、19 頁 PDF 與來源 hash 不變。正式 application 可回到 `m10`，不需 database downgrade。
- M10.3.1 公司候選 release `e56f043`：Web／Worker／EDB health 正常，公司 VM 85 tests；ENGDB 三檔產生 9 個 deterministic Section items、QA/V4 QA、DOCX/PDF 與來源 hash 通過。切換前曾偵測另一個開發套件使用同一 shared venv，後續多人部署必須採 deploy lock／release owner。
- M10.2 同仁 UI Adapter 公司候選已部署：目前 release `0a6dccd`；無 Primary 時 Database Output 顯示空白來源並強制人工選擇，節點修正為唯一 Primary 且全部映射完成後才可確認。本機 88 tests、公司 VM 相關 11 tests、health、UI marker 與 per-release process 通過；完整 Golden E2E 基準沿用前版 Job `2a8d40b0727c41119236fd6642cd2ec2`。rollback 為 `/classic` 或 application release `a0582a0`，無 database downgrade；EDB `0007_m13_catalog` schema reconciliation 仍待處理。
- 聯詠三檔唯讀回歸與公司部署：release `327748d`；walsender／walreceiver 自動提出 `OADB15N → Primary`、`OADB15-DR → DR`，Database Output 建議來源 `OADB15N`。normalized checks 29 → 49、coverage 50% → 92.5%；剩餘 missing 為來源未提供的兩台 Kernel version 與 Primary `pg_hba.conf`。本機 93 tests、公司相關 28 tests、Discovery API、health、Web／Worker process、QA/V4 QA、29 頁 PDF 與來源 SHA-256 不變均通過。rollback `0a6dccd`。
- 台灣行動支付實際資料在 SCRAM 重啟後通過 13 inputs／13 outputs、QA 8/8、V4 QA、29 頁 PDF 與來源 SHA-256 不變。
- `.81` 的 OMNIcheck 精確規則已要求 SCRAM；cluster-wide `host all all 0.0.0.0/0 trust` 仍是其他連線的安全風險，需另案收斂。
- 兩次修正前 API 500 留下兩筆空的 draft Golden 測試案件；尚未執行破壞性清除。
- 正式 TLS/VIP、EFM failover、reverse proxy、登入／RBAC 尚未完成。
- M10 可對標準搜集包提出角色候選；非標準檔名、缺少 EFM／OS 訊號或衝突時仍需使用者指定，且所有案件都必須人工確認。
- Barman 真實 wrapper fixture 待提供。
- Python dependency 目前為 version ranges，正式 reproducible build 尚需 lock／wheelhouse。
- 同仁 UI Adapter 已進入候選驗證；Section persistence/API、歷史比較、CVE cache 與 Ollama AI Gateway 尚未完成，順序與責任邊界見 `docs/MILESTONE_ROADMAP.md`。
- EDB 中心化與 CVE 自動化方向已核准；Application Data foundation、M9.5 Persistence Adapter 與 M9.6 Artifact lifecycle 已實作，CVE tables 尚未實作。

## 附錄 A：官方與專案依據

- EDB EPAS 17 Linux 安裝：<https://www.enterprisedb.com/docs/epas/17/installing/>
- EDB EPAS 17 RHEL 9 安裝（依 CPU architecture 選頁面）：<https://www.enterprisedb.com/docs/epas/17/installing/linux_x86_64/>
- EDB Failover Manager 安裝與操作：<https://www.enterprisedb.com/docs/efm/latest/installing/>、<https://www.enterprisedb.com/docs/efm/latest/05_using_efm/>
- Python venv：<https://docs.python.org/3/library/venv.html>
- 專案規範：`AGENTS.md`、`docs/PIPELINE_SPEC.md`、`docs/ACCEPTANCE_CRITERIA.md`
- M9.3：`docs/M9_3_EDB_QUEUE.md`、`docs/M9_3_VALIDATION.md`
- M9.4：`docs/M9_4_APPLICATION_DATA_FOUNDATION.md`、`docs/M9_4_VALIDATION.md`
- M9.5：`docs/M9_5_PIPELINE_RESULT_PERSISTENCE.md`、`docs/M9_5_VALIDATION.md`
- M9.6：`docs/M9_6_ARTIFACT_LIFECYCLE.md`、`docs/M9_6_VALIDATION.md`
- M10：`docs/M10_TOPOLOGY_DISCOVERY.md`、`docs/M10_VALIDATION.md`
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
