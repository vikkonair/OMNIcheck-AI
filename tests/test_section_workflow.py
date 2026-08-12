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
    apply_workflow_to_v4_report,
    build_section_workflow,
    build_v4_section_workflow,
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


def test_duplicate_section_keys_fail_before_persistence() -> None:
    assessment = assessment_document()
    assessment = assessment.model_copy(
        update={"assessments": assessment.assessments * 2}, deep=True
    )

    with pytest.raises(ValueError, match="duplicate section workflow key"):
        build_section_workflow(assessment)


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


def test_renderer_uses_ai_draft_only_when_document_policy_enables_it() -> None:
    assessment = assessment_document()
    original = build_section_workflow(assessment)
    drafted = original.model_copy(update={"items": [attach_ai_draft(
        original.items[0], observation="AI 不可見", recommendation="AI 不可見"
    )]})
    assert apply_approved_narratives(assessment, drafted) == assessment

    ai_delivery = drafted.model_copy(update={"renderer_uses_ai": True})
    ai_rendered = apply_approved_narratives(assessment, ai_delivery)
    assert ai_rendered.assessments[0].observation == "AI 不可見"
    assert ai_rendered.assessments[0].recommendation == "AI 不可見"

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


def test_v4_workflow_covers_visible_text_and_monitoring_image(tmp_path) -> None:
    image = tmp_path / "cpu.png"
    image.write_bytes(b"not-real-image")
    report = {"chapters": [{"sections": [{
        "number": "3.8",
        "items": [
            {
                "title": "Table Bloat", "status": "注意", "node": "primary",
                "observation": "原始觀察。\n結論：需要處理。",
                "recommendation": "執行 VACUUM FULL。", "evidence": {"rows": []},
            },
            {
                "title": "CPU 使用率", "status": "待確認", "node": "primary",
                "observation": "已納入圖表。\n結論：待確認。",
                "recommendation": "確認趨勢。",
                "evidence": {"type": "image", "path": str(image)},
            },
            {
                "title": "Extension 清單", "assessment_display": False,
                "evidence": {"type": "table", "headers": ["Extension"], "rows": [["postgis"]]},
            },
        ],
    }]}]}

    workflow = build_v4_section_workflow(report, "2026.2")
    assert len(workflow.items) == 2
    assert workflow.items[0].check_id == "table_bloat"
    assert workflow.items[0].evidence_snapshot == {"rows": []}
    assert workflow.items[1].check_id == "monitoring_cpu"
    assert workflow.items[1].media is not None
    assert workflow.items[1].media.path == str(image)
    assert workflow.items[1].evidence_snapshot == {"type": "image"}

    approved = approve_review(review_draft(
        workflow.items[0], observation="覆核觀察。", recommendation="覆核建議。"
    ))
    updated = apply_workflow_to_v4_report(
        report, workflow.model_copy(update={"items": [approved, workflow.items[1]]})
    )
    assert updated["chapters"][0]["sections"][0]["items"][0]["observation"] == "覆核觀察。"
    assert updated["chapters"][0]["sections"][0]["items"][1]["observation"] == "已納入圖表。\n結論：待確認。"
