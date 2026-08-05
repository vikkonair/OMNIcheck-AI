# M9.3 公司環境部署驗證

日期：2026-08-05  
程式版本：`a1d286f`
狀態：Passed；已合併 `main` 並建立 `m9.3` 正式回復點

## 環境

- App：`omnicheck-ai-app`／`192.168.118.77`／CentOS Stream 9 x86_64
- Data：`/data/omnicheck`，XFS，約 46 GB 可用
- Python：3.12.13
- LibreOffice：7.1.8.1
- Font：Noto Sans CJK TC
- EDB：EPAS 17.10，`192.168.118.81:5444`
- Database／User／Schema：`omnicheck_app`／`omnicheck_app`／`omnicheck`
- TLS：off（測試環境）

## 部署結果

- `current`：`/data/omnicheck/app/releases/a1d286f`
- Alembic：`0001_m9_3 (head)`
- Tables：`omnicheck.alembic_version`、`jobs`、`job_events`
- `omnicheck-web`：enabled／active
- `omnicheck-worker`：enabled／active
- Health：`metadata=database`、`worker=external`
- Firewall：TCP 8000 opened
- 完整測試：60 passed（本機與公司 VM）

## 實機發現與修正

1. EPAS Redwood `DateStyle` 讓 psycopg 3 無法解析 `timestamptz`。修正為只在 OMNIcheck connection session 強制 `DateStyle=ISO`，不改 EDB 全域模式。Commit：`ebf9332`。
2. Linux 誤套 `config/fonts.macos.conf`，導致 LibreOffice 看不到系統字型。修正為 macOS 才設定該 fontconfig；Linux 使用系統 Noto CJK。Commit：`8faff37`。
3. 一般 wheel 安裝不包含 repository 外的 V4 vendor bundle。目前部署以固定 source release + editable link；後續應將 bundle 正式 package 化。
4. 實際客戶 PDF 在 Linux LibreOffice 出現「更新與建議」孤立標題頁。原因是摘要表格所有列被 `keep_with_next` 串接；修正為只串接表頭與第一筆資料，新增 20 筆摘要回歸測試。Commit：`a1d286f`。

## Golden E2E

- Dataset：去識別 `jiuxing_v4`
- Job ID：`ae97be8739b44d7591a5acccecfa65b9`
- Files：3
- 最終狀態：succeeded
- Attempts after retry reset：1
- Outputs：13
- PDF：10 pages，A4，182,016 bytes
- Embedded fonts：Noto Sans CJK、Liberation Sans、DejaVu Sans、Carlito
- M6 QA：8 passed／0 failed／delivery allowed
- V4 QA：passed／delivery allowed
- 10 頁 PDF：逐頁目視無缺字、截斷或重疊
- Web／Worker restart 後：EDB status、13 outputs 與下載均保留

## 實際客戶資料 E2E

- Dataset：台灣行動支付 2026 上半年（來源只讀）
- SCRAM 後最終 Job ID：`330b228499c04b96b87ff510ba0d8ac8`
- 有效上傳：13 個檔案；來源清單：14 個檔案（含 `.DS_Store`）
- 最終狀態：succeeded；attempts：1；outputs：13
- Scope：11 allowed／2 excluded／0 pending
- Database：只採 `twmpedbp1` Primary；Standby 與 PEM backend database 正確排除
- Monitoring：5 張圖片依既定政策映射至 `twmpedbp1` Primary
- M6 QA：8 passed／0 failed／delivery allowed
- V4 QA：passed／delivery allowed
- PDF：29 頁 A4；逐頁目視無缺字、重疊、裁切或孤立章節標題
- 來源 14 個檔案執行前後 SHA-256 manifest 一致

## SCRAM 與 pgpass

- EPAS `password_encryption`：`scram-sha-256`
- 在既有寬鬆規則前新增精確規則：database/user `omnicheck_app`、來源 `192.168.118.77/32`、`scram-sha-256`
- 未移除既有 cluster-wide 規則，避免影響其他應用；其風險留待獨立 EDB 安全強化變更處理
- `pg_hba.conf` 備份：`/pgdata/as17/data/pg_hba.conf.pre-m9.3-scram-20260805`
- Reload 成功；`pg_hba_file_rules` error count：0；未重啟 EDB
- `.77` `/etc/omnicheck-ai/pgpass`：`omnicheck:omnicheck`、mode `0600`
- 無密碼連線：拒絕；受控 pgpass：成功
- Web／Worker 重啟後：enabled／active；health `metadata=database`、`worker=external`
- 密碼輪替暫存明文已安全清除，密碼未寫入 Git、文件或驗證輸出

## 不阻擋 M9.3 的後續工作

- 正式 TLS `verify-full`、VIP／DNS、憑證、EFM failover 與完整 HA 演練納入 M15。
- Stale lease 已有自動測試；實際長時間中斷演練納入維運演練窗口。
- 既有 cluster-wide `host all all 0.0.0.0/0 trust` 是獨立安全風險，需盤點所有使用者後另案收斂。
- 經核准清理修正前留下的兩筆空 draft Golden job。
