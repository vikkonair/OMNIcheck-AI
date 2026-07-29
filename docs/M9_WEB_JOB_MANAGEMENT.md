# M9 Web UI 與案件管理

## 第一階段範圍

M9 第一階段在既有 M1–M8.1 Pipeline 外新增 FastAPI 服務，不改寫 Parser、Scope、Rule Engine、QA 或 V4 Renderer。

目前提供：

- 建立健檢案件並驗證 `JobConfig`
- 將上傳證據保存在案件專屬 input 目錄
- 拒絕路徑穿越、重複檔名與案件執行後的追加上傳
- 透過背景工作呼叫既有 `run_generate`
- 查詢案件狀態、錯誤及輸出清單
- 下載案件輸出檔案
- 本機案件列表與建立案件頁面

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

## 已知限制與後續工作

第一階段的 metadata 使用檔案系統，背景工作在 Web 程序內執行；程序中斷時不具備可靠重試或工作接手能力。後續 M9 會加入 PostgreSQL metadata、Redis／Worker、完整 UI 操作、身分驗證、取消／重試與部署設定。

Barman parser 已具備 provider 架構與 Golden 測試；實際客戶輸出範本不是 M9 的阻擋條件，但取得後仍須新增對應 fixture，驗證不同版本與 wrapper 格式。
