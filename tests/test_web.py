import json
from pathlib import Path

from fastapi.testclient import TestClient

from omni_healthcheck.web import create_app
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.section_persistence import SectionWorkflowStore
from omni_healthcheck.section_workflow import build_section_workflow
from omni_healthcheck.ai_gateway import AIGatewaySettings, OllamaGateway
from omni_healthcheck.ai_persistence import AIGatewayAuditStore
from test_section_workflow import assessment_document


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/golden/jiuxing_v4"


def _config() -> dict:
    import yaml

    return yaml.safe_load((FIXTURE / "job.yaml").read_text(encoding="utf-8"))


def test_web_job_lifecycle_runs_existing_pipeline(tmp_path: Path) -> None:
    app = create_app(
        data_root=tmp_path / "jobs",
        rules_path=ROOT / "config/rules.default.yaml",
    )
    client = TestClient(app)

    assert client.get("/api/health").json()["status"] == "ok"
    created = client.post("/api/jobs", json=_config())
    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "draft"

    files = []
    for path in sorted((FIXTURE / "input").rglob("*")):
        if path.is_file():
            files.append(
                (
                    "files",
                    (
                        path.relative_to(FIXTURE / "input").as_posix(),
                        path.read_bytes(),
                        "application/octet-stream",
                    ),
                )
            )
    uploaded = client.post(f"/api/jobs/{job['job_id']}/files", files=files)
    assert uploaded.status_code == 201
    assert len(uploaded.json()["files"]) == 3

    started = client.post(f"/api/jobs/{job['job_id']}/run")
    assert started.status_code == 202

    completed = client.get(f"/api/jobs/{job['job_id']}").json()
    assert completed["status"] == "succeeded"
    output_names = {item["name"] for item in completed["outputs"]}
    assert {
        "inventory.json",
        "normalized.json",
        "qa-result.json",
        "v4-report.json",
        "v4-qa-result.json",
    } <= output_names
    assert "report.pdf" not in output_names

    qa = client.get(
        f"/api/jobs/{job['job_id']}/outputs/qa-result.json"
    )
    assert qa.status_code == 200
    assert json.loads(qa.content)["delivery_allowed"] is True


def test_web_rejects_path_traversal_and_empty_run(tmp_path: Path) -> None:
    app = create_app(
        data_root=tmp_path / "jobs",
        rules_path=ROOT / "config/rules.default.yaml",
    )
    client = TestClient(app)
    job_id = client.post("/api/jobs", json=_config()).json()["job_id"]

    empty_run = client.post(f"/api/jobs/{job_id}/run")
    assert empty_run.status_code == 409

    traversal = client.post(
        f"/api/jobs/{job_id}/files",
        files={"files": ("../escape.txt", b"unsafe", "text/plain")},
    )
    assert traversal.status_code == 400
    assert not (tmp_path / "escape.txt").exists()

    mixed = client.post(
        f"/api/jobs/{job_id}/files",
        files=[
            ("files", ("valid.txt", b"must not persist", "text/plain")),
            ("files", ("../escape.txt", b"unsafe", "text/plain")),
        ],
    )
    assert mixed.status_code == 400
    assert client.get(f"/api/jobs/{job_id}").json()["input_files"] == 0


def test_web_validates_job_configuration(tmp_path: Path) -> None:
    app = create_app(data_root=tmp_path / "jobs")
    client = TestClient(app)
    invalid = _config()
    invalid["nodes"].append(
        {"hostname": "second-primary", "role": "Primary", "services": []}
    )

    response = client.post("/api/jobs", json=invalid)

    assert response.status_code == 422
    assert client.get("/api/jobs").json() == []


