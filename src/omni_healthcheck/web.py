"""M9 FastAPI application for local job creation and pipeline execution."""

from __future__ import annotations

import os
import json
from uuid import uuid4
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from omni_healthcheck.ai_gateway import AIGatewaySettings, OllamaGateway
from omni_healthcheck.ai_batch import AIDraftBatchStore
from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.auth import AuthStore, CURRENT_PRINCIPAL, Principal
from omni_healthcheck.ai_persistence import AIGatewayAuditStore
from omni_healthcheck.cli import run_generate
from omni_healthcheck.config import JobConfig
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import (
    JobNotFoundError,
    JobStore,
    UnsafeUploadPathError,
)
from omni_healthcheck.services import SERVICE_REGISTRY
from omni_healthcheck.section_persistence import (
    SectionRevisionConflictError,
    SectionWorkflowStore,
)
from omni_healthcheck.topology_discovery import DiscoveryEvidence, discover_topology
from omni_healthcheck.web_ui import INDEX_HTML
from omni_healthcheck.web_ui_integrated import INTEGRATED_INDEX_HTML


class SectionTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=128)
    observation: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class SectionApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=128)


class BulkSectionApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=128)


class SectionAIDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=128)


class SectionAIBatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(min_length=1, max_length=32)
    expected_revision: int = Field(ge=1)


class SectionAIBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=128)
    items: list[SectionAIBatchItem]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class BootstrapRequest(LoginRequest):
    display_name: str = Field(min_length=1, max_length=256)
    bootstrap_token: str = Field(min_length=16, max_length=512)


class UserCreateRequest(LoginRequest):
    display_name: str = Field(min_length=1, max_length=256)
    platform_admin: bool = False


class MembershipGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=32, max_length=32)
    customer_id: str = Field(min_length=32, max_length=32)
    role: str = Field(pattern="^(engineer|reviewer|viewer)$")


LOGIN_HTML = """<!doctype html><html lang=\"zh-Hant\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>登入｜OMNIcheck AI</title><style>body{font-family:Arial,'Noto Sans TC',sans-serif;background:#eef5fb;color:#18324b;display:grid;place-items:center;min-height:100vh;margin:0}.box{background:#fff;padding:36px;border-radius:10px;width:min(390px,calc(100% - 40px));box-shadow:0 10px 30px #12345622}h1{margin:0 0 8px;color:#075bab}p{color:#617287}label{display:block;margin-top:16px;font-size:14px}input{width:100%;box-sizing:border-box;margin-top:6px;padding:11px;border:1px solid #b9c9d7;border-radius:5px;font:inherit}button{margin-top:22px;width:100%;padding:11px;background:#0879df;border:0;border-radius:5px;color:white;font-weight:bold;font:inherit}.message{margin-top:14px;color:#b42318;white-space:pre-wrap}</style><main class=\"box\"><h1>OMNIcheck AI</h1><p>請登入後存取案件與報告。</p><form id=\"login\"><label>帳號<input id=\"username\" autocomplete=\"username\" required></label><label>密碼<input id=\"password\" type=\"password\" autocomplete=\"current-password\" required></label><button>登入</button></form><div id=\"message\" class=\"message\"></div></main><script>document.querySelector('#login').addEventListener('submit',async e=>{e.preventDefault();const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,password:password.value})});if(!r.ok){message.textContent=(await r.json()).detail||'登入失敗';return}location.href='/integrated'})</script></html>"""


def _default_data_root() -> Path:
    return Path(os.environ.get("OMNICHECK_DATA_ROOT", "data/jobs"))


def _default_rules_path() -> Path:
    return Path(os.environ.get("OMNICHECK_RULES_PATH", "config/rules.default.yaml"))


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or uuid4().hex


def _run_job(store: JobStore, job_id: str, rules_path: Path) -> None:
    store.update(job_id, status="running", error=None)
    paths = store.paths(job_id)
    try:
        run_generate(
            paths["job"],
            paths["input"],
            paths["output"],
            rules_path,
        )
    except Exception as exc:  # Status must retain deterministic gate failures.
        store.update(job_id, status="failed", error=str(exc))
    else:
        store.update(job_id, status="succeeded", error=None)


