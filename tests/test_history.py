from __future__ import annotations

from omni_healthcheck.history import compare_snapshots
from omni_healthcheck.rules import AssessmentDocument, Assessment, EvidenceReference, RuleTrace
from omni_healthcheck.schema import CheckResult, NormalizedDocument, TableEvidence, Trace


def _normalized(value: str) -> NormalizedDocument:
    return NormalizedDocument(checks=[CheckResult(
        check_id="filesystem_usage", section_id="3.1", node="db-primary",
        node_role="Primary", product="OS", evidence=TableEvidence(
            headers=["Filesystem", "Use%"], rows=[["/data", value]],
        ), trace=Trace(parser_id="test", evidence_sha256=("a" if value == "65%" else "b") * 64),
    )], unparsed_allowed_evidence=[], pipeline_version="test")


def _assessment(status: str) -> AssessmentDocument:
    item = Assessment(
        check_id="filesystem_usage", section_id="3.1", node="db-primary",
        status=status, observation="x\n結論：x", recommendation="x",
        evidence_refs=[EvidenceReference(
            check_id="filesystem_usage", node="db-primary", evidence_sha256="a" * 64,
        )], trace=RuleTrace(rule_id="test", rule_version="test"),
    )
    return AssessmentDocument(ruleset_version="test", summary={}, assessments=[item])


def test_history_comparison_reports_status_direction_and_evidence_change() -> None:
    result = compare_snapshots(
        current_normalized=_normalized("65%"), current_assessment=_assessment("attention"),
        prior_normalized=_normalized("85%"), prior_assessment=_assessment("critical"),
        prior_job_id="a" * 32, prior_period="2026-H1",
    )
    assert result["summary"]["improved"] == 1
    assert result["changes"][0]["check_id"] == "filesystem_usage"
    assert result["changes"][0]["prior_status"] == "critical"
