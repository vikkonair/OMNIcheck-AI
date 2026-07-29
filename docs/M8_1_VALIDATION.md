# M8.1 驗證紀錄

驗證日期：2026-07-29

## 自動驗證

- XDB 只允許配置於 Witness
- PEM 舊有角色限制維持相容
- 服務名稱正規化與自訂服務保留
- Backup provider 必須對應已配置節點及服務
- Barman Parser ID：`backup.barman.v1`
- Barman 正常及失敗狀態規則
- Barman on Witness 不進入 Primary-only 邏輯資料庫 Scope
- Golden PEM／XDB／Barman 報告契約
- 完整測試：45 項通過

## Golden 報告

- XDB 與 Barman Golden Job：0 pending
- M6 QA：通過
- V4 QA：通過
- DOCX／PDF：產生成功
- PDF：9 頁 A4
- 9 頁視覺巡檢：通過
- XDB 與 PEM Server 同時顯示於服務摘要
- Barman 顯示於 Witness 的備份服務狀態
- 未發現裁切、重疊、空白頁或缺字

## 實際客戶資料

- 唯讀端對端執行：成功
- Scope：11 allowed、3 excluded、0 pending
- 執行前後 SHA-256：完全一致
- M6 QA：通過
- V4 QA：通過
- pgBackRest 未指定 provider 時只採 Primary
- pgBackRest 備份 Output：只出現已配置的 Primary
- DOCX／PDF：產生成功
- PDF：37 頁 A4
- pgBackRest 所在頁面視覺檢查：通過
- 既有報告頁數未發生漂移

## 結論

M8.1 所有目前適用的驗證門檻均已通過，可建立 commit。Barman 已完成
Parser 架構與 Golden 驗證；收到實際客戶輸出後仍需增加格式 fixture，
才能宣告支援該客戶的 Barman wrapper 格式。
