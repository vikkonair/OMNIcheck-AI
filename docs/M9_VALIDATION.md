# M9 第一階段驗證

## 驗證目標

- Web 建案沿用既有 `JobConfig` 驗證
- 原始證據無法透過路徑穿越寫出案件目錄
- 同一批上傳先完成整批檢查，驗證失敗不留下部分檔案
- Web 工作直接執行既有 M1–M8.1 Pipeline
- 成功案件可列出並下載結構化輸出
- 既有測試與 V4 vendor bundle 不回歸

## 測試資料

端對端測試使用 Repository 內去識別的 `tests/fixtures/golden/jiuxing_v4`。客戶原始資料不會被修改或提交。

## 驗證指令

```bash
.venv/bin/pytest
.venv/bin/python vendor/omni-healthcheck-codex-template/scripts/verify_bundle.py
```

本機介面另以瀏覽器實際確認首頁載入、案件建立與案件列表更新。
