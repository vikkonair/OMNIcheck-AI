# M11 Validation Report

日期：2026-08-10  
分支：`feature/m11-auth-rbac-audit`  
狀態：In progress；本機基礎驗證通過，公司環境尚未驗證

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

- 公司 `.77/.81` EDB backup、`0005_m11` migration 與 constraint 查核。
- 由使用者在安全終端建立第一個 platform admin；密碼不得貼入聊天。
- 建立公司測試 Customer／System 與 Engineer／Reviewer／Viewer grants。
- 瀏覽器逐角色驗收、跨 Customer API 負向測試、Audit 查詢與服務重啟持久性。
- 台灣行動支付資料唯讀 E2E、QA／V4 QA 與來源 manifest 回歸。
- 使用者驗收後才可合併 `main`、建立 `m11` tag。
