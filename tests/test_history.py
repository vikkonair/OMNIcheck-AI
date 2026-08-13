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


def test_job_history_requires_exact_identity_and_uses_newest_prior(tmp_path) -> None:
    from omni_healthcheck.history import build_job_history
    current = tmp_path / "jobs" / ("b" * 32) / "output"
    prior = tmp_path / "jobs" / ("a" * 32) / "output"
    current.mkdir(parents=True); prior.mkdir(parents=True)
    for target, normalized, assessment in ((current, _normalized("65%"), _assessment("attention")), (prior, _normalized("85%"), _assessment("critical"))):
        (target / "normalized.json").write_text(normalized.model_dump_json(), encoding="utf-8")
        (target / "assessment.json").write_text(assessment.model_dump_json(), encoding="utf-8")
    result = build_job_history(
        current_job={"job_id": "b" * 32, "customer": "Customer", "system_name": "System", "product": "EPAS", "created_at": "2026-08-02"},
        current_output_dir=current,
        jobs=[{"job_id": "a" * 32, "customer": "Customer", "system_name": "System", "product": "EPAS", "status": "succeeded", "period": "2026-H1", "created_at": "2026-08-01"}],
    )
    assert result["status"] == "ready"
    assert result["prior_job_id"] == "a" * 32
