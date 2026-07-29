# M8 Golden Dataset 與回歸測試

## 目標

M8 將不可提交 Git 的客戶原始資料，轉換為完全虛構、去識別且可長期
保留於 Repository 的測試契約。Golden Dataset 不複製客戶內容，只保留
Pipeline 必須持續遵守的資料形狀、節點角色與輸出規則。

## Golden Dataset

### `jiuxing_v4`

- 驗證核准 V4 的三個主要章節
- 驗證 EPAS 顯示為 `EDB Postgres Advanced Server`
- 驗證資料庫 Output 只來自 Primary
- 驗證架構總覽不顯示元件欄
- 驗證資料庫清單及同步狀態的精簡欄位

### `globalwafers_pem`

- 驗證未標示節點的 PEM／monitoring 圖片依政策映射至 Primary
- 驗證圖片成為正式 V4 Output
- 驗證圖片標題、節點與 caption 契約
- 圖片為專為自動測試產生的虛構 CPU 趨勢，不含客戶資料

### `multi_node_scope`

- 驗證 Primary、Standby、DR、Witness 四種角色
- 驗證 Standby／DR 邏輯資料庫 Output 被排除
- 驗證 Primary／Standby／DR 的 `postgresql.auto.conf` 與
  `pg_hba.conf` 仍進入跨節點比較
- 驗證非 Primary 的特殊值不會進入客戶報告

## 版本契約

`tests/fixtures/golden/manifest.json` 記錄：

- Golden fixture 版本
- Canonical schema 版本
- Pipeline 版本
- Ruleset 版本
- Report template 版本
- 每組 fixture 的責任範圍

版本發生有意變更時，必須同步更新 manifest、expected contract 與測試；
不得直接重新產生 expected output 來掩蓋回歸。

## 資料安全

- Golden 客戶、主機、資料庫、帳號、IP 與數值均為虛構
- Golden Dataset 不含客戶檔案、客戶雜湊或可逆識別資訊
- 真實客戶資料只用於 milestone 完成前的唯讀驗證
- 真實資料及其產出不得加入 Git

## 驗證指令

```bash
.venv/bin/pytest -q tests/test_golden_regression.py
.venv/bin/pytest -q
```

正式完成 M8 前，仍需以指定客戶資料執行端對端 Pipeline，並確認執行
前後檔案數量、大小及 SHA-256 完全一致。
