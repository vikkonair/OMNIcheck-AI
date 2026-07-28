from omni_healthcheck.config import (
    AIConfig,
    JobConfig,
    NodeConfig,
    ReportConfig,
    ScopeConfig,
)
from omni_healthcheck.quality import build_coverage_ledger, build_qa_result
from omni_healthcheck.rules import AssessmentDocument
from omni_healthcheck.schema import (
    CheckResult,
    NormalizedDocument,
    TableEvidence,
    Trace,
)


def _job() -> JobConfig:
    return JobConfig(
        customer="測試客戶",
        period="2026-H1",
        product="EPAS",
        first_healthcheck=True,
        nodes=[NodeConfig(hostname="db-primary", role="Primary")],
        scope=ScopeConfig(),
        report=ReportConfig(template="omni-v4"),
        ai=AIConfig(),
    )


def _normalized(value: str = "EPAS 16.1") -> NormalizedDocument:
    return NormalizedDocument(
        pipeline_version="test",
        checks=[
            CheckResult(
                check_id="database_version",
                section_id="3.1",
                node="db-primary",
                node_role="Primary",
                product="EPAS",
                evidence=TableEvidence(headers=["Output"], rows=[[value]]),
                trace=Trace(
                    parser_id="test.v1",
                    evidence_sha256="a" * 64,
                ),
            )
        ],
        unparsed_allowed_evidence=[],
    )


def _assessment() -> AssessmentDocument:
    return AssessmentDocument(
        ruleset_version="test",
        summary={"normal": 0, "attention": 0, "critical": 0, "pending": 0},
        assessments=[],
    )


def test_quality_gate_detects_unmasked_secret() -> None:
    job = _job()
    normalized = _normalized("password=customer-secret")
    assessment = _assessment()
    coverage = build_coverage_ledger(job, normalized, assessment)
    result = build_qa_result(
        job,
        {"summary": {"unknown_files": 0}, "files": []},
        {"summary": {"pending": 0}, "evidence": []},
        normalized,
        assessment,
        coverage,
    )

    assert result["delivery_allowed"] is False
    assert "security.no_unmasked_secrets" in result["failed_gates"]


def test_missing_optional_coverage_remains_visible_without_blocking() -> None:
    job = _job()
    normalized = _normalized()
    assessment = _assessment()
    coverage = build_coverage_ledger(job, normalized, assessment)
    result = build_qa_result(
        job,
        {"summary": {"unknown_files": 0}, "files": []},
        {"summary": {"pending": 2}, "evidence": []},
        normalized,
        assessment,
        coverage,
    )

    assert coverage["summary"]["missing"] > 0
    assert result["delivery_allowed"] is True
    assert result["diagnostics"]["pending_scope_evidence"] == 2
