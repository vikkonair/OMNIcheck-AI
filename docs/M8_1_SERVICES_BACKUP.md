# M8.1 Witness 元件與備份工具架構

## 目標

M8.1 將節點角色、節點上的服務元件及備份工具分開建模，避免把 XDB
誤認成節點或主要資料庫產品，也避免將備份健檢寫死為 pgBackRest。

## 服務 Registry

`src/omni_healthcheck/services.py` 是集中式 Registry。目前內建：

| 名稱 | 類別 | 角色限制 |
|---|---|---|
| PEM | monitoring | Witness |
| EFM | failover | 無 |
| XDB | supporting_component | Witness |
| pgBackRest | backup | 無 |
| Barman | backup | 無 |

已登錄名稱會進行大小寫與別名正規化。尚未登錄的自訂服務仍會保留，
不會被靜默刪除；在加入 Parser 與規則前，其專屬內容應維持待確認。

## XDB

XDB 是 Witness 上的元件，不是節點角色，也不是目標資料庫產品：

```yaml
nodes:
  - hostname: witness-01
    role: Witness
    services:
      - PEM
      - EFM
      - XDB
```

XDB 狀態由 OS 健檢輸出中的 `XDB` 區段解析，並加入服務狀態彙整。
XDB 不會進入 Primary-only 邏輯資料庫判斷。

## 備份工具

Job 可明確指定備份 provider 與執行節點：

```yaml
nodes:
  - hostname: backup-witness
    role: Witness
    services:
      - Barman

backup:
  provider: barman
  node: backup-witness
```

目前 provider：

- `pgbackrest`
- `barman`

備份 Output 使用共通 `backup_configuration` check，並保留 provider、
節點、原始可見 Output、判斷與證據追溯。

pgBackRest 會以 stanza 為單位解析 `status`。若唯一的主要 stanza（排除名稱明確
標示 DR／Standby／Replica 的 stanza）回報 `status: ok`，報告會將主要備份判為
正常，並在觀察與建議中保留 stanza 名稱、狀態、持續監控及定期還原驗證要求。
同一份 Output 內其他 stanza 的異常會另外揭露，不會污染主要備份結論；若無法
唯一辨識主要 stanza，則保守標示待確認，不由 AI 猜測。

### 報告位置

- Primary 上的備份工具：列於資料庫運行與效能狀態
- Witness 等非 Primary 節點上的備份工具：列於服務與備份狀態
- 非 Primary 備份 Output 不會被誤當成邏輯資料庫 Output

## Barman Parser

`backup.barman.v1` 可辨識：

- `barman check`
- `barman status`
- `barman list-backup`
- `backup maximum age`
- `retention policy`
- 健檢檔中的 `Barman` 區段

輸出含 `FAILED`、`error`、`fatal` 等明確錯誤時，規則引擎標示注意；
否則標示正常並建議持續追蹤成功率與還原演練。

## 尚需實際範例

目前 Barman Parser 使用去識別 Golden Output 驗證。要完成客戶格式的
精準欄位解析，仍需至少一組去識別的實際輸出：

```text
barman check <server>
barman status <server>
barman list-backup <server>
```

若實際蒐集方式另有 wrapper script，也需要該 script 的輸出段落標題。
