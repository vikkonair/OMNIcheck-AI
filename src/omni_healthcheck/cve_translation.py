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


_GENERIC_TRANSLATION_PHRASES = (
    "更多細節",
    "更多資訊",
    "詳細資訊",
    "請參閱",
    "詳情",
)


def _usable_translation(value: Any) -> str:
    """Accept useful Chinese prose, but fail back to the authoritative source.

    A generic trailing phrase is worse than retaining English: it suggests an
    explanation exists while withholding the actual CVE repair detail.
    """
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not 12 <= len(text) <= 2000:
        return ""
    if not re.search(r"[\u4e00-\u9fff]", text):
        return ""
    if any(phrase in text for phrase in _GENERIC_TRANSLATION_PHRASES):
        return ""
    return text


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
                        "你是資料庫資安報告翻譯器。針對每一筆官方英文 CVE 修正內容，"
                        "以一至兩句繁體中文說明修正的具體行為與其可避免的影響；只能根據"
                        "輸入英文內容，不得新增、刪除或推論版本、CVSS、影響範圍或修補方式。"
                        "不得使用「更多細節」、「更多資訊」、「詳情」、「請參閱」等空泛"
                        "結尾，也不可保留英文。若原文資訊不足，僅翻譯原文可確認的事實。"
                        "只輸出 JSON object：{\"translations\":[{\"id\":\"CVE...\","
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
                str(item.get("id")): _usable_translation(item.get("summary_zh", ""))
                for item in translations
                if isinstance(item, dict)
                and str(item.get("id")) in allowed
                and _usable_translation(item.get("summary_zh", ""))
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
