from fastapi.testclient import TestClient

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.auth import AuthStore
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.web import create_app


def _config() -> dict:
    return {
        "customer": "授權客戶", "system_name": "production-db", "period": "2026-H2",
        "product": "EPAS", "engineer": "XXX", "first_healthcheck": True,
        "nodes": [{"hostname": "db1", "role": "Primary", "services": []}],
        "scope": {"include_os_from_all_nodes": True, "database_primary_only": True},
        "report": {"template": "omni-v4", "output_docx": True, "output_pdf": True},
        "ai": {"enabled": False, "provider": "disabled"},
        "topology_confirmation": {
            "source": "deterministic_discovery", "confirmed": True,
            "discovery_schema_version": "1.0",
            "nodes": [{"hostname": "db1", "suggested_role": "Primary", "confidence": "high", "role_evidence": [], "conflicts": []}],
        },
    }


def test_auth_enabled_requires_login_and_enforces_customer_scope(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OMNICHECK_AUTH_ENABLED", "true")
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'auth.db'}")
    metadata.create_schema_for_test()
    app_data = ApplicationDataStore(engine=metadata.engine)
    customer = app_data.create_customer(tenant_key="authorized", name="授權客戶")
    app_data.create_system(customer["customer_id"], system_key="production-db", name="production-db", environment="production", product="EPAS")
    auth = AuthStore(engine=metadata.engine, enabled=True)
    engineer = auth.create_user(username="engineer", display_name="工程師", password="correct-horse-battery")
    auth.grant(user_id=engineer["user_id"], customer_id=customer["customer_id"], role="engineer")
    app = create_app(data_root=tmp_path / "jobs", metadata_store=metadata)
    client = TestClient(app)

    assert client.get("/api/jobs").status_code == 401
    denied = client.post("/api/auth/login", json={"username": "engineer", "password": "wrong-password"})
    assert denied.status_code == 401
    login = client.post("/api/auth/login", json={"username": "engineer", "password": "correct-horse-battery"})
    assert login.status_code == 200
    csrf = client.cookies.get("omnicheck_csrf")
    assert client.get("/api/auth/me").json()["username"] == "engineer"
    assert client.get("/api/auth/scope").json()[0]["system_name"] == "production-db"

    created = client.post("/api/jobs", json=_config(), headers={"X-OMNI-CSRF": csrf})
    assert created.status_code == 201, created.text
    assert created.json()["customer_id"] == customer["customer_id"]
    assert len(client.get("/api/jobs").json()) == 1

    legacy = metadata.create({**created.json(), "job_id": "a" * 32, "customer_id": None, "system_id": None, "status": "draft"})
    (tmp_path / "jobs" / legacy["job_id"]).mkdir()
    assert client.get("/api/jobs").json()[0]["job_id"] == created.json()["job_id"]


def test_auth_bootstrap_only_allows_first_platform_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OMNICHECK_AUTH_ENABLED", "true")
    monkeypatch.setenv("OMNICHECK_AUTH_BOOTSTRAP_TOKEN", "a" * 32)
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    metadata.create_schema_for_test()
    client = TestClient(create_app(data_root=tmp_path / "jobs", metadata_store=metadata))
    body = {"username": "admin", "display_name": "管理者", "password": "correct-horse-battery", "bootstrap_token": "a" * 32}
    created = client.post("/api/auth/bootstrap", json=body)
    assert created.status_code == 201
    assert created.json()["platform_role"] == "platform_admin"
    assert client.post("/api/auth/bootstrap", json=body).status_code == 409


def test_auth_password_length_can_only_be_lowered_by_explicit_environment(monkeypatch) -> None:
    from omni_healthcheck.auth import hash_password, verify_password

    monkeypatch.delenv("OMNICHECK_AUTH_MIN_PASSWORD_LENGTH", raising=False)
    try:
        hash_password("victor")
    except ValueError as exc:
        assert "12" in str(exc)
    else:
        raise AssertionError("default password policy must remain at least 12 characters")
    monkeypatch.setenv("OMNICHECK_AUTH_MIN_PASSWORD_LENGTH", "1")
    assert verify_password("victor", hash_password("victor"))
