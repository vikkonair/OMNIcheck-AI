# M9.2 圖形化操作流程驗證

驗證日期：2026-08-04

## 驗證目標

- Web 建案沿用既有 `JobConfig` 驗證
- 原始證據無法透過路徑穿越寫出案件目錄
- 同一批上傳先完成整批檢查，驗證失敗不留下部分檔案
- Web 工作直接執行既有 M1–M8.1 Pipeline
- 成功案件可列出並下載結構化輸出
- 使用者可透過表單配置案件與節點，不需手寫 JSON
- 資料夾選擇器保留 Parser 所需的相對目錄結構
- Web 可在同一操作流程完成建案、上傳、執行與下載
- 既有測試與 V4 vendor bundle 不回歸

## 測試資料

端對端測試使用 Repository 內去識別的 `tests/fixtures/golden/jiuxing_v4`。客戶原始資料不會被修改或提交。

## 驗證指令

```bash
.venv/bin/pytest
.venv/bin/python ../omni-healthcheck-codex-complete/scripts/verify_bundle.py
```

## 驗證結果

- 自動化測試：49 項通過
- V4 bundle：29 個必要檔案與雜湊全部通過
- Web health／config-options API：通過
- 去識別 Golden V4 Web 端到端 Pipeline：通過
- 台灣行動支付實際資料 Web 端到端 Pipeline：通過
- 實際資料：13 個有效檔案上傳、2 個 Scope 排除、0 pending
- M6 QA：`delivery_allowed = true`
- DOCX／PDF：皆產生成功
- 客戶來源資料：執行前後 14 個檔案 SHA-256 清單一致

自動瀏覽器控制受到本機 URL 安全政策阻擋，因此本次未宣稱完成自動化視覺驗證。服務已啟動，可由使用者直接重新整理 `http://127.0.0.1:8000` 進行目視驗收。