def create_app(
    *,
    data_root: Path | None = None,
    rules_path: Path | None = None,
    database_url: str | None = None,
    metadata_store: object | None = None,
    ai_gateway: object | None = None,
) -> FastAPI:
    selected_database_url = database_url or os.environ.get("OMNICHECK_DATABASE_URL")
    selected_metadata_store = metadata_store
    if selected_metadata_store is None and selected_database_url:
        selected_metadata_store = DatabaseMetadataStore(selected_database_url)
    store = JobStore(
        data_root or _default_data_root(),
        metadata_store=selected_metadata_store,
    )
    selected_rules = (rules_path or _default_rules_path()).resolve()
    app = FastAPI(title="OMNIcheck AI", version="0.9.0")
    app.state.job_store = store
    auth_store = (
        AuthStore(engine=selected_metadata_store.engine)
        if selected_metadata_store is not None and getattr(selected_metadata_store, "engine", None) is not None
        else None
    )
    application_store = (
        ApplicationDataStore(engine=selected_metadata_store.engine)
        if selected_metadata_store is not None and getattr(selected_metadata_store, "engine", None) is not None
        else None
    )
    app.state.auth_store = auth_store
    section_store = (
        SectionWorkflowStore(engine=selected_metadata_store.engine)
        if selected_metadata_store is not None
        and getattr(selected_metadata_store, "engine", None) is not None
        else None
    )
    ai_audit_store = (
        AIGatewayAuditStore(engine=selected_metadata_store.engine)
        if selected_metadata_store is not None
        and getattr(selected_metadata_store, "engine", None) is not None
        else None
    )
    ai_batch_store = (
        AIDraftBatchStore(
            engine=selected_metadata_store.engine,
            max_items=int(os.environ.get("OMNICHECK_AI_BATCH_MAX_ITEMS", "5")),
        )
        if selected_metadata_store is not None
        and getattr(selected_metadata_store, "engine", None) is not None
        else None
    )
    selected_ai_gateway = ai_gateway
    if selected_ai_gateway is None and ai_audit_store is not None:
        selected_ai_gateway = OllamaGateway(
            AIGatewaySettings.from_env(), ai_audit_store
        )

    @app.middleware("http")
    async def authentication_gate(request: Request, call_next):
        if auth_store is None or not auth_store.enabled:
            return await call_next(request)
        path = request.url.path
        if path in {"/api/health", "/api/auth/login", "/api/auth/bootstrap", "/login"}:
            return await call_next(request)
        authorization = request.headers.get("Authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else request.cookies.get("omnicheck_session")
        principal = auth_store.principal_for_token(token)
        if principal is None:
            if path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"detail": "authentication required"})
            return RedirectResponse("/login", status_code=303)
        if path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and not authorization:
            if not request.headers.get("X-OMNI-CSRF") or request.headers.get("X-OMNI-CSRF") != request.cookies.get("omnicheck_csrf"):
                return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
        marker = CURRENT_PRINCIPAL.set(principal)
        try:
            return await call_next(request)
        finally:
            CURRENT_PRINCIPAL.reset(marker)

    def sections_or_503() -> SectionWorkflowStore:
        if section_store is None:
            raise HTTPException(
                status_code=503,
                detail="Section Workflow persistence requires EDB metadata",
            )
        return section_store

    def ai_batches_or_503() -> AIDraftBatchStore:
        if ai_batch_store is None:
            raise HTTPException(status_code=503, detail="AI batch queue requires EDB metadata")
        return ai_batch_store

    def principal_or_401() -> Principal:
        principal = CURRENT_PRINCIPAL.get()
        if auth_store is not None and auth_store.enabled and principal is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return principal or Principal("internal", "internal", "internal", "platform_admin")

    def job_or_404(job_id: str, minimum: str = "viewer") -> dict:
        try:
            job = store.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        if auth_store is not None and auth_store.enabled:
            try:
                auth_store.require_job(principal_or_401(), job, minimum)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="job access is not authorized") from exc
        return job

    @app.get("/login", response_class=HTMLResponse)
    def login_page() -> str:
        return LOGIN_HTML if auth_store is not None and auth_store.enabled else "<p>登入功能尚未啟用。</p>"

    @app.post("/api/auth/bootstrap", status_code=201)
    def bootstrap_auth(body: BootstrapRequest, request: Request) -> dict:
        if auth_store is None:
            raise HTTPException(status_code=503, detail="authentication requires EDB metadata")
        expected = os.environ.get("OMNICHECK_AUTH_BOOTSTRAP_TOKEN")
        import hmac
        if not expected or not hmac.compare_digest(body.bootstrap_token, expected):
            raise HTTPException(status_code=403, detail="invalid bootstrap token")
        if auth_store.user_count():
            raise HTTPException(status_code=409, detail="bootstrap has already completed")
        try:
            user = auth_store.create_user(username=body.username, display_name=body.display_name, password=body.password, platform_admin=True)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        auth_store.audit(principal=None, action="auth.bootstrap", outcome="success", request_id=_request_id(request), details={"username": user["username"]})
        return {key: user[key] for key in ("user_id", "username", "display_name", "platform_role", "active")}

    @app.post("/api/auth/login")
    def login(body: LoginRequest, request: Request, response: Response) -> dict:
        if auth_store is None or not auth_store.enabled:
            raise HTTPException(status_code=404, detail="authentication is disabled")
        principal = auth_store.authenticate(body.username, body.password)
        if principal is None:
            auth_store.audit(principal=None, action="auth.login", outcome="denied", request_id=_request_id(request), client_ip=request.client.host if request.client else None, details={"username": body.username.strip().lower()})
            raise HTTPException(status_code=401, detail="invalid username or password")
        token, csrf = auth_store.issue_session(principal)
        secure = os.environ.get("OMNICHECK_AUTH_COOKIE_SECURE", "false").lower() == "true"
        response.set_cookie("omnicheck_session", token, httponly=True, samesite="strict", secure=secure, max_age=auth_store.session_hours * 3600)
        response.set_cookie("omnicheck_csrf", csrf, httponly=False, samesite="strict", secure=secure, max_age=auth_store.session_hours * 3600)
        auth_store.audit(principal=principal, action="auth.login", outcome="success", request_id=_request_id(request), client_ip=request.client.host if request.client else None)
        return {"username": principal.username, "display_name": principal.display_name, "platform_role": principal.platform_role}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict:
        if auth_store is not None:
            auth_store.revoke(request.cookies.get("omnicheck_session"))
        response.delete_cookie("omnicheck_session")
        response.delete_cookie("omnicheck_csrf")
        return {"status": "logged_out"}

    @app.get("/api/auth/me")
    def auth_me() -> dict:
        principal = principal_or_401()
        return {"user_id": principal.user_id, "username": principal.username, "display_name": principal.display_name, "platform_role": principal.platform_role, "auth_enabled": auth_store is not None and auth_store.enabled}

    @app.get("/api/auth/scope")
    def auth_scope() -> list[dict]:
        if auth_store is None:
            raise HTTPException(status_code=503, detail="authentication requires EDB metadata")
        return auth_store.scope(principal_or_401())

    def platform_admin_or_403() -> Principal:
        principal = principal_or_401()
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="platform administrator role is required")
        return principal

    @app.post("/api/admin/users", status_code=201)
    def create_user(body: UserCreateRequest, request: Request) -> dict:
        principal = platform_admin_or_403()
        if auth_store is None:
            raise HTTPException(status_code=503, detail="authentication requires EDB metadata")
        try:
            user = auth_store.create_user(username=body.username, display_name=body.display_name, password=body.password, platform_admin=body.platform_admin)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="unable to create user") from exc
        auth_store.audit(principal=principal, action="user.created", outcome="success", request_id=_request_id(request), details={"user_id": user["user_id"], "username": user["username"], "platform_admin": bool(user["platform_role"])})
        return {key: user[key] for key in ("user_id", "username", "display_name", "platform_role", "active")}

    @app.post("/api/admin/customer-memberships", status_code=201)
    def grant_customer_membership(body: MembershipGrantRequest, request: Request) -> dict:
        principal = platform_admin_or_403()
        if auth_store is None:
            raise HTTPException(status_code=503, detail="authentication requires EDB metadata")
        try:
            auth_store.grant(user_id=body.user_id, customer_id=body.customer_id, role=body.role)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="unable to grant customer membership") from exc
        auth_store.audit(principal=principal, action="membership.granted", outcome="success", request_id=_request_id(request), customer_id=body.customer_id, details={"user_id": body.user_id, "role": body.role})
        return {"user_id": body.user_id, "customer_id": body.customer_id, "role": body.role}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INTEGRATED_INDEX_HTML

    @app.get("/integrated", response_class=HTMLResponse)
    def integrated_index() -> str:
        return INTEGRATED_INDEX_HTML

    @app.get("/classic", response_class=HTMLResponse)
    def classic_index() -> str:
        return INDEX_HTML

    @app.get("/api/health")
    def health() -> dict:
        try:
            store.ping()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="metadata database unavailable",
            ) from exc
        return {
            "status": "ok",
            "service": "OMNIcheck AI",
            "metadata": "database" if store.database_backed else "filesystem",
            "worker": "external" if store.database_backed else "in_process",
            "ai_gateway": (
                "enabled"
                if selected_ai_gateway is not None
                and getattr(
                    getattr(selected_ai_gateway, "settings", None),
                    "enabled", False,
                )
                else "disabled"
            ),
        }

    @app.get("/api/config-options")
    def config_options() -> dict:
        return {
            "roles": ["Primary", "Standby", "DR", "Witness"],
            "products": ["PostgreSQL", "EPAS"],
            "services": [
                {
                    "name": definition.name,
                    "category": definition.category,
                    "allowed_roles": sorted(definition.allowed_roles or []),
                }
                for definition in SERVICE_REGISTRY.values()
            ],
        }

    @app.post("/api/jobs", status_code=201)
    def create_job(config: JobConfig) -> dict:
        customer_id = system_id = None
        if auth_store is not None and auth_store.enabled:
            principal = principal_or_401()
            try:
                customer_id, system_id = auth_store.resolve_scope(
                    principal, customer=config.customer, system_name=config.system_name
                )
                auth_store.require_customer(principal, customer_id, "engineer")
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="customer or system is not authorized") from exc
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        created = store.create(config)
        if customer_id and system_id and application_store is not None:
            application_store.associate_job(customer_id, system_id, created["job_id"])
            created = store.get(created["job_id"])
        return created

    @app.post("/api/topology/discover")
    def discover_uploaded_topology(files: list[UploadFile] = File(...)) -> dict:
        items = []
        for upload in files:
            filename = upload.filename or ""
            try:
                JobStore.safe_relative_path(filename)
            except UnsafeUploadPathError as exc:
                raise HTTPException(status_code=400, detail="unsafe upload path") from exc
            # Discovery samples text only. The immutable full upload still happens
            # once, after the operator confirms the proposed topology.
            items.append(
                DiscoveryEvidence(path=filename, content=upload.file.read(512 * 1024))
            )
        return discover_topology(items)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        values = store.list()
        if auth_store is None or not auth_store.enabled:
            return values
        principal = principal_or_401()
        result = []
        for job in values:
            try:
                auth_store.require_job(principal, job)
            except PermissionError:
                continue
            result.append(job)
        return result

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        metadata = job_or_404(job_id)
        outputs = store.outputs(job_id) if metadata["status"] == "succeeded" else []
        return {**metadata, "outputs": outputs}

    @app.post("/api/jobs/{job_id}/files", status_code=201)
    def upload_files(
        job_id: str,
        files: list[UploadFile] = File(...),
    ) -> dict:
        job_or_404(job_id, "engineer")
        saved = []
        try:
            store.validate_upload_batch(
                job_id,
                [upload.filename or "" for upload in files],
            )
            for upload in files:
                saved.append(
                    store.save_upload(
                        job_id,
                        upload.filename or "",
                        upload.file,
                    )
                )
        except UnsafeUploadPathError as exc:
            raise HTTPException(status_code=400, detail="unsafe upload path") from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"files": saved}

    @app.post("/api/jobs/{job_id}/run", status_code=202)
    def run_job(job_id: str, background: BackgroundTasks) -> dict:
        metadata = job_or_404(job_id, "engineer")
        if metadata["status"] not in {"draft", "failed"}:
            raise HTTPException(status_code=409, detail="job is already running or complete")
        if metadata["input_files"] == 0:
            raise HTTPException(status_code=409, detail="job has no input evidence")
        reset = {"attempts": 0} if store.database_backed and metadata["status"] == "failed" else {}
        store.update(job_id, status="queued", error=None, **reset)
        if not store.database_backed:
            background.add_task(_run_job, store, job_id, selected_rules)
        return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}/events")
    def list_job_events(job_id: str) -> list[dict]:
        job_or_404(job_id)
        return store.events(job_id)

    @app.get("/api/jobs/{job_id}/outputs")
    def list_outputs(job_id: str) -> list[dict]:
        metadata = job_or_404(job_id)
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        return store.outputs(job_id)

    @app.get("/api/jobs/{job_id}/execution-profile")
    def execution_profile(job_id: str) -> dict:
        metadata = job_or_404(job_id)
        if metadata["status"] not in {"succeeded", "failed"}:
            raise HTTPException(status_code=409, detail="execution profile is not ready")
        try:
            path = store.output_path(job_id, "execution-profile.json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="execution profile is unavailable") from exc
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/jobs/{job_id}/sections")
    def list_sections(job_id: str) -> list[dict]:
        job_or_404(job_id)
        try:
            return sections_or_503().list_items(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=409, detail="section workflow is not ready") from exc

    @app.get("/api/jobs/{job_id}/sections/{item_id}/revisions")
    def list_section_revisions(job_id: str, item_id: str) -> list[dict]:
        job_or_404(job_id)
        return sections_or_503().revisions(job_id, item_id)

    def transition_section(job_id: str, item_id: str, action: str, body) -> dict:
        job_or_404(job_id, "reviewer" if action == "approved" else "engineer")
        try:
            return sections_or_503().transition(
                job_id,
                item_id,
                expected_revision=body.expected_revision,
                action=action,
                actor=body.actor,
                observation=getattr(body, "observation", None),
                recommendation=getattr(body, "recommendation", None),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="section item not found") from exc
        except SectionRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/sections/{item_id}/ai-draft")
    def save_ai_draft(job_id: str, item_id: str, body: SectionTextRequest) -> dict:
        """Store an externally supplied draft; this endpoint never invokes AI."""
        return transition_section(job_id, item_id, "ai_drafted", body)

    @app.post("/api/jobs/{job_id}/sections/{item_id}/generate-ai-draft")
    def generate_ai_draft(
        job_id: str, item_id: str, body: SectionAIDraftRequest
    ) -> dict:
        job_or_404(job_id, "engineer")
        if selected_ai_gateway is None:
            return {
                "status": "disabled",
                "fallback": "deterministic_template",
                "detail": "AI Gateway requires EDB metadata",
            }
        try:
            item = sections_or_503().get_item(job_id, item_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="section item not found") from exc
        if item.revision != body.expected_revision:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"expected revision {body.expected_revision}, "
                    f"current revision is {item.revision}"
                ),
            )
        if item.workflow_status not in {"generated", "ai_drafted"}:
            raise HTTPException(
                status_code=409,
                detail="AI draft cannot replace reviewed or approved content",
            )
        result = selected_ai_gateway.generate(
            job_id=job_id, item_id=item_id, item=item,
            requested_by=body.actor,
        )
        if result.draft is None:
            return {
                "status": result.status,
                "request_id": result.request_id,
                "fallback": "deterministic_template",
                "detail": result.error,
            }
        try:
            saved = sections_or_503().transition(
                job_id, item_id, expected_revision=body.expected_revision,
                action="ai_drafted", actor=f"ai:ollama:{selected_ai_gateway.settings.model}",
                observation=result.draft.observation,
                recommendation=result.draft.recommendation,
            )
        except SectionRevisionConflictError as exc:
            if result.request_id:
                selected_ai_gateway.discard_stale(result.request_id)
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": "ai_drafted",
            "request_id": result.request_id,
            "item": saved,
        }

    @app.get("/api/jobs/{job_id}/ai-audit")
    def list_ai_audit(job_id: str) -> list[dict]:
        job_or_404(job_id)
        if ai_audit_store is None:
            raise HTTPException(
                status_code=503, detail="AI audit requires EDB metadata"
            )
        return ai_audit_store.list_for_job(job_id)

    @app.post("/api/jobs/{job_id}/ai-draft-batches", status_code=202)
    def create_ai_draft_batch(job_id: str, body: SectionAIBatchRequest) -> dict:
        job_or_404(job_id, "engineer")
        if selected_ai_gateway is None or not selected_ai_gateway.settings.enabled:
            raise HTTPException(status_code=409, detail="AI Gateway is disabled")
        try:
            return ai_batches_or_503().create(
                job_id, body.actor, [item.model_dump() for item in body.items]
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SectionRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/ai-draft-batches/{batch_id}")
    def get_ai_draft_batch(job_id: str, batch_id: str) -> dict:
        job_or_404(job_id)
        try:
            return ai_batches_or_503().get(job_id, batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="AI batch not found") from exc

    @app.post("/api/jobs/{job_id}/sections/{item_id}/review")
    def review_section(job_id: str, item_id: str, body: SectionTextRequest) -> dict:
        job_or_404(job_id, "engineer")
        return transition_section(job_id, item_id, "reviewed", body)

    @app.post("/api/jobs/{job_id}/sections/{item_id}/approve")
    def approve_section(job_id: str, item_id: str, body: SectionApprovalRequest) -> dict:
        job_or_404(job_id, "reviewer")
        return transition_section(job_id, item_id, "approved", body)

    @app.post("/api/jobs/{job_id}/sections/approve-all")
    def approve_all_sections(job_id: str, body: BulkSectionApprovalRequest) -> dict:
        metadata = job_or_404(job_id, "reviewer")
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        try:
            return sections_or_503().approve_all_ai_drafts(job_id, body.actor)
        except SectionRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/sections/render")
    def render_approved_sections(job_id: str) -> dict:
        metadata = job_or_404(job_id, "reviewer")
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        paths = store.paths(job_id)
        try:
            workflow = sections_or_503().document(job_id)
            run_generate(
                paths["job"], paths["input"], paths["output"], selected_rules,
                section_workflow_override=workflow,
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"approved render failed: {exc}") from exc
        return {
            "job_id": job_id,
            "status": "rendered",
            "policy": "approved_then_ai_draft_then_deterministic",
        }

    @app.get("/api/jobs/{job_id}/outputs/{filename}")
    def download_output(job_id: str, filename: str) -> FileResponse:
        metadata = job_or_404(job_id)
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        try:
            path = store.output_path(job_id, filename)
        except (FileNotFoundError, UnsafeUploadPathError) as exc:
            raise HTTPException(status_code=404, detail="output not found") from exc
        return FileResponse(path, filename=path.name)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "omni_healthcheck.web:app",
        host=os.environ.get("OMNICHECK_WEB_HOST", "127.0.0.1"),
        port=int(os.environ.get("OMNICHECK_WEB_PORT", "8000")),
        reload=False,
    )
