# M14.1 Ollama Gateway 驗證紀錄

日期：2026-08-11

## 本機與公司候選

- 本機／公司完整 Pytest：101 passed。
- Alembic 單一 head：`0009_m14_ai_gateway`。
- 公司 Application release：`6b24cb5`。
- Application rollback：`48eac67`。
- 公司 EDB：`0008_m10_3_sections → 0009_m14_ai_gateway` 成功。
- Migration 前 schema-only backup：`/data/omnicheck/archive/m14-1-pre-0009/omnicheck-schema-0008.sql`。
- Backup SHA-256：`1056f00a8653b89c3d8acd5766f5a666b3d3f07300ac82294ccd1902130c09b8`。
- Web／Worker active；health 顯示 database／external worker／AI Gateway enabled。

## Ollama 連線

- 來源：App VM `192.168.118.77`。
- Endpoint：`http://192.168.68.39:11434/v1/chat/completions`。
- Model：`gpt-oss:20b`。
- 最小連線回覆：`OMNIcheck AI connection OK`。
- 目前內網 HTTP、無 Token；M15 應強化網路 ACL／TLS／authentication。

## 真實 AI Draft E2E

- Job：`774499b66693455eb16d14f04a5fd687`。
- Section：`4.12:golden-primary:pg_hba_conf`。
- AI audit request：`c8253fe505ae445c868f322a6ee10527`。
- Model duration：10,718 ms。
- Usage：prompt 638、completion 57、total 695 tokens。
- Prompt 未含原 hostname、customer 或 IPv4。
- Audit response 未保存 reasoning。
- AI draft 成功寫入 revision 2，但 selected source 維持 deterministic。
- 核准前重新 render，AI draft 未出現在 report-model。
- Engineer review revision 3；Reviewer approval revision 4。
- 核准後重新 render，approved 文字進入 report-model。
- Revision actions：`generated → ai_drafted → reviewed → approved`。

## Fallback／安全測試

- node、IPv4、email、password／secret／token／API key 與 credential URI 遮蔽測試通過。
- 不合法 JSON／schema 回覆：audit failed、Section 不變、deterministic fallback。
- AI disabled 即使 endpoint 設定無效，Application 與 deterministic 報告仍可正常運作。
- stale expected revision：HTTP 409；AI 完成後發生 concurrency conflict 時 audit 標記 discarded_stale。
- AI 不可改 status、evidence、trace、Topology、Scope 或 selected source。

## 結論

M14.1 驗證成功。單一 Section Ollama 草稿、遮蔽、EDB 稽核、人工核准與 fail-safe Renderer 已完成。批次前端、排程／rate limit、主管摘要、歷史摘要與問答留待後續 M14.x。
