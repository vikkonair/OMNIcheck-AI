"""Optional, audited Traditional-Chinese presentation translations for CVEs.

This module never changes CVE applicability, scores, versions, or sources.  It
only adds a cached Chinese rendering of an already-authoritative English repair
summary, with the original summary retained as the fact source.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from omni_healthcheck.ai_gateway import OllamaGateway, _sha


def _content(response: dict[str, Any]) -> dict[str, Any]:
    value = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not isinstance(value, str):
        raise ValueError("CVE translation response is not text")
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("translations"), list):
        raise ValueError("CVE translation response has invalid JSON shape")
    return parsed


def translate_cve_report(
    report: dict[str, Any], *, job_id: str, item_id: str, gateway: OllamaGateway
) -> dict[str, Any]:
    """Add Chinese repair summaries in bounded, auditable batches.

    Failed batches intentionally retain the authoritative English original.
    """
    entries = [
        entry
        for update_item in report.get("version_updates") or []
        for entry in update_item.get("cves") or []
        if str(entry.get("summary", "")).strip()
        and not str(entry.get("summary_zh", "")).strip()
    ]
    if not entries or not gateway.settings.enabled:
        return report
    for offset in range(0, len(entries), 20):
        batch = entries[offset : offset + 20]
        source = [
            {"id": str(entry["id"]), "summary": str(entry["summary"])}
            for entry in batch
        ]
        prompt = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是資料庫資安報告翻譯器。只將每一筆官方 CVE 修正內容"
                        "忠實翻譯為繁體中文；不得新增、刪除或推論版本、CVSS、影響範圍或"
                        "修補方式。只輸出 JSON object：{\"translations\":[{\"id\":\"CVE...\","
                        "\"summary_zh\":\"...\"}]}。每個 id 必須與輸入完全相同。"
                    ),
                },
                {"role": "user", "content": json.dumps(source, ensure_ascii=False)},
            ]
        }
        request_id = gateway.audit_store.start(
            job_id=job_id,
            item_id=item_id,
            provider="ollama",
            model=gateway.settings.model,
            prompt_version="cve-repair-translation-v1",
            requested_by="system:cve-translation",
            prompt_sha256=_sha(prompt),
            sanitized_prompt=prompt,
        )
        started = time.monotonic()
        try:
            response = gateway.transport(
                gateway.settings.endpoint,
                {
                    "model": gateway.settings.model,
                    **prompt,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                {"Content-Type": "application/json"},
                gateway.settings.timeout_seconds,
            )
            translations = _content(response)["translations"]
            allowed = {item["id"] for item in source}
            translated = {
                str(item.get("id")): str(item.get("summary_zh", "")).strip()
                for item in translations
                if isinstance(item, dict)
                and str(item.get("id")) in allowed
                and 1 <= len(str(item.get("summary_zh", "")).strip()) <= 2000
            }
            for entry in batch:
                if translated.get(str(entry["id"])):
                    entry["summary_zh"] = translated[str(entry["id"])]
            gateway.audit_store.finish(
                request_id,
                status="succeeded",
                attempts=1,
                duration_ms=round((time.monotonic() - started) * 1000),
                response_sha256=_sha(response),
                sanitized_response=response,
                usage=response.get("usage") if isinstance(response.get("usage"), dict) else None,
            )
        except Exception as exc:
            gateway.audit_store.finish(
                request_id,
                status="failed",
                attempts=1,
                duration_ms=round((time.monotonic() - started) * 1000),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
    return report
