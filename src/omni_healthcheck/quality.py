"""Coverage accounting and deterministic delivery quality gates."""

from __future__ import annotations

import json
import re
from collections import Counter

from omni_healthcheck.config import JobConfig
from omni_healthcheck.rules import AssessmentDocument
from omni_healthcheck.schema import NormalizedDocument


OS_EXPECTED = (
    "hostname",
    "os_version",
    "kernel_version",
    "cpu_count",
    "total_memory",
    "total_swap",
    "filesystem_usage",
    "process_state",
    "network_listeners",
    "hugepages",
    "selinux",
    "firewall",
)
DATABASE_EXPECTED = (
    "database_version",
    "database_inventory",
    "connections",
    "transaction_id_age",
    "database_size",
    "extensions",
    "roles_privileges",
    "schema_privileges",
    "pg_hba_conf",
    "postgresql_auto_conf",
    "replication_state",
    "locks",
    "dead_tuples",
    "table_bloat",
    "index_bloat",
    "rarely_used_indexes",
)
SECRET_PATTERN = re.compile(
    r"(?i)[a-z0-9_.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|"
    r"access[_-]?key|private[_-]?key|wrapper\.key)"
    r"\s*(?:=|:)\s*(?!\*{3,}|masked|redacted)([^\s,;]+)"
)


class QualityGateError(ValueError):
    """Raised when a generated job is not safe to deliver."""


def build_coverage_ledger(
    job: JobConfig,
    normalized: NormalizedDocument,
    assessment: AssessmentDocument,
) -> dict:
    available = {(item.node.casefold(), item.check_id) for item in normalized.checks}
    assessed = {
        (item.node.casefold(), ref.check_id)
        for item in assessment.assessments
        for ref in item.evidence_refs
    }
    items: list[dict] = []
    for node in job.nodes:
        for check_id in OS_EXPECTED:
            key = (node.hostname.casefold(), check_id)
            items.append(
                {
                    "node": node.hostname,
                    "node_role": node.role,
                    "domain": "os",
                    "check_id": check_id,
                    "required": False,
                    "evidence_status": "available" if key in available else "missing",
                    "assessment_status": "available" if key in assessed else "not_applicable",
                }
            )
        if node.role == "Primary":
            for check_id in DATABASE_EXPECTED:
                key = (node.hostname.casefold(), check_id)
                items.append(
                    {
                        "node": node.hostname,
                        "node_role": node.role,
                        "domain": "database",
                        "check_id": check_id,
                        "required": check_id == "database_version",
                        "evidence_status": "available" if key in available else "missing",
                        "assessment_status": (
                            "available" if key in assessed else "not_applicable"
                        ),
                    }
                )
    counts = Counter(item["evidence_status"] for item in items)
    return {
        "schema_version": "1.0",
        "summary": {
            "expected": len(items),
            "available": counts["available"],
            "missing": counts["missing"],
            "coverage_percent": round(
                100 * counts["available"] / len(items), 1
            ) if items else 100.0,
        },
        "items": items,
    }


def _gate(gate_id: str, passed: bool, detail: str) -> dict:
    return {"gate_id": gate_id, "status": "passed" if passed else "failed", "detail": detail}


def build_qa_result(
    job: JobConfig,
    inventory: dict,
    scope_ledger: dict,
    normalized: NormalizedDocument,
    assessment: AssessmentDocument,
    coverage: dict,
) -> dict:
    configured = {node.hostname.casefold() for node in job.nodes}
    primary_nodes = [node for node in job.nodes if node.role == "Primary"]
    primary = primary_nodes[0].hostname.casefold() if len(primary_nodes) == 1 else None
    primary_db = [
        check for check in normalized.checks
        if check.node.casefold() == primary
        and check.node_role == "Primary"
        and check.product in {"PostgreSQL", "EPAS"}
        and check.check_id not in {"postgresql_conf", "postgresql_auto_conf", "pg_hba_conf"}
    ]
    evidence_keys = {
        (check.node.casefold(), check.check_id, check.trace.evidence_sha256)
        for check in normalized.checks
    }
    bad_refs = [
        ref.model_dump()
        for item in assessment.assessments
        for ref in item.evidence_refs
        if (ref.node.casefold(), ref.check_id, ref.evidence_sha256) not in evidence_keys
    ]
    foreign_nodes = sorted(
        {
            str(item["node"])
            for item in scope_ledger["evidence"]
            if item["node"] and str(item["node"]).casefold() not in configured
        }
    )
    outward = json.dumps(
        {
            "normalized": normalized.model_dump(mode="json"),
            "assessment": assessment.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    secret_matches = sorted({match.group(0) for match in SECRET_PATTERN.finditer(outward)})
    assessment_text = json.dumps(assessment.model_dump(mode="json"), ensure_ascii=False)
    source_mentions = sorted(
        {
            item["path"]
            for item in inventory["files"]
            if item["path"] and item["path"] in assessment_text
        }
    )
    all_non_normal = [
        item for item in assessment.assessments if item.status != "normal"
    ]
    gates = [
        _gate("topology.exactly_one_primary", len(primary_nodes) == 1,
              f"configured_primary_count={len(primary_nodes)}"),
        _gate("evidence.primary_database_present", bool(primary_db),
              f"primary_logical_database_checks={len(primary_db)}"),
        _gate("assessment.visible_evidence", not bad_refs,
              f"invalid_evidence_references={len(bad_refs)}"),
        _gate("security.no_unmasked_secrets", not secret_matches,
              f"unmasked_secret_matches={len(secret_matches)}"),
        _gate("content.no_source_paths", not source_mentions,
              f"source_path_mentions={len(source_mentions)}"),
        _gate("isolation.no_foreign_nodes", not foreign_nodes,
              f"foreign_nodes={foreign_nodes}"),
        _gate("summary.non_normal_accounted", (
            len(all_non_normal)
            == sum(assessment.summary.get(state, 0)
                   for state in ("attention", "critical", "pending"))
        ), f"non_normal_assessments={len(all_non_normal)}"),
        _gate("coverage.required_checks", not any(
            item["required"] and item["evidence_status"] == "missing"
            for item in coverage["items"]
        ), "required coverage items must be available"),
    ]
    failed = [gate["gate_id"] for gate in gates if gate["status"] == "failed"]
    return {
        "schema_version": "1.0",
        "status": "passed" if not failed else "failed",
        "delivery_allowed": not failed,
        "summary": {"passed": len(gates) - len(failed), "failed": len(failed)},
        "failed_gates": failed,
        "gates": gates,
        "diagnostics": {
            "bad_evidence_references": bad_refs,
            "foreign_nodes": foreign_nodes,
            "secret_match_count": len(secret_matches),
            "source_path_mention_count": len(source_mentions),
            "pending_scope_evidence": scope_ledger["summary"]["pending"],
            "unknown_files": inventory["summary"]["unknown_files"],
        },
    }
