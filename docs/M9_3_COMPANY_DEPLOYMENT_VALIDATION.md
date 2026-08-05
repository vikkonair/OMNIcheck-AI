# M9.3 公司環境部署驗證

日期：2026-08-05  
程式版本：`8faff37`  
狀態：Core deployment passed；安全強化與實際客戶資料待完成

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

- `current`：`/data/omnicheck/app/releases/8faff37`
- Alembic：`0001_m9_3 (head)`
- Tables：`omnicheck.alembic_version`、`jobs`、`job_events`
- `omnicheck-web`：enabled／active
- `omnicheck-worker`：enabled／active
- Health：`metadata=database`、`worker=external`
- Firewall：TCP 8000 opened
- 完整測試：59 passed

## 實機發現與修正

1. EPAS Redwood `DateStyle` 讓 psycopg 3 無法解析 `timestamptz`。修正為只在 OMNIcheck connection session 強制 `DateStyle=ISO`，不改 EDB 全域模式。Commit：`ebf9332`。
2. Linux 誤套 `config/fonts.macos.conf`，導致 LibreOffice 看不到系統字型。修正為 macOS 才設定該 fontconfig；Linux 使用系統 Noto CJK。Commit：`8faff37`。
3. 一般 wheel 安裝不包含 repository 外的 V4 vendor bundle。目前部署以固定 source release + editable link；後續應將 bundle 正式 package 化。

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

## 尚待完成

- 使用台灣行動支付實際資料在公司 VM 執行唯讀 E2E，並比對來源前後 SHA-256。
- 將 `.81` application connection 改為 SCRAM password；建立 `/etc/omnicheck-ai/pgpass` 0600。
- 正式 TLS `verify-full`、VIP／DNS 與憑證。
- 實際停止 Worker 超過 lease，驗證 stale recovery。
- 經核准清理修正前留下的兩筆空 draft Golden job。
