# M10.3.1 驗證紀錄

日期：2026-08-11  
狀態：本機、實際資料與公司候選部署驗證完成，待使用者驗收

## 自動化驗證

- Section／CLI／Artifact／Persistence／Golden targeted tests：21 passed。
- 完整測試：85 passed。
- V4 vendor manifest：5/5 passed。
- `git diff --check`：passed。

## 台灣行動支付實際資料唯讀驗證

來源：`20260616 (1)`，共 14 個檔案；輸出位於 `/private/tmp/m10-3-section-output`，未寫入來源資料夾。

- 來源整體 manifest digest 前後皆為 `1d316dcde06aff7ef04ef5edfb586283f553f7b1b6003a1794fc5bed3c5ba4ea`。
- Scope：3 excluded、0 pending。
- Section workflow：19 items，全部為 `generated`。
- `selected_source`：19 項全部為 `deterministic_template`。
- `ai_enabled=false`、`renderer_uses_ai=false`。
- QA：8/8 passed；V4 QA：passed。
- DOCX 約 1.7 MiB；PDF 約 2.0 MiB。

## 已知限制與下一步

- 尚未呼叫 Ollama；本階段只建立安全契約與 fail-closed transition。
- 尚未建立 EDB Section tables 或 Web API，需先處理公司 EDB 的 M11 additive revision 與正式 migration history reconciliation。
- M14 Ollama Adapter 必須輸出結構化草稿、經 schema 驗證、遮蔽機敏資料並保留 timeout／fallback；不得直接寫入 V4 Renderer。

## 公司 App VM 候選驗證

- Release／branch commit：`e56f043`。
- Web、Worker：active；health 為 database metadata／external worker；首頁與 Job API 皆 HTTP 200。
- 公司 VM 完整測試：85 passed。
- 既有 ENGDB 三檔以唯讀輸入、隔離輸出完成 Pipeline：9 個 `generated` items，全部使用 deterministic template；QA 8/8、V4 QA、DOCX 52 KiB、PDF 214 KiB。
- ENGDB 來源 manifest 前後皆為 `4d6415f72cc600e27eb462ee9f90b348dbb836b207ce2fdd4d8d3f25f24c82eb`。
- 切換前 VM 曾載入另一個 `0.13.2.dev2` 開發套件並出現 auth API；候選部署已明確切至 `e56f043`。多人共用 App VM 前需建立 deploy lock／release owner，避免互相覆寫 editable venv 與 current symlink。
