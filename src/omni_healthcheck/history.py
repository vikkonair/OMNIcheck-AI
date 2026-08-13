"""Deterministic M12 comparisons between two immutable health-check snapshots.

The comparison deliberately consumes Canonical JSON and deterministic
assessment output only.  It never uses AI and never changes current findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omni_healthcheck.rules import AssessmentDocument
from omni_healthcheck.schema import NormalizedDocument


STATUS_RANK = {"normal": 0, "pending": 1, "attention": 2, "critical": 3}


def _check_key(check: dict[str, Any]) -> tuple[str, str]:
    return (str(check["node"]).casefold(), str(check["check_id"]))


def _assessment_index(document: AssessmentDocument) -> dict[tuple[str, str], str]:
    return {(item.node.casefold(), item.check_id): item.status for item in document.assessments}


def _evidence_hash(check: dict[str, Any]) -> str:
    return str(check["trace"]["evidence_sha256"])


def compare_snapshots(
    *,
    current_normalized: NormalizedDocument,
    current_assessment: AssessmentDocument,
    prior_normalized: NormalizedDocument,
    prior_assessment: AssessmentDocument,
    prior_job_id: str,
    prior_period: str,
) -> dict[str, Any]:
    """Return explainable additions, removals, evidence and status changes."""
    current_checks = {
        _check_key(record): record
        for record in (item.model_dump(mode="json") for item in current_normalized.checks)
    }
    prior_checks = {
        _check_key(record): record
        for record in (item.model_dump(mode="json") for item in prior_normalized.checks)
    }
    current_status = _assessment_index(current_assessment)
    prior_status = _assessment_index(prior_assessment)
    changes: list[dict[str, Any]] = []
    for key in sorted(set(current_checks) | set(prior_checks)):
        before, after = prior_checks.get(key), current_checks.get(key)
        node, check_id = key
        if before is None:
            changes.append({"node": node, "check_id": check_id, "change": "added", "prior_status": None, "current_status": current_status.get(key)})
            continue
        if after is None:
            changes.append({"node": node, "check_id": check_id, "change": "removed", "prior_status": prior_status.get(key), "current_status": None})
            continue
        prior_value, current_value = prior_status.get(key), current_status.get(key)
        if prior_value != current_value:
            prior_rank, current_rank = STATUS_RANK.get(prior_value or "normal", 0), STATUS_RANK.get(current_value or "normal", 0)
            direction = "improved" if current_rank < prior_rank else "worsened" if current_rank > prior_rank else "changed"
            changes.append({"node": node, "check_id": check_id, "change": direction, "prior_status": prior_value, "current_status": current_value})
        elif _evidence_hash(before) != _evidence_hash(after):
            changes.append({"node": node, "check_id": check_id, "change": "evidence_changed", "prior_status": prior_value, "current_status": current_value})
    summary = {kind: sum(item["change"] == kind for item in changes) for kind in ("added", "removed", "improved", "worsened", "evidence_changed")}
    return {
        "schema_version": "1.0",
        "comparison_version": "m12.history.v1",
        "prior_job_id": prior_job_id,
        "prior_period": prior_period,
        "summary": summary,
        "changes": changes,
    }


def load_history_inputs(output_dir) -> tuple[NormalizedDocument, AssessmentDocument]:
    """Load immutable historical documents from a completed Job output folder."""
    normalized = NormalizedDocument.model_validate(json.loads(
        (output_dir / "normalized.json").read_text(encoding="utf-8")
    ))
    assessment = AssessmentDocument.model_validate(json.loads(
        (output_dir / "assessment.json").read_text(encoding="utf-8")
    ))
    return normalized, assessment


def build_job_history(
    *,
    current_job: dict[str, Any],
    current_output_dir: Path,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare a Job with the newest compatible completed predecessor.

    The classic UI has intentionally no Customer/System selector.  Until
    internal identities are backfilled, matching is deliberately conservative:
    exact customer and system name, same product, completed predecessor only.
    """
    customer = str(current_job.get("customer") or "").strip().casefold()
    system = str(current_job.get("system_name") or "").strip().casefold()
    product = str(current_job.get("product") or "").strip().casefold()
    created_at = str(current_job.get("created_at") or "")
    candidates = [
        item for item in jobs
        if item.get("job_id") != current_job.get("job_id")
        and item.get("status") == "succeeded"
        and str(item.get("customer") or "").strip().casefold() == customer
        and str(item.get("system_name") or "").strip().casefold() == system
        and str(item.get("product") or "").strip().casefold() == product
        and str(item.get("created_at") or "") < created_at
    ]
    if not candidates:
        return {
            "schema_version": "1.0", "comparison_version": "m12.history.v1",
            "status": "no_prior_baseline", "message": "尚無同客戶、系統與產品的前期完成案件可供比較。",
            "changes": [], "summary": {},
        }
    prior = max(candidates, key=lambda item: str(item.get("created_at") or ""))
    prior_output = current_output_dir.parent.parent / str(prior["job_id"]) / "output"
    required = (prior_output / "normalized.json", prior_output / "assessment.json")
    if not all(path.is_file() for path in required):
        return {
            "schema_version": "1.0", "comparison_version": "m12.history.v1",
            "status": "prior_artifacts_unavailable", "message": "已找到前期案件，但其 Canonical 歷史產物不完整。",
            "prior_job_id": prior["job_id"], "changes": [], "summary": {},
        }
    current_normalized, current_assessment = load_history_inputs(current_output_dir)
    prior_normalized, prior_assessment = load_history_inputs(prior_output)
    return {
        "status": "ready",
        "message": "已完成與前一期相同客戶／系統／產品案件的 deterministic 比較。",
        **compare_snapshots(
            current_normalized=current_normalized, current_assessment=current_assessment,
            prior_normalized=prior_normalized, prior_assessment=prior_assessment,
            prior_job_id=str(prior["job_id"]), prior_period=str(prior.get("period") or ""),
        ),
    }
