# M10.2 前端整合架構與交接資料

最後更新：2026-08-10  
狀態：規劃核准，待取得前端資料後實作

## 架構原則

組員既有 Frontend 與 OMNIcheck AI Backend 維持獨立 Repository，透過版本化 REST API 整合：

```text
Frontend App
    -> OMNIcheck REST/OpenAPI
    -> EDB Queue
    -> Worker
    -> M1～M10.1 Pipeline
    -> JSON／DOCX／PDF
```

目前內建 Web UI 保留為開發、診斷與 rollback 介面。M10.2 不修改確定性規則、Canonical JSON 或 V4 Renderer。

## 前端團隊需提供

1. Repository、基準 commit、framework、Node/package manager 版本與啟動命令。
2. VM、URL、port、同／跨網域、Nginx／proxy、HTTP／HTTPS 與各環境 API base URL。
3. 現有 route、page、component、API client、畫面截圖或 Figma。
4. 建案、資料夾上傳、拓撲確認、Database Output 來源確認、進度、結果與下載流程。
5. 單檔／整包大小、檔案數、ZIP、續傳、分批及失敗重試需求。
6. Job polling／SSE／WebSocket 需求；M10.2 預設先採 polling。
7. 統一錯誤顯示、分頁、搜尋、排序及 timeout 需求。
8. 是否已有登入／token；M10.2 預設不恢復完整 RBAC，但保留未來 authentication header。
9. M10.3 是否需要 Section 編輯、重新產生 AI 草稿、人工核准及版本比較。

## 開工 Gate

- Backend 必須以正式 `m10.1` tag 為基準，完整測試與 V4 manifest 通過。
- Frontend 必須提供可重現的啟動方式與固定 commit。
- 先產出現有 API／前端需求差距、OpenAPI 草案、修改／不修改檔案與回歸風險，核准後才實作。
- 前後端使用獨立 feature branch，禁止直接推送 `main`。

