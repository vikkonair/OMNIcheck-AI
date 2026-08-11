from __future__ import annotations

from pathlib import Path

import pytest

from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.section_persistence import (
    SectionRevisionConflictError,
    SectionWorkflowStore,
)
from omni_healthcheck.section_workflow import build_section_workflow
from test_section_workflow import assessment_document


def stores(tmp_path: Path) -> tuple[DatabaseMetadataStore, SectionWorkflowStore, str]:
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'sections.db'}")
    metadata.create_schema_for_test()
    job_id = "a" * 32
    metadata.create({
        "job_id": job_id,
        "customer": "測試客戶",
        "system_name": "測試系統",
        "period": "2026-H2",
        "product": "EPAS",
        "status": "succeeded",
        "error": None,
        "input_files": 1,
    })
    return metadata, SectionWorkflowStore(engine=metadata.engine), job_id


def test_persists_all_versions_and_allows_no_ai_review(tmp_path: Path) -> None:
    _, store, job_id = stores(tmp_path)
    baseline = build_section_workflow(assessment_document())
    assert store.persist_baseline(job_id, baseline)["created"] is True
    assert store.persist_baseline(job_id, baseline)["created"] is False

    item = store.list_items(job_id)[0]
    reviewed = store.transition(
        job_id, item["item_id"], expected_revision=1, action="reviewed",
        actor="engineer-a", observation="人工觀察", recommendation="人工建議",
    )
    assert reviewed["revision"] == 2
    assert reviewed["ai_draft"] is None
    approved = store.transition(
        job_id, item["item_id"], expected_revision=2, action="approved",
        actor="reviewer-a",
    )
    assert approved["selected_source"] == "approved"
    assert store.document(job_id).items[0].selected_narrative.observation == "人工觀察"
    assert [row["action"] for row in store.revisions(job_id, item["item_id"])] == [
        "generated", "reviewed", "approved"
    ]


def test_rejects_stale_section_revision(tmp_path: Path) -> None:
    _, store, job_id = stores(tmp_path)
    store.persist_baseline(job_id, build_section_workflow(assessment_document()))
    item = store.list_items(job_id)[0]
    store.transition(
        job_id, item["item_id"], expected_revision=1, action="ai_drafted",
        actor="gateway", observation="draft", recommendation="draft",
    )
    with pytest.raises(SectionRevisionConflictError):
        store.transition(
            job_id, item["item_id"], expected_revision=1, action="reviewed",
            actor="engineer", observation="review", recommendation="review",
        )