def test_web_ui_exposes_guided_workflow_and_registry_options(tmp_path: Path) -> None:
    client = TestClient(create_app(data_root=tmp_path / "jobs"))

    page = client.get("/")
    assert page.status_code == 200
    assert 'content="integrated-v1"' in page.text
    assert "OMNIcheck HealthCheck Studio" in page.text
    assert "M10.3.1 Pipeline" in page.text
    assert 'href="/classic"' in page.text
    assert "/knowledge" not in page.text
    assert "GPDB" not in page.text
    assert "建立案件並開始健檢" in page.text
    assert "webkitdirectory" in page.text
    assert "id=\"nodes\"" in page.text
    assert "分析節點架構" in page.text
    assert "topologyConfirmed" in page.text
    assert "Database Output 來源確認" in page.text
    assert "evidence_mappings" in page.text
    assert "if (discoveredNodes.length) state.nodes=discoveredNodes" in page.text
    assert "請選擇來源節點" in page.text
    assert "updateConfirmationAvailability" in page.text
    assert "exactlyOnePrimary" in page.text
    assert "Section 審核工作台" in page.text
    assert "review-observation" in page.text
    assert "/ai-draft-batches" in page.text
    assert "依核准內容重新產報" in page.text

    options = client.get("/api/config-options")
    assert options.status_code == 200
    body = options.json()
    assert body["roles"] == ["Primary", "Standby", "DR", "Witness"]
    services = {service["name"]: service for service in body["services"]}
    assert {"PEM", "EFM", "XDB", "pgBackRest", "Barman"} <= services.keys()
    assert services["PEM"]["allowed_roles"] == ["Witness"]
    assert services["XDB"]["allowed_roles"] == ["Witness"]

    integrated = client.get("/integrated")
    classic = client.get("/classic")
    assert integrated.status_code == 200
    assert integrated.text == page.text
    assert classic.status_code == 200
    assert 'content="integrated-v1"' not in classic.text
    assert "OMNIcheck AI" in classic.text


