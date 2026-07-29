# M8 驗證紀錄

驗證日期：2026-07-29

## Golden Dataset

- `jiuxing_v4`：V4 結構與 Primary-only 報告契約
- `globalwafers_pem`：PEM 圖片 Primary 映射與正式 Output
- `multi_node_scope`：Primary／Standby／DR／Witness Scope 與設定比較
- 所有資料均為虛構及去識別內容
- `tests/fixtures/golden/manifest.json` 已記錄契約版本

## 自動測試

- M8 新增回歸測試：7 項通過
- 完整測試：38 項通過
- V4 Renderer manifest：全部通過
- `git diff --check`：通過
- Golden PEM DOCX／PDF：產生成功
- Golden PEM PDF：9 頁 A4
- Golden PEM 9 頁已完成視覺巡檢
- Golden PEM 圖片為純虛構 CPU 趨勢，不含客戶資訊

## 實際客戶資料

- 唯讀端對端執行：成功
- Scope：11 allowed、3 excluded、0 pending
- 執行前後 SHA-256：完全一致
- M6 QA：通過
- V4 QA：通過
- DOCX／PDF：產生成功
- PDF：37 頁 A4
- 37 頁已完成視覺巡檢
- 繁體中文與關鍵文字擷取檢查：通過
- 未發現新增的文字重疊、表格裁切、空白頁或缺字

## 結論

M8 所有適用驗證門檻均已通過，可建立 commit。依既定流程，分支合併
至 `main` 後才建立正式 `m8` tag。
