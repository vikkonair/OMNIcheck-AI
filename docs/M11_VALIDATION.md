# M11 Validation Report

日期：2026-08-10  
分支：`feature/m11-auth-rbac-audit`  
狀態：Paused by product decision；功能分支與 schema 保留，公司 application 已 rollback 至 M10

## 已通過

- PBKDF2 salt、正確密碼與錯誤密碼驗證。
- 未登入 API 回 401；登入失敗及成功寫入 Audit。
- Engineer 可在授權 Customer 建案，跨 Customer 建案回 403，Job list 只顯示授權資料。
- Viewer 無建案權限；Logout 撤銷 Session。
- Platform admin 可存取未綁 tenant 的 legacy Job。
- 停用 User 後既有 Session 立即失效。
- 跨站 state-changing request 回 403；安全 response headers 存在。
- SQLite test schema 包含四張 M11 table。
- PostgreSQL dialect offline upgrade／downgrade SQL 可完整產生；upgrade 指向 `0005_m11`，downgrade 會刪除四張表。
- Reviewer 只能查詢已授權 Customer 的 Audit，不會看到其他租戶事件。
- Auth/Web targeted tests：14 passed；完整回歸目前 87 passed（後續變更需重跑，以 0 failed 為準）。

## 尚待完成

- 由使用者在安全終端建立第一個 platform admin；密碼不得貼入聊天。
- 建立公司測試 Customer／System 與 Engineer／Reviewer／Viewer grants。
- 瀏覽器逐角色驗收、跨 Customer API 負向測試、Audit 查詢與服務重啟持久性。
- 台灣行動支付資料唯讀 E2E、QA／V4 QA 與來源 manifest 回歸。
- 使用者驗收後才可合併 `main`、建立 `m11` tag。

## 公司環境階段驗證

- App VM `.77`／EPAS 17.10 `.81` precheck：M10 release `6e8ee6e`、revision `0004_m9_6`、Web／Worker active、health 正常。
- 升級前 backup：`omnicheck_app_pre_m11_20260810.dump`，67 KiB，SHA-256 `0a27b7ea507d97d2605e0a1180aaef5d9dd5c84b106dafcfd89f30d5d0901bd4`，`pg_restore --list` passed。
- M11 release：`d93da78`；archive SHA-256 `705e0c3781f2087a283250b11246f3c4c76eceae4d910ef77e6b40d09a53839b`，本機與 VM 一致。
- 公司 VM 完整測試：87 passed；V4 manifest 5／5 OK。
- `0004_m9_6 → 0005_m11` transactional migration passed；四張 M11 table 存在，總計 23 張 application tables。
- Current release 指向 `d93da78`；Web／Worker active、health 正常、journal 無 error。
- Auth 暫維持 disabled，避免第一個平台管理員建立前鎖住 Web。

## 使用者決定與 Application Rollback

使用者登入 smoke test 後決定目前先不要登入功能及授權 Customer／System 欄位。公司環境已完成非破壞性 application rollback：

- 還原 `/etc/omnicheck-ai/omnicheck.env.pre_m11_auth`。
- 重新安裝並切回 M10 release `6e8ee6e`，不是只切 symlink。
- Web／Worker active、health 正常、Jobs API 無登入回 200、M11 登入頁不存在。
- Python import path 指向 `/data/omnicheck/app/releases/6e8ee6e`；journal 無 error。
- EDB revision 保留 `0005_m11`，四張 additive tables 不刪除；M10 會忽略它們。
- 正式 `main`／`m10` 從未移動，因此 Git rollback 點不變。