def test_web_discovers_topology_without_persisting_samples(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    client = TestClient(create_app(data_root=jobs))

    response = client.post(
        "/api/topology/discover",
        files=[
            (
                "files",
                (
                    "os/HealthChekOS-LOG-db01-20260616.txt",
                    b"db.user=efm\nbind.address=efm1-primary:7800",
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "os/HealthChekOS-LOG-db02-20260616.txt",
                    b"db.user=efm\nbind.address=efm2-standby:7800",
                    "text/plain",
                ),
            ),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmation_required"] is True
    assert body["can_confirm"] is True
    assert [node["suggested_role"] for node in body["nodes"]] == [
        "Primary",
        "Standby",
    ]
    assert list(jobs.iterdir()) == []


def test_section_review_api_requires_revision_and_approval(tmp_path: Path) -> None:
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'api.db'}")
    metadata.create_schema_for_test()
    app = create_app(data_root=tmp_path / "jobs", metadata_store=metadata)
    client = TestClient(app)
    job_id = client.post("/api/jobs", json=_config()).json()["job_id"]
    section_store = SectionWorkflowStore(engine=metadata.engine)
    section_store.persist_baseline(job_id, build_section_workflow(assessment_document()))

    item = client.get(f"/api/jobs/{job_id}/sections").json()[0]
    reviewed = client.post(
        f"/api/jobs/{job_id}/sections/{item['item_id']}/review",
        json={
            "expected_revision": 1,
            "actor": "engineer-a",
            "observation": "人工確認觀察",
            "recommendation": "人工確認建議",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["selected_source"] == "deterministic_template"

    stale = client.post(
        f"/api/jobs/{job_id}/sections/{item['item_id']}/approve",
        json={"expected_revision": 1, "actor": "reviewer-a"},
    )
    assert stale.status_code == 409
    approved = client.post(
        f"/api/jobs/{job_id}/sections/{item['item_id']}/approve",
        json={"expected_revision": 2, "actor": "reviewer-a"},
    )
    assert approved.status_code == 200
    assert approved.json()["selected_source"] == "approved"
    revisions = client.get(
        f"/api/jobs/{job_id}/sections/{item['item_id']}/revisions"
    )
    assert [entry["action"] for entry in revisions.json()] == [
        "generated", "reviewed", "approved"
    ]


def test_ai_gateway_api_saves_untrusted_draft_but_does_not_select_it(
    tmp_path: Path,
) -> None:
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'ai-api.db'}")
    metadata.create_schema_for_test()
    audit = AIGatewayAuditStore(engine=metadata.engine)

    def transport(*_args):
        return {
            "model": "gpt-oss:20b",
            "choices": [{
                "message": {"content": json.dumps({
                    "observation": "AI 草稿觀察。\n結論：仍需人工確認。",
                    "recommendation": "請由工程師檢視證據後核准。",
                }, ensure_ascii=False)},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 42},
        }

    gateway = OllamaGateway(
        AIGatewaySettings(
            enabled=True,
            endpoint="http://ollama.internal:11434/v1/chat/completions",
            model="gpt-oss:20b",
            timeout_seconds=10,
            max_attempts=1,
        ),
        audit,
        transport=transport,
    )
    app = create_app(
        data_root=tmp_path / "jobs", metadata_store=metadata,
        ai_gateway=gateway,
    )
    client = TestClient(app)
    job_id = client.post("/api/jobs", json=_config()).json()["job_id"]
    sections = SectionWorkflowStore(engine=metadata.engine)
    sections.persist_baseline(job_id, build_section_workflow(assessment_document()))
    item = client.get(f"/api/jobs/{job_id}/sections").json()[0]

    response = client.post(
        f"/api/jobs/{job_id}/sections/{item['item_id']}/generate-ai-draft",
        json={"expected_revision": 1, "actor": "engineer-a"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ai_drafted"
    assert body["item"]["revision"] == 2
    assert body["item"]["selected_source"] == "deterministic_template"
    assert body["item"]["ai_draft"]["observation"].startswith("AI 草稿")
    assert client.get("/api/health").json()["ai_gateway"] == "enabled"
    audit_rows = client.get(f"/api/jobs/{job_id}/ai-audit").json()
    assert audit_rows[0]["status"] == "succeeded"
    assert audit_rows[0]["model"] == "gpt-oss:20b"


def test_ai_batch_api_queues_and_worker_generates_sequential_drafts(tmp_path: Path) -> None:
    from omni_healthcheck.ai_batch import AIDraftBatchStore
    from omni_healthcheck.worker import run_ai_batch_once

    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'ai-batch.db'}")
    metadata.create_schema_for_test()
    audit = AIGatewayAuditStore(engine=metadata.engine)
    calls = []

    def transport(_endpoint, payload, _headers, _timeout):
        calls.append(payload)
        return {
            "model": "gpt-oss:20b",
            "choices": [{"message": {"content": json.dumps({
                "observation": "受控批次草稿。\n結論：仍須工程師審核。",
                "recommendation": "確認證據後再核准。",
            }, ensure_ascii=False)}, "finish_reason": "stop"}],
        }

    gateway = OllamaGateway(AIGatewaySettings(
        enabled=True, endpoint="http://ollama.internal:11434/v1/chat/completions",
        model="gpt-oss:20b", timeout_seconds=10, max_attempts=1,
    ), audit, transport=transport)
    client = TestClient(create_app(
        data_root=tmp_path / "jobs", metadata_store=metadata, ai_gateway=gateway,
    ))
    job_id = client.post("/api/jobs", json=_config()).json()["job_id"]
    sections = SectionWorkflowStore(engine=metadata.engine)
    workflow = build_section_workflow(assessment_document())
    second = workflow.items[0].model_copy(update={
        "section_key": "4.2:primary:second-check", "section_id": "4.2",
        "check_id": "second-check",
    }, deep=True)
    workflow = workflow.model_copy(update={"items": [*workflow.items, second]}, deep=True)
    sections.persist_baseline(job_id, workflow)
    candidates = client.get(f"/api/jobs/{job_id}/sections").json()[:2]
    response = client.post(f"/api/jobs/{job_id}/ai-draft-batches", json={
        "actor": "engineer-a",
        "items": [{"item_id": item["item_id"], "expected_revision": item["revision"]} for item in candidates],
    })
    assert response.status_code == 202
    batch_id = response.json()["batch_id"]
    assert response.json()["status"] == "queued"

    batch_store = AIDraftBatchStore(engine=metadata.engine, max_items=5)
    assert run_ai_batch_once(
        batch_store, sections, gateway, "test-ai-worker", min_interval_seconds=0,
    ) is True
    completed = client.get(f"/api/jobs/{job_id}/ai-draft-batches/{batch_id}").json()
    assert completed["status"] == "completed"
    assert completed["succeeded_items"] == 2
    assert len(calls) == 2
    updated = client.get(f"/api/jobs/{job_id}/sections").json()[:2]
    assert all(item["workflow_status"] == "ai_drafted" for item in updated)
    assert all(item["selected_source"] == "deterministic_template" for item in updated)


def test_ai_batch_rejects_disabled_gateway_and_stale_revision(tmp_path: Path) -> None:
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'ai-disabled.db'}")
    metadata.create_schema_for_test()
    job_client = TestClient(create_app(data_root=tmp_path / "jobs", metadata_store=metadata))
    job_id = job_client.post("/api/jobs", json=_config()).json()["job_id"]
    sections = SectionWorkflowStore(engine=metadata.engine)
    sections.persist_baseline(job_id, build_section_workflow(assessment_document()))
    item = job_client.get(f"/api/jobs/{job_id}/sections").json()[0]
    response = job_client.post(f"/api/jobs/{job_id}/ai-draft-batches", json={
        "actor": "engineer", "items": [{"item_id": item["item_id"], "expected_revision": 1}],
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "AI Gateway is disabled"
