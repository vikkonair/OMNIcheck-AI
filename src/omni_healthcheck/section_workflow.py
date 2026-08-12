"""Versioned, AI-optional narrative workflow built from deterministic assessments."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omni_healthcheck.rules import (
    AssessmentDocument,
    EvidenceReference,
    RuleTrace,
    Status,
)


WorkflowStatus = Literal["generated", "ai_drafted", "reviewed", "approved"]
NarrativeSource = Literal["deterministic_template", "ai", "engineer"]


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Narrative(WorkflowModel):
    source: NarrativeSource
    observation: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class SectionWorkflowItem(WorkflowModel):
    section_key: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    check_id: str = Field(min_length=1)
    node: str = Field(min_length=1)
    status: Status
    workflow_status: WorkflowStatus = "generated"
    revision: int = Field(default=1, ge=1)
    deterministic: Narrative
    ai_draft: Narrative | None = None
    reviewed: Narrative | None = None
    approved: Narrative | None = None
    selected_source: Literal["deterministic_template", "approved"] = (
        "deterministic_template"
    )
    evidence_refs: list[EvidenceReference] = Field(min_length=1)
    trace: RuleTrace

    @model_validator(mode="after")
    def workflow_is_fail_closed(self) -> "SectionWorkflowItem":
        if self.deterministic.source != "deterministic_template":
            raise ValueError("deterministic narrative must use deterministic_template")
        if self.ai_draft is not None and self.ai_draft.source != "ai":
            raise ValueError("AI draft must use ai source")
        if self.reviewed is not None and self.reviewed.source != "engineer":
            raise ValueError("reviewed narrative must use engineer source")
        if self.approved is not None and self.approved.source != "engineer":
            raise ValueError("approved narrative must use engineer source")
        if self.workflow_status == "ai_drafted" and self.ai_draft is None:
            raise ValueError("AI draft is required for ai_drafted status")
        if self.workflow_status in {"reviewed", "approved"} and self.reviewed is None:
            raise ValueError("engineer review is required for this workflow status")
        if self.workflow_status == "approved" and self.approved is None:
            raise ValueError("approved narrative is required for approved status")
        if self.selected_source == "approved":
            if self.workflow_status != "approved" or self.approved is None:
                raise ValueError("approved text can only be selected after approval")
        return self

    @property
    def selected_narrative(self) -> Narrative:
        if self.selected_source == "approved" and self.approved is not None:
            return self.approved
        return self.deterministic


class SectionWorkflowDocument(WorkflowModel):
    schema_version: Literal["1.0"] = "1.0"
    contract: Literal["omnicheck.section-workflow"] = "omnicheck.section-workflow"
    ruleset_version: str
    ai_enabled: bool = False
    renderer_uses_ai: bool = False
    items: list[SectionWorkflowItem]


def build_section_workflow(assessment: AssessmentDocument) -> SectionWorkflowDocument:
    """Create a deterministic baseline; no AI text is selected or rendered."""

    section_keys = [
        f"{item.section_id}:{item.node}:{item.check_id}"
        for item in assessment.assessments
    ]
    duplicates = sorted(
        key for key, count in Counter(section_keys).items() if count > 1
    )
    if duplicates:
        raise ValueError(
            "duplicate section workflow key(s): "
            + ", ".join(duplicates)
            + "; database evidence may have been mapped to the same node"
        )

    return SectionWorkflowDocument(
        ruleset_version=assessment.ruleset_version,
        items=[
            SectionWorkflowItem(
                section_key=f"{item.section_id}:{item.node}:{item.check_id}",
                section_id=item.section_id,
                check_id=item.check_id,
                node=item.node,
                status=item.status,
                deterministic=Narrative(
                    source="deterministic_template",
                    observation=item.observation,
                    recommendation=item.recommendation,
                ),
                evidence_refs=item.evidence_refs,
                trace=item.trace,
            )
            for item in assessment.assessments
        ],
    )


def attach_ai_draft(
    item: SectionWorkflowItem, *, observation: str, recommendation: str
) -> SectionWorkflowItem:
    """Attach an untrusted AI draft without changing facts or selected text."""

    return item.model_copy(
        update={
            "workflow_status": "ai_drafted",
            "revision": item.revision + 1,
            "ai_draft": Narrative(
                source="ai",
                observation=observation,
                recommendation=recommendation,
            ),
        },
        deep=True,
    )


def review_draft(
    item: SectionWorkflowItem, *, observation: str, recommendation: str
) -> SectionWorkflowItem:
    """Save engineer text based on either AI or deterministic content."""
    return item.model_copy(
        update={
            "workflow_status": "reviewed",
            "revision": item.revision + 1,
            "reviewed": Narrative(
                source="engineer",
                observation=observation,
                recommendation=recommendation,
            ),
        },
        deep=True,
    )


def apply_approved_narratives(
    assessment: AssessmentDocument,
    workflow: SectionWorkflowDocument,
) -> AssessmentDocument:
    """Overlay approved text only; all other stages remain deterministic."""

    by_key = {item.section_key: item for item in workflow.items}
    updated = []
    for item in assessment.assessments:
        key = f"{item.section_id}:{item.node}:{item.check_id}"
        workflow_item = by_key.get(key)
        narrative = (
            workflow_item.selected_narrative
            if workflow_item is not None
            else None
        )
        if narrative is None:
            updated.append(item)
            continue
        updated.append(
            item.model_copy(
                update={
                    "observation": narrative.observation,
                    "recommendation": narrative.recommendation,
                },
                deep=True,
            )
        )
    return assessment.model_copy(update={"assessments": updated}, deep=True)


def approve_review(item: SectionWorkflowItem) -> SectionWorkflowItem:
    if item.reviewed is None:
        raise ValueError("an engineer review is required before approval")
    return item.model_copy(
        update={
            "workflow_status": "approved",
            "revision": item.revision + 1,
            "approved": item.reviewed.model_copy(deep=True),
            "selected_source": "approved",
        },
        deep=True,
    )
