"""Versioned, AI-optional narrative workflow built from deterministic assessments."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
from pathlib import Path
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
    # Workflow payloads are persisted as JSON. Ignore future additive fields so
    # an application rollback can still read jobs created by a newer release.
    model_config = ConfigDict(extra="ignore")


class Narrative(WorkflowModel):
    source: NarrativeSource
    observation: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class WorkflowMedia(WorkflowModel):
    type: Literal["image"]
    path: str = Field(min_length=1)
    media_type: str = Field(pattern=r"^image/")


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
    evidence_snapshot: dict | None = None
    trace: RuleTrace
    media: WorkflowMedia | None = None

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


def narrative_for_render(
    item: SectionWorkflowItem, *, renderer_uses_ai: bool
) -> Narrative:
    """Select report prose without misrepresenting an AI draft as approved."""
    if item.selected_source == "approved" and item.approved is not None:
        return item.approved
    if renderer_uses_ai and item.ai_draft is not None:
        return item.ai_draft
    return item.deterministic


class SectionWorkflowDocument(WorkflowModel):
    schema_version: Literal["1.0"] = "1.0"
    contract: Literal["omnicheck.section-workflow"] = "omnicheck.section-workflow"
    ruleset_version: str
    ai_enabled: bool = False
    renderer_uses_ai: bool = False
    items: list[SectionWorkflowItem]


V4_STATUS = {"正常": "normal", "注意": "attention", "異常": "critical", "待確認": "pending"}


def _v4_check_id(title: str) -> str:
    aliases = {
        "主機與作業系統組態彙整": "system_configuration_summary",
        "檔案系統容量": "filesystem_usage",
        "版本資訊": "database_version",
        "Extension 清單": "extensions",
        "資料庫清單": "database_inventory",
        "Checkpoint 狀態": "checkpoint_activity",
        "SLRU 狀態": "slru_status",
        "資料量與大型資料表": "largest_tables",
        "Schema Default Privileges": "schema_default_privileges",
        "PEM / EFM 服務摘要": "pem_efm_summary",
        "PEM / EFM / XDB 服務摘要": "pem_efm_summary",
        "Primary 設定檔": "primary_configuration",
        "資料庫連線設定": "database_connections",
        "Transaction ID 年齡": "transaction_id_age",
        "Lock 狀態": "lock_status",
        "Dead Tuples": "dead_tuples",
        "Dead Tuple": "dead_tuples",
        "Table Bloat": "table_bloat",
        "Index Bloat": "index_bloat",
        "罕用索引": "rarely_used_indexes",
        "同步狀態": "replication_status",
        "Roles Privileges": "roles_privileges",
        "Schema Privileges": "schema_privileges",
        "備份狀態": "backup_status",
    }
    if title in aliases:
        return aliases[title]
    monitoring_aliases = {
        "CPU": "monitoring_cpu",
        "Memory": "monitoring_memory",
        "Disk": "monitoring_disk",
        "Process": "monitoring_process",
        "Commit": "monitoring_commit_rollback",
        "Transaction": "monitoring_transaction",
        "記憶體": "monitoring_memory",
        "磁碟": "monitoring_disk",
        "程序": "monitoring_process",
        "交易": "monitoring_transaction",
    }
    for prefix, check_id in monitoring_aliases.items():
        if title.casefold().startswith(prefix.casefold()):
            return check_id
    value = re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")
    return value or "report_section"


def _v4_section_key(section_number: str, ordinal: int, title: str) -> str:
    return f"v4:{section_number}:{ordinal}:{_v4_check_id(title)}"


def build_v4_section_workflow(v4_report: dict, ruleset_version: str) -> SectionWorkflowDocument:
    """Create one workflow item for every customer-visible V4 report item."""
    items = []
    for chapter in v4_report.get("chapters", []):
        for section in chapter.get("sections", []):
            for ordinal, report_item in enumerate(section.get("items", [])):
                if report_item.get("assessment_display") is False:
                    continue
                title = str(report_item.get("title") or "Report Section")
                evidence = report_item.get("evidence") or {}
                digest = hashlib.sha256(
                    json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest()
                media = None
                if evidence.get("type") == "image" and evidence.get("path"):
                    suffix = Path(str(evidence["path"])).suffix.casefold()
                    media = WorkflowMedia(
                        type="image",
                        path=str(evidence["path"]),
                        media_type={
                            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".png": "image/png", ".webp": "image/webp",
                            ".tif": "image/tiff", ".tiff": "image/tiff",
                        }.get(suffix, "image/png"),
                    )
                evidence_snapshot = {
                    key: value
                    for key, value in evidence.items()
                    if key not in {"path", "image_base64", "data"}
                }
                items.append(SectionWorkflowItem(
                    section_key=_v4_section_key(str(section["number"]), ordinal, title),
                    section_id=str(section["number"]),
                    check_id=_v4_check_id(title),
                    node=str(report_item.get("node") or "all-nodes"),
                    status=V4_STATUS.get(str(report_item.get("status")), "pending"),
                    deterministic=Narrative(
                        source="deterministic_template",
                        observation=str(report_item.get("observation") or "已彙整當期 Output。\n結論：本項仍待確認"),
                        recommendation=str(report_item.get("recommendation") or "確認 Output 後完成覆核"),
                    ),
                    evidence_refs=[EvidenceReference(
                        check_id=_v4_check_id(title),
                        node=str(report_item.get("node") or "all-nodes"),
                        evidence_sha256=digest,
                    )],
                    evidence_snapshot=evidence_snapshot,
                    trace=RuleTrace(
                        rule_id="report.v4.visible_section.v1",
                        rule_version=ruleset_version,
                    ),
                    media=media,
                ))
    return SectionWorkflowDocument(ruleset_version=ruleset_version, items=items)


def apply_workflow_to_v4_report(v4_report: dict, workflow: SectionWorkflowDocument) -> dict:
    """Overlay delivery-selected narratives onto the exact V4 items only."""
    updated = json.loads(json.dumps(v4_report, ensure_ascii=False))
    by_key = {item.section_key: item for item in workflow.items}
    for chapter in updated.get("chapters", []):
        for section in chapter.get("sections", []):
            for ordinal, report_item in enumerate(section.get("items", [])):
                key = _v4_section_key(
                    str(section["number"]), ordinal, str(report_item.get("title") or "Report Section")
                )
                item = by_key.get(key)
                if item is None:
                    continue
                narrative = narrative_for_render(
                    item, renderer_uses_ai=workflow.renderer_uses_ai
                )
                report_item["observation"] = narrative.observation
                report_item["recommendation"] = narrative.recommendation
    return updated


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
    """Attach an untrusted AI draft without changing facts or approval state."""

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
    """Overlay delivery-selected prose; facts and rule status stay deterministic."""

    by_key = {item.section_key: item for item in workflow.items}
    updated = []
    for item in assessment.assessments:
        key = f"{item.section_id}:{item.node}:{item.check_id}"
        workflow_item = by_key.get(key)
        narrative = (
            narrative_for_render(
                workflow_item, renderer_uses_ai=workflow.renderer_uses_ai
            )
            if workflow_item is not None else None
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
