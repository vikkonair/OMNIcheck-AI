"""Fail-closed quality gates for customer-facing V4 report JSON."""

from __future__ import annotations

from pathlib import Path


VALID_STATUSES = {"正常", "注意", "待確認", "異常", "資料不足", "不適用"}


class V4QualityError(ValueError):
    """Raised when a V4 report is not safe to render."""


def validate_v4_report(
    report: dict, scope_ledger: dict, *, raise_on_failure: bool = True
) -> dict:
    failures: list[str] = []
    pending = [
        item["path"] for item in scope_ledger["evidence"]
        if item["decision"] == "pending"
    ]
    if pending:
        failures.append(f"scope.pending_evidence={pending}")

    primary = report.get("database_source_hostname")
    for chapter in report.get("chapters") or []:
        database_chapter = chapter.get("source_scope") == "database"
        for section in chapter.get("sections") or []:
            for item in section.get("items") or []:
                evidence = item.get("evidence") or {}
                evidence_type = evidence.get("type")
                visible = (
                    bool(evidence.get("content"))
                    if evidence_type == "text"
                    else bool(evidence.get("headers") or evidence.get("rows"))
                    if evidence_type == "table"
                    else bool(evidence.get("path"))
                    if evidence_type == "image"
                    else False
                )
                if not visible:
                    failures.append(f"item.no_visible_output={item.get('title')}")
                if evidence_type == "image" and not Path(evidence["path"]).is_file():
                    failures.append(f"item.image_missing={item.get('title')}")
                if item.get("assessment_display") is False:
                    continue
                if item.get("status") not in VALID_STATUSES:
                    failures.append(f"item.invalid_status={item.get('title')}")
                if "結論：" not in str(item.get("observation", "")):
                    failures.append(f"item.missing_conclusion={item.get('title')}")
                if not str(item.get("recommendation", "")).strip():
                    failures.append(f"item.missing_recommendation={item.get('title')}")
                if database_chapter and item.get("node") != primary:
                    failures.append(f"database.non_primary={item.get('title')}")

    result = {
        "schema_version": "1.0",
        "status": "failed" if failures else "passed",
        "delivery_allowed": not failures,
        "failed_gates": failures,
    }
    if failures and raise_on_failure:
        raise V4QualityError("V4 report quality gates failed: " + "; ".join(failures))
    return result
