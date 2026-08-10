# M11 登入、RBAC、客戶隔離與 Audit

日期：2026-08-10  
狀態：功能分支保留；公司曾完成 `0005_m11` migration 與登入 smoke test，依使用者決定已將 application rollback 至 M10 並停用 Auth

## 目的

在不改變 M1～M10 Pipeline 與 V4 Renderer 的前提下，讓每個 Web 操作具備可識別操作者、明確角色、Customer 邊界與不可由 UI 繞過的 API 授權，並保存關鍵行為的 Audit event。

## 資料模型

`0005_m11` 以 additive migration 新增：

- `users`：本機帳號、PBKDF2-SHA256 password hash、啟用狀態及選配 `platform_admin`。
- `customer_memberships`：User 對 Customer 的 `engineer`／`reviewer`／`viewer` 授權。
- `user_sessions`：只保存 token SHA-256、期限與撤銷時間，不保存明文 token。
- `audit_events`：操作者、Customer、Job、action、outcome、request ID、client IP、details 與時間。

## 角色政策

| 角色 | 權限 |
|---|---|
| `platform_admin` | 跨 Customer 管理與存取，也可處理未綁 tenant 的 legacy Job |
| `engineer` | 授權 Customer 內讀取、建案、上傳、執行與下載 |
| `reviewer` | 授權 Customer 內讀取、下載、覆核與 Audit 查詢 |
| `viewer` | 授權 Customer 內唯讀與下載 |

非管理員看不到其他 Customer 的 Job；直接猜測 Job ID 也回 404。M11 正式模式要求新 Job 同時指定 `customer_id` 與 `system_id`。未綁 tenant 的舊 Job 只允許平台管理員存取。

## 安全邊界

- 密碼不得存明文或寫入 Git；建立帳號時由 CLI 互動式 `getpass` 輸入。
- Password hash 使用 PBKDF2-HMAC-SHA256、隨機 salt 與 600,000 iterations。
- Session cookie 為 HttpOnly、SameSite=Strict；TLS 環境必須設定 `OMNICHECK_COOKIE_SECURE=true`。
- 有 Origin 的跨站 state-changing request 會被拒絕；回應加入 nosniff、frame deny 與 no-referrer headers。
- 停用 User 後，既有 Session 立即失效。
- `OMNICHECK_AUTH_REQUIRED=false` 僅供升級前相容與隔離開發；正式啟用前必須先建立管理員。

## 啟用與 Rollback

部署順序：備份 EDB → migration `0005_m11` → 建立 platform admin → 建立 Customer grants → 測試登入 → 設定 `OMNICHECK_AUTH_REQUIRED=true` → 重啟 Web。Worker 不使用瀏覽器 Session，Pipeline 行為不變。

Application 可切回 `m10` 並保留 additive M11 tables；舊程式會忽略它們。`alembic downgrade 0004_m9_6` 會刪除 User、Session、Membership 與 Audit 全部資料，必須先備份並另行取得破壞性操作核准。

2026-08-10 使用者決定暫不採用登入及 Customer／System 選擇。公司 `.77` 已還原登入前 environment、重新安裝 M10 release `6e8ee6e` 並切回 `current`；Web／Worker active、health 正常、未登入 Jobs API 200、登入頁不存在。EDB 保留 `0005_m11` additive tables，不執行破壞性 downgrade；M10 不會讀寫這四張表。
