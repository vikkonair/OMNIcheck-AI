# M10 自動探索與拓撲確認

日期：2026-08-10  
狀態：正式完成；本機、使用者驗收、實際客戶資料與公司 `.77/.81` 部署驗證通過

## 目的

讓使用者不必先知道完整節點架構。系統先從未知資料包提出節點、Primary／Standby／DR／Witness 與服務候選，使用者核對後才建立正式案件並執行既有 Pipeline。

## 確定性訊號

- `HealthChekOS-LOG-<hostname>-<date>` 與 `<date>_<hostname>_check` 路徑辨識 hostname。
- EFM `bind.address` 的 primary／standby／witness 標記與 `is.witness=true`。
- hostname 的 DR 標記。
- `primary_conninfo` 只能提出 Standby／DR 待確認訊號，不單獨決定 Primary。
- PEM Server、EFM、pgBackRest、Barman、XDB 使用明確服務訊號；PEM Agent 不等於 PEM Server。
- `PEM_check` 內的 Database Output 屬於 PEM Server 的後端 PostgreSQL；若案件中只有一個 PEM 節點，Discovery 必須建議該 Witness，而不是業務 Primary。後端 Scope 會再次保護此服務邊界，舊的錯誤人工映射也不能把它帶入業務資料庫檢查。
- 無法唯一判斷時輸出 `Unknown`／conflict，正式執行前必須人工修正。

## 人工確認與稽核

Web 選取資料夾後自動呼叫 `/api/topology/discover`。Discovery 只讀取文字檔前 512 KiB；圖片只計入未映射數量，不送入解析器。候選節點、建議角色、信心、理由及衝突顯示在頁面上。

使用者必須勾選「我已核對並確認上述節點架構」才能建立案件。原始建議與確認狀態寫入 `job.yaml.topology_confirmation`；正式 `topology.json` 使用 `operator_confirmed_discovery` 作為 Primary confirmation／role source。AI 不參與角色決策。

## 與既有 Pipeline 的關係

M10 位於 Job creation 與 M1 Inventory 之前。確認後仍使用原有 `JobConfig`、Inventory、Scope、Parser、Rules、QA 與 V4 Renderer：

```text
資料夾選取
→ Deterministic Discovery
→ Operator Confirmation
→ 既有 JobConfig
→ M1～M9.6 Pipeline
```

既有規則不變：邏輯資料庫 Primary-only；Primary／Standby／DR 設定檔比較；未標節點的 PEM 圖片預設 Primary；Witness 可承載 PEM、EFM、XDB 與 Barman。

Section Workflow 寫入 EDB 前會檢查 `section_id:node:check_id` 是否唯一。若同一節點被錯誤納入兩份 Database Output，系統會先回報明確的 duplicate section workflow key，而不是延後到 EDB unique constraint 才失敗；不得以合併兩份不同資料庫輸出來規避錯誤。

## Rollback

沒有 migration、套件或環境變數變更。Application 可切回 `m9.6`；既有 M9.6 案件與資料庫 schema 不需 downgrade。M10 建立的 `job.yaml` 多出 optional `topology_confirmation`，舊版本不應重新執行該案件，若要回復應建立新的 M9.6 設定。

## 正式部署證據

公司 App VM 已部署 release `6e8ee6e`，VM 78 tests 與 V4 manifest 通過。台灣行動支付實際資料經 Web、EDB Queue 與獨立 Worker 建立 Job `12c90aa3da354f1c83dbc42e6d57e118`，正確提出 5 個節點、唯一 Primary，完成 13 個 outputs，QA／V4 QA 通過且來源 manifest 不變。Web／Worker 重啟後 Job 與 outputs 仍可由 EDB 讀回；revision 維持 `0004_m9_6`。
