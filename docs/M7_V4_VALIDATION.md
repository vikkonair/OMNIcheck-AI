# M7 V4 整合驗證

驗證日期：2026-07-29

## Bundle baseline

- Vendor Renderer SHA-256：
  `f4f3728c4c11d4b1fcaa563d800a5d91fa5878b1663275b085bda568e70c9895`
- Smoke DOCX 產生成功
- Smoke PDF：7 頁
- 核准 Reference PDF：7 頁
- 兩者皆為 A4
- Smoke 七頁已轉成 PNG 並完成視覺檢查

## Pipeline regression

- 自動測試：30 項通過
- M1～M6 輸出契約保留
- Legacy M7 tag：`m7-legacy-renderer`
- V4 Renderer hash pin 測試通過
- Pending Scope 阻擋正式報告測試通過

## 台灣行動支付實際資料

- 原始資料執行前後 SHA-256 清單一致
- Scope：11 allowed、3 excluded、0 pending
- 五張 PEM／monitoring 圖片全部映射至 `twmpedbp1` Primary
- M6 QA：通過
- V4 QA：通過
- V4 DOCX：產生成功
- V4 PDF：38 頁、A4
- DOCX 標準 Render Workflow：38 頁
- DOCX／PDF 頁數一致
- 38 張頁面 PNG 已逐頁檢查
- 未發現中文字缺字、表格裁切、圖片溢位或頁首頁尾遺失

## 字型驗證

第一次標準轉換因本機缺少 Microsoft JhengHei，發生中文字缺字及
34／40 頁漂移。macOS Fontconfig 已明確將 Microsoft JhengHei
映射到 Arial Unicode MS。修正後 CLI PDF 與標準 DOCX Render 均為
38 頁。
