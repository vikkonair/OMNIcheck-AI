# M9.4 Validation Report

日期：2026-08-05  
分支：`feature/m9-4-application-data-foundation`  
狀態：本機實作驗證通過；公司 `.81` EDB deployment 尚未執行

## 1. 自動化測試

- M9.4 application data + M9.3 database queue targeted tests：13 passed。
- 完整 regression：65 passed。
- `git diff --check`：passed。
- PostgreSQL Alembic offline upgrade：`0001_m9_3 → 0002_m9_4` 成功生成。
- PostgreSQL Alembic offline downgrade：`0002_m9_4 → 0001_m9_3` 成功生成。

驗證涵蓋：

- 六張 M9.4 table 與 `jobs.customer_id/system_id`。
- Customer／System／Node／Topology／Evidence／Artifact CRUD。
- 跨 tenant Node、Topology 與 Job 重新關聯拒絕。
- 相對 storage key、SHA-256、file size 與 uniqueness validation。
- M9.3 legacy Job 在 tenant scope 為 `NULL` 時仍可建立。

## 2. 實際客戶資料唯讀驗證

Dataset：台灣行動支付 2026 上半年  
來源：Repository 外部唯讀資料夾；未複製或提交 Git

驗證方法：

1. 執行前建立所有 14 個來源檔案的 relative path、size、SHA-256 manifest。
2. 使用既有 Inventory／Scope 決定 evidence domain 與節點映射。
3. 在系統 temporary directory 建立隔離 SQLite，不連線公司 EDB。
4. 建立 Customer、System、5 個 Node、4 條 Topology relation 與 M9.3 Job。
5. 將 14 個來源檔案只以 metadata 方式登錄 Evidence；不寫入來源目錄。
6. 再次計算來源 manifest 並比較。

結果：

| 項目 | 結果 |
|---|---:|
| Source files | 14 |
| Source manifest before／after | identical |
| Customer／System | 1／1 |
| Nodes | 5 |
| Topology relations | 4 |
| Evidence metadata | 14 |
| Scope allowed／excluded／pending | 11／3／0 |

5 個節點為 `twmpedbp1` Primary、`twmpedbp2` Standby、`twmpedbdr1` DR、`pemp1` Witness／PEM、`twmpedbwitness` Witness／EFM。3 筆 excluded 包含 Standby database、PEM backend database 與 `.DS_Store`；Web M9.3 沒有上傳 `.DS_Store`，因此其有效 13 inputs 結果仍是 11 allowed／2 excluded／0 pending。

## 3. 回歸判斷

- M1～M8.1 Pipeline：未修改資料契約與處理順序。
- M7 V4 Renderer：未修改。
- M9.3 Queue／Worker：既有 nullable scope 路徑與 targeted regression 均通過。
- Canonical JSON：仍是不可變 Pipeline／Renderer 契約；M9.4 沒有改 schema。
- AI：未加入，也不影響離線確定性流程。

## 4. 尚未驗證／不得誤標完成

- 尚未在公司 EPAS 17.10 `.81` 執行 `0002_m9_4` migration。
- 尚未執行 `.81` backup／restore／downgrade drill。
- Web 尚未自動建立 Customer／System／Node。
- Pipeline result persistence 與完整 Artifact lifecycle 分屬 M9.5／M9.6。

## 5. 結論

M9.4 本機功能與實際客戶資料唯讀驗證通過，可進入文件／Golden 最終 gate；通過後再由使用者決定是否部署公司測試 EDB。尚未合併 `main` 或建立 `m9.4` tag，因此目前正式 rollback 基準仍是 `m9.3`。
