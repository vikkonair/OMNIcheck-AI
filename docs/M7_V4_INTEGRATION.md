# M7 V4 報告引擎整合

## 架構

M1～M6 仍是唯一的資料盤點、Scope、解析、判斷與交付安全來源。M7
新增 Adapter，將既有 `ReportModel` 轉換為核准的 Jiuxing V4 Report
JSON，再交給固定 SHA-256 的 V4 Renderer。

```text
M1～M6 JSON
  -> ReportModel
  -> V4 Adapter
  -> V4 Report QA
  -> approved build_report.py
  -> DOCX
  -> LibreOffice PDF
```

## OMNIcheck 專案規則

- Database 邏輯證據只使用目前 Primary
- `postgresql.conf`、`postgresql.auto.conf`、`pg_hba.conf` 保留
  Primary／Standby／DR 比較
- 報告只顯示 Primary 設定檔內容，其他節點差異寫入同項觀察
- 未明確標示節點的 PEM／monitoring 圖片自動歸屬 Primary
- 正式 V4 DOCX／PDF 產出前，Scope Ledger 的 Pending 必須為零
- M6 QA 與 V4 QA 分開；V4 QA 失敗時仍保留診斷 JSON

## Rollback

- Legacy M7 保存點：Git tag `m7-legacy-renderer`
- Legacy Renderer：`src/omni_healthcheck/docx_renderer.py`
- 正式 V4 Renderer：`vendor/omni-v4-renderer/scripts/build_report.py`
- Vendor 檔案雜湊：`vendor/omni-v4-renderer/MANIFEST.sha256`

Vendor Renderer 的預設 V4 token 不得任意修改。經使用者明確核准的
參數化擴充，必須維持預設輸出相容、重新執行 Baseline regression，
並同步更新 SHA-256。

目前核准的擴充參數：

- `cover_company_name`：只覆蓋封面藍色框的公司名稱
- `evidence.font_size`：只調整純文字 Technical Output 字級
- `show_components`：控制架構總覽是否顯示元件欄

## 字型

DOCX 遵循 V4 契約，以 Microsoft JhengHei 作為 CJK implementation
font。macOS PDF 轉換透過 `config/fonts.macos.conf` 將缺少的字型明確
映射至 Arial Unicode MS。Linux／Container 部署需安裝相容 CJK 字型並
提供等效 Fontconfig alias，避免分頁與中文字形漂移。
