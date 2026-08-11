# M10.2 同仁 UI 整合候選版

## 目的

將同仁交付的 `0.13.2.dev2` 整合式健檢介面接到目前 M10.3.1 後端，保留既有 Inventory、Topology、Scope、Parser、Rules、Coverage／QA、Canonical JSON、Section Workflow 與 V4 Renderer，不以同仁分支覆蓋後端。

## 來源與完整性

- 交付 Bundle：`OMNIcheck_AI_0.13.2dev2_GPDB_Segment_Bundle`
- Source ZIP：`OMNIcheck-AI_0.13.2.dev2_Source.zip`
- Bundle 內 7 個 SHA-256 項目全部通過。
- Source ZIP 與公司 App VM `/data/omnicheck/app/releases/omnicheck-ai-0.13.2dev2` 排除 cache 後均為 185 個檔案，逐檔 SHA-256 差異為 0。
- 同仁 Source 的 107 個 collected tests 全部通過。

## 第一階段整合邊界

保留並接入：

- 同仁的品牌 Header、視覺樣式、步驟導覽與整合式健檢作業頁。
- 既有 `/api/config-options`、`/api/topology/discover`、Job、Upload、Run、Polling 與 Output API。
- 目前 M10.3.1 後端與 `section-workflow.json`。

暫不接入：

- Login、RBAC、Customer／System authorization 與 Audit API。
- Knowledge UI、CVE／Release sync、Knowledge Worker。
- GPDB planning preview 與 `0005`～`0007` migration。
- 同仁分支的 `web.py`、Pipeline、Parser、Rules、Topology 或 Renderer。

## 路由與 rollback

- `/`：新版整合式健檢 UI。
- `/integrated`：新版整合式健檢 UI 的固定路由。
- `/classic`：原 M10.3.1 傳統 UI，作為畫面層立即 fallback。
- API 契約與資料庫 schema 不變，無 migration。
- Application rollback 可切回 M10.3.1 release `e56f043`；不需 database downgrade。

## Per-release runtime 與部署鎖

- Web／Worker 的 systemd `ExecStart` 必須使用 `/data/omnicheck/app/current/.venv/bin/...`，不可再指向 shared `/data/omnicheck/venv`。
- 每個 release 自帶 `.venv` 並在切換前執行完整 tests。
- 正式切換使用 `/data/omnicheck/app/deploy.lock` 的 non-blocking `flock`；鎖已被其他部署持有時直接停止。
- release 內保存 `RELEASE_DEPLOYMENT.json`，至少包含 owner、commit、branch、previous release、database revision、deployed_at 與 rollback target。
- 本次沒有 migration；rollback 必須先確認舊 release 也有獨立 `.venv`，才允許單純切換 `current`。

## 安全修正

Topology discovery 回傳 `can_confirm=false` 時，確認 checkbox 必須停用；若沒有提出任何節點，不得清空使用者已填寫的人工節點。這能避免 0 Primary／未解析 evidence 被誤認為已確認。

若 discovery 沒有唯一 Primary，Database Output 的 `suggested_node` 為空值。UI 必須顯示「請選擇來源節點」，不得讓瀏覽器把排序第一台（例如 DR）顯示成預設來源。使用者將節點角色修正為唯一 Primary，且所有 Database Output 都完成來源映射後，系統才重新開放確認 checkbox；未選來源時建立案件必須 fail closed。

## 驗證

- 專案 Python 3.12 syntax check：通過。
- 完整 pytest：88 passed（包含無 Primary 時不得預選 DR 的 regression test）。
- Browser DOM／視覺檢查：品牌、路由、產品選項與操作元件正常；無水平 overflow。
- `/knowledge` link：0。
- GPDB UI：未出現。
- 無節點探索：保留人工 Primary，確認 checkbox 維持 disabled。
- 既有 Golden／V4 tests：通過，Pipeline 與 Renderer 未變更。

## 公司候選部署

- 公司 VM 已切換 release `0a6dccd`，per-release venv、systemd、deploy lock／owner、health、UI markers 與 `/classic` 均通過；聯詠資料測試揭露的空來源誤顯示問題已修正，rollback release 為 `a0582a0`。
- 台灣行動支付既有 immutable 13 檔資料已在隔離輸出目錄完成候選 Pipeline：14 outputs、QA/V4 QA delivery allowed、Section Workflow、DOCX/PDF 皆通過，來源整包 SHA-256 執行前後相同。
- 使用者核准後才合併 `main` 或建立正式 tag。
- Knowledge、CVE、GPDB 與登入功能後續各自建立 milestone／feature flag，不在本候選版偷渡啟用。

## 聯詠實際資料回歸

`2026聯詠健檢資料 2` 三檔以唯讀方式驗證。OS process 證據中的 `walsender streaming` 與 `walreceiver streaming` 可提出 `OADB15N → Primary`、`OADB15-DR → DR`，Database Output 自動建議來源 `OADB15N`。聯詠標題相容、zero-row 語意與 coverage check ID 修正後，normalized checks 由 29 增至 49，coverage 由 50% 升至 92.5%；剩餘缺項僅為來源未提供的兩台 Kernel version 與 Primary `pg_hba.conf`。QA／V4 QA、29 頁 PDF 逐頁檢查與來源 SHA-256 不變均通過。
