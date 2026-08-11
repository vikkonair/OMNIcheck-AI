# M14.1 Ollama Gateway Adapter

## 目的

以公司內網 Ollama `gpt-oss:20b` 產生單一 Section 的繁體中文觀察／建議草稿。AI 是選配且不受信任；Pipeline、規則狀態、證據、Topology、Scope、Canonical JSON 與 Renderer contract 不變。

## 公司端點

- Endpoint：`http://192.168.68.39:11434/v1/chat/completions`
- Model：`gpt-oss:20b`
- Protocol：OpenAI-compatible chat completions
- Authentication：目前內網不需 Token
- App VM `192.168.118.77` 已完成最小連線測試

正式環境目前為 HTTP。端點只應開放核准的 App VM；若跨不受信任網段，M15 必須加入 TLS／reverse proxy／API authentication。

## 資料最小化與遮蔽

Gateway 不傳送：

- 客戶名稱、System 名稱與原始檔名
- 原始 evidence、圖片、DOCX／PDF
- Topology、Primary 選擇與完整節點清冊
- Prompt 中不需要的 Canonical JSON

單次只傳送 Section ID、check ID、deterministic status、deterministic observation／recommendation。送出前遮蔽目前 node、IPv4、email、password／secret／token／API key 與含帳密的 PostgreSQL URI。

## Fail-safe 流程

1. 預設 `OMNICHECK_AI_ENABLED=false`。
2. 工程師呼叫 generate API 並提交 `expected_revision`。
3. Gateway 建立 EDB audit record。
4. Ollama 必須回傳只有 `observation`、`recommendation` 的 JSON object。
5. Observation 必須包含換行後的 `結論：`；欄位長度與 extra fields 皆驗證。
6. 成功只保存為 `ai_drafted`，selected source 仍是 deterministic。
7. timeout、網路、HTTP、JSON 或 schema 錯誤回 fallback；不修改 Section。
8. AI 完成後若 Section revision 已改變，草稿標記 `discarded_stale`，不得覆蓋。
9. 只有 engineer review＋approval 後，Renderer 才使用核准文字。

## API

- `POST /api/jobs/{job_id}/sections/{item_id}/generate-ai-draft`
- `GET /api/jobs/{job_id}/ai-audit`

Generate body：

```json
{
  "expected_revision": 1,
  "actor": "engineer-name"
}
```

## EDB Audit

Migration `0009_m14_ai_gateway` 新增 `omnicheck.ai_gateway_requests`，保存：provider、model、prompt version、requested by、status、attempts、duration、已遮蔽 prompt／response、SHA-256、token usage 與錯誤摘要。模型的 reasoning 欄位不保存、不顯示、不採用。

## 設定

```bash
OMNICHECK_AI_ENABLED=false
OMNICHECK_AI_ENDPOINT=http://192.168.68.39:11434/v1/chat/completions
OMNICHECK_AI_MODEL=gpt-oss:20b
OMNICHECK_AI_TIMEOUT_SECONDS=120
OMNICHECK_AI_MAX_ATTEMPTS=2
```

若未來端點需要 Token，使用 `OMNICHECK_AI_API_KEY`，只能放在權限 600 的環境檔或 secret manager，不可提交 Git。

## Rollback

- 先把 `OMNICHECK_AI_ENABLED=false` 並重啟 Web，即可立即停用 AI。
- Application 可切回 `m10.3.2`／前一 release。
- 0009 是 additive audit table，保留不影響 deterministic 報告。
- 正式 EDB 不做 downgrade；問題以 forward-fix migration 處理。
