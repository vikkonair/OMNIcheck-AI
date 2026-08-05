# M9 Web UI 與案件管理

## 已完成範圍

M9 第一階段在既有 M1–M8.1 Pipeline 外新增 FastAPI 服務，不改寫 Parser、Scope、Rule Engine、QA 或 V4 Renderer。

目前提供：

- 建立健檢案件並驗證 `JobConfig`
- 將上傳證據保存在案件專屬 input 目錄
- 拒絕路徑穿越、重複檔名與案件執行後的追加上傳
- 透過背景工作呼叫既有 `run_generate`
- 查詢案件狀態、錯誤及輸出清單
- 下載案件輸出檔案
- 圖形化客戶、產品、期間與報告格式表單
- 動態新增 Primary、Standby、DR、Witness 節點
- 依節點角色選擇 EFM、PEM、XDB、pgBackRest、Barman
- 選取整包資料夾並保留節點與分類相對路徑
- 一鍵建案、分批上傳、執行 Pipeline 與輪詢案件狀態
- 案件列表、執行結果及輸出下載

## 儲存結構

```text
data/jobs/<job-id>/
├── job.json
├── job.yaml
├── input/
└── output/
```

原始證據在同一案件中不得覆寫。每次正式重新執行應建立新案件，以保留可追溯性。

## API

- `GET /api/health`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/files`
- `POST /api/jobs/{job_id}/run`
- `GET /api/jobs/{job_id}/outputs`
- `GET /api/jobs/{job_id}/outputs/{filename}`

## 執行模式與已知限制

未設定 `OMNICHECK_DATABASE_URL` 時，metadata 使用檔案系統，背景工作在 Web 程序內執行，適合本機開發。M9.3 已新增 EDB／PostgreSQL metadata、資料庫工作佇列與獨立 Worker，不需要 Redis；公司環境仍待實機部署驗證。

瀏覽器基於安全限制不能直接讀取任意本機路徑，因此使用者需透過資料夾選擇器授權上傳。辨識結果確認畫面、身分驗證、取消操作與完整權限控管仍屬後續工作。

Barman parser 已具備 provider 架構與 Golden 測試；實際客戶輸出範本不是 M9 的阻擋條件，但取得後仍須新增對應 fixture，驗證不同版本與 wrapper 格式。
