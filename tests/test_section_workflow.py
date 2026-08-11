from __future__ import annotations

import pytest

from omni_healthcheck.rules import (
    Assessment,
    AssessmentDocument,
    EvidenceReference,
    RuleTrace,
)
from omni_healthcheck.section_workflow import (
    SectionWorkflowItem,
    approve_review,
    attach_ai_draft,
    apply_approved_narratives,
    build_section_workflow,
    review_draft,
)


def assessment_document() -> AssessmentDocument:
    return AssessmentDocument(
        ruleset_version="2026.1",
        summary={"normal": 1},
        assessments=[Assessment(
            check_id="filesystem_usage",
            section_id="3.7",
            node="db-primary",
            status="normal",
            observation="使用率正常。\n結論：目前無容量風險。",
            recommendation="持續監控。",
            evidence_refs=[EvidenceReference(
                check_id="filesystem_usage",
                node="db-primary",
                evidence_sha256="a" * 64,
            )],
            trace=RuleTrace(rule_id="filesystem.threshold", rule_version="2026.1"),
        )],
    )


def test_builds_deterministic_ai_disabled_contract() -> None:
    document = build_section_workflow(assessment_document())
    item = document.items[0]

    assert document.schema_version == "1.0"
    assert document.ai_enabled is False
    assert document.renderer_uses_ai is False
    assert item.section_key == "3.7:db-primary:filesystem_usage"
    assert item.workflow_status == "generated"
    assert item.selected_narrative == item.deterministic
    assert item.ai_draft is None


def test_ai_draft_cannot_replace_selected_text_without_engineer_approval() -> None:
    original = build_section_workflow(assessment_document()).items[0]
    drafted = attach_ai_draft(
        original,
        observation="AI 草稿觀察",
        recommendation="AI 草稿建議",
    )

    assert original.ai_draft is None
    assert drafted.workflow_status == "ai_drafted"
    assert drafted.selected_source == "deterministic_template"
    assert drafted.selected_narrative == original.deterministic
    assert drafted.status == original.status
    assert drafted.evidence_refs == original.evidence_refs
    assert drafted.trace == original.trace

    reviewed = review_draft(
        drafted,
        observation="工程師確認觀察",
        recommendation="工程師確認建議",
    )
    approved = approve_review(reviewed)
    assert approved.workflow_status == "approved"
    assert approved.selected_source == "approved"
    assert approved.selected_narrative.observation == "工程師確認觀察"
    assert approved.status == original.status
    assert approved.trace == original.trace


def test_review_and_approval_fail_closed() -> None:
    original = build_section_workflow(assessment_document()).items[0]
    reviewed = review_draft(original, observation="x", recommendation="y")
    assert reviewed.ai_draft is None
    assert reviewed.workflow_status == "reviewed"
    with pytest.raises(ValueError, match="engineer review"):
        approve_review(original)

    forged = original.model_dump(mode="json")
    forged["selected_source"] = "approved"
    with pytest.raises(ValueError, match="only be selected after approval"):
        SectionWorkflowItem.model_validate(forged)


def test_renderer_overlay_uses_only_approved_or_deterministic() -> None:
    assessment = assessment_document()
    original = build_section_workflow(assessment)
    drafted = original.model_copy(update={"items": [attach_ai_draft(
        original.items[0], observation="AI 不可見", recommendation="AI 不可見"
    )]})
    assert apply_approved_narratives(assessment, drafted) == assessment

    reviewed = review_draft(
        drafted.items[0], observation="工程師觀察", recommendation="工程師建議"
    )
    reviewed_document = drafted.model_copy(update={"items": [reviewed]})
    assert apply_approved_narratives(assessment, reviewed_document) == assessment

    approved_document = reviewed_document.model_copy(
        update={"items": [approve_review(reviewed)]}
    )
    rendered = apply_approved_narratives(assessment, approved_document)
    assert rendered.assessments[0].observation == "工程師觀察"
    assert rendered.assessments[0].recommendation == "工程師建議"
