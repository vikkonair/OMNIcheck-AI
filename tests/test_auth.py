from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, update

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.auth import AuthStore, hash_password, users, verify_password
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.web import create_app


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/golden/jiuxing_v4"


def _config() -> dict:
    import yaml
    return yaml.safe_load((FIXTURE / "job.yaml").read_text(encoding="utf-8"))


def _secured_app(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'm11.db'}"
    metadata_store = DatabaseMetadataStore(database_url)
    metadata_store.create_schema_for_test()
    auth = AuthStore(engine=metadata_store.engine)
    application = ApplicationDataStore(engine=metadata_store.engine)
    customer_a = application.create_customer(tenant_key="customer-a", name="Customer A")
    system_a = application.create_system(customer_a["customer_id"], system_key="prod", name="Prod", environment="production")
    customer_b = application.create_customer(tenant_key="customer-b", name="Customer B")
    system_b = application.create_system(customer_b["customer_id"], system_key="prod", name="Prod", environment="production")
    engineer = auth.create_user(username="engineer", display_name="Engineer", password="correct-horse-123")
    auth.grant_customer(engineer["user_id"], customer_a["customer_id"], "engineer")
    viewer = auth.create_user(username="viewer", display_name="Viewer", password="correct-horse-456")
    auth.grant_customer(viewer["user_id"], customer_a["customer_id"], "viewer")
    admin = auth.create_user(username="admin", display_name="Admin", password="correct-horse-789", platform_role="platform_admin")
    app = create_app(data_root=tmp_path / "jobs", metadata_store=metadata_store,
                     auth_store=auth, auth_required=True)
    return TestClient(app), auth, (customer_a, system_a), (customer_b, system_b)


def _login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct-horse-123")
    second = hash_password("correct-horse-123")
    assert first != second
    assert verify_password("correct-horse-123", first)
    assert not verify_password("wrong-password", first)


def test_m11_schema_contains_identity_rbac_session_and_audit_tables(tmp_path: Path) -> None:
    _, auth, _, _ = _secured_app(tmp_path)
    assert {"users", "customer_memberships", "user_sessions", "audit_events"} <= set(
        inspect(auth.engine).get_table_names()
    )


def test_authentication_is_required_and_failed_login_is_audited(tmp_path: Path) -> None:
    client, auth, _, _ = _secured_app(tmp_path)
    assert client.get("/api/jobs").status_code == 401
    assert client.post("/api/auth/login", json={"username": "engineer", "password": "wrong"}).status_code == 401
    _login(client, "admin", "correct-horse-789")
    events = client.get("/api/audit-events").json()
    assert {event["outcome"] for event in events if event["action"] == "auth.login"} == {"failed", "success"}


def test_engineer_can_only_create_and_read_authorized_customer_jobs(tmp_path: Path) -> None:
    client, auth, tenant_a, tenant_b = _secured_app(tmp_path)
    _login(client, "engineer", "correct-horse-123")
    customer_a, system_a = tenant_a
    customer_b, system_b = tenant_b

    allowed = client.post(
        f"/api/jobs?customer_id={customer_a['customer_id']}&system_id={system_a['system_id']}",
        json=_config(),
    )
    assert allowed.status_code == 201
    assert allowed.json()["customer_id"] == customer_a["customer_id"]

    denied = client.post(
        f"/api/jobs?customer_id={customer_b['customer_id']}&system_id={system_b['system_id']}",
        json=_config(),
    )
    assert denied.status_code == 403
    jobs = client.get("/api/jobs").json()
    assert [job["job_id"] for job in jobs] == [allowed.json()["job_id"]]


def test_viewer_is_read_only_and_logout_revokes_session(tmp_path: Path) -> None:
    client, auth, tenant_a, _ = _secured_app(tmp_path)
    _login(client, "viewer", "correct-horse-456")
    customer, system = tenant_a
    denied = client.post(
        f"/api/jobs?customer_id={customer['customer_id']}&system_id={system['system_id']}",
        json=_config(),
    )
    assert denied.status_code == 403
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_platform_admin_can_access_legacy_unscoped_jobs(tmp_path: Path) -> None:
    client, auth, _, _ = _secured_app(tmp_path)
    legacy = client.app.state.job_store.create(type("Config", (), {
        "customer": "Legacy", "system_name": None, "period": "2026-H1",
        "product": "PostgreSQL", "model_dump": lambda self, **kwargs: _config(),
    })())
    _login(client, "admin", "correct-horse-789")
    assert client.get(f"/api/jobs/{legacy['job_id']}").status_code == 200


def test_cross_site_state_change_is_denied(tmp_path: Path) -> None:
    client, _, _, _ = _secured_app(tmp_path)
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"username": "admin", "password": "correct-horse-789"},
    )
    assert response.status_code == 403
    assert response.headers["x-frame-options"] == "DENY"


def test_disabling_user_invalidates_existing_session(tmp_path: Path) -> None:
    client, auth, _, _ = _secured_app(tmp_path)
    _login(client, "engineer", "correct-horse-123")
    assert client.get("/api/auth/me").status_code == 200
    with auth.engine.begin() as connection:
        connection.execute(update(users).where(users.c.username == "engineer").values(active=False))
    assert client.get("/api/auth/me").status_code == 401


def test_reviewer_audit_is_limited_to_authorized_customers(tmp_path: Path) -> None:
    client, auth, tenant_a, tenant_b = _secured_app(tmp_path)
    reviewer = auth.create_user(username="reviewer", display_name="Reviewer", password="correct-horse-999")
    auth.grant_customer(reviewer["user_id"], tenant_a[0]["customer_id"], "reviewer")
    auth.audit(action="test.a", outcome="success", request_id="a" * 32,
               customer_id=tenant_a[0]["customer_id"])
    auth.audit(action="test.b", outcome="success", request_id="b" * 32,
               customer_id=tenant_b[0]["customer_id"])
    _login(client, "reviewer", "correct-horse-999")
    events = client.get("/api/audit-events").json()
    assert "test.a" in {event["action"] for event in events}
    assert "test.b" not in {event["action"] for event in events}
