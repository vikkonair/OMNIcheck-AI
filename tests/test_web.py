import json
from pathlib import Path

from fastapi.testclient import TestClient

from omni_healthcheck.web import create_app


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
    assert "建立案件並開始健檢" in page.text
    assert "webkitdirectory" in page.text
    assert "id=\"nodes\"" in page.text
    assert "textarea" not in page.text

    options = client.get("/api/config-options")
    assert options.status_code == 200
    body = options.json()
    assert body["roles"] == ["Primary", "Standby", "DR", "Witness"]
    services = {service["name"]: service for service in body["services"]}
    assert {"PEM", "EFM", "XDB", "pgBackRest", "Barman"} <= services.keys()
    assert services["PEM"]["allowed_roles"] == ["Witness"]
    assert services["XDB"]["allowed_roles"] == ["Witness"]
