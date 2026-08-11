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

## 安全修正

Topology discovery 回傳 `can_confirm=false` 時，確認 checkbox 必須停用；若沒有提出任何節點，不得清空使用者已填寫的人工節點。這能避免 0 Primary／未解析 evidence 被誤認為已確認。

## 驗證

- 專案 Python 3.12 syntax check：通過。
- 完整 pytest：85 passed。
- Browser DOM／視覺檢查：品牌、路由、產品選項與操作元件正常；無水平 overflow。
- `/knowledge` link：0。
- GPDB UI：未出現。
- 無節點探索：保留人工 Primary，確認 checkbox 維持 disabled。
- 既有 Golden／V4 tests：通過，Pipeline 與 Renderer 未變更。

## 尚待完成

- 公司 VM 已建立隔離 release `59eff13`，以 `PYTHONPATH` 執行 85 tests 全數通過；loopback 候選 Web 的 health 為 `metadata=database／worker=external`，UI markers 與 `/classic` 均通過。
- 台灣行動支付既有 immutable 13 檔資料已在隔離輸出目錄完成候選 Pipeline：14 outputs、QA/V4 QA delivery allowed、Section Workflow、DOCX/PDF 皆通過，來源整包 SHA-256 執行前後相同。
- 正式 `current` 與 shared venv 仍維持 `e56f043`。不得直接重裝 shared editable package；正式切換前需完成 per-release venv／systemd release owner 設計，避免 Web、Worker、Knowledge process 互相覆蓋。
- 使用者核准後才合併 `main` 或建立正式 tag。
- Knowledge、CVE、GPDB 與登入功能後續各自建立 milestone／feature flag，不在本候選版偷渡啟用。
