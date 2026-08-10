"""M9 FastAPI application for local job creation and pipeline execution."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from omni_healthcheck.application_data import ApplicationDataStore
from omni_healthcheck.auth import AuthStore
from omni_healthcheck.cli import run_generate
from omni_healthcheck.config import JobConfig
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.job_store import (
    JobNotFoundError,
    JobStore,
    UnsafeUploadPathError,
)
from omni_healthcheck.services import SERVICE_REGISTRY
from omni_healthcheck.topology_discovery import DiscoveryEvidence, discover_topology
from omni_healthcheck.web_ui import INDEX_HTML


class LoginRequest(BaseModel):
    username: str
    password: str


def _default_data_root() -> Path:
    return Path(os.environ.get("OMNICHECK_DATA_ROOT", "data/jobs"))


def _default_rules_path() -> Path:
    return Path(os.environ.get("OMNICHECK_RULES_PATH", "config/rules.default.yaml"))


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
    auth_store: AuthStore | None = None,
    auth_required: bool | None = None,
) -> FastAPI:
    selected_database_url = database_url or os.environ.get("OMNICHECK_DATABASE_URL")
    selected_metadata_store = metadata_store
    if selected_metadata_store is None and selected_database_url:
        selected_metadata_store = DatabaseMetadataStore(selected_database_url)
    selected_auth_store = auth_store
    if selected_auth_store is None and selected_database_url:
        selected_auth_store = AuthStore(selected_database_url)
    selected_auth_required = (
        auth_required if auth_required is not None
        else os.environ.get("OMNICHECK_AUTH_REQUIRED", "false").lower() in {"1", "true", "yes"}
    )
    if selected_auth_required and selected_auth_store is None:
        raise ValueError("auth_required needs database-backed AuthStore")
    store = JobStore(
        data_root or _default_data_root(),
        metadata_store=selected_metadata_store,
    )
    selected_rules = (rules_path or _default_rules_path()).resolve()
    app = FastAPI(title="OMNIcheck AI", version="0.9.0")
    app.state.job_store = store
    app.state.auth_store = selected_auth_store

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        if selected_auth_required and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            host = request.headers.get("host")
            if origin and host and origin.rstrip("/").split("://", 1)[-1] != host:
                response = Response(content='{"detail":"cross-site request denied"}',
                                    status_code=403, media_type="application/json")
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                return response
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def request_token(request: Request) -> str | None:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return request.cookies.get("omnicheck_session")

    def current_identity(request: Request) -> dict | None:
        if not selected_auth_required:
            return None
        token = request_token(request)
        identity = selected_auth_store.identity_for_token(token) if token else None
        if identity is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return identity

    def client_ip(request: Request) -> str | None:
        return request.client.host if request.client else None

    def can(identity: dict | None, permission: str, customer_id: str | None) -> bool:
        return not selected_auth_required or bool(
            identity and selected_auth_store.allowed(identity, permission, customer_id)
        )

    def audit(request: Request, action: str, outcome: str, *, identity: dict | None = None,
              customer_id: str | None = None, job_id: str | None = None,
              details: dict | None = None) -> None:
        if selected_auth_store is not None:
            selected_auth_store.audit(action=action, outcome=outcome,
                request_id=request.headers.get("x-request-id") or os.urandom(16).hex(),
                identity=identity, customer_id=customer_id, job_id=job_id,
                client_ip=client_ip(request), details=details)

    def job_or_404(job_id: str, identity: dict | None = None, permission: str = "read") -> dict:
        try:
            metadata = store.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        if not can(identity, permission, metadata.get("customer_id")):
            raise HTTPException(status_code=404, detail="job not found")
        return metadata

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
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
        }

    @app.post("/api/auth/login")
    def login(payload: LoginRequest, request: Request, response: Response) -> dict:
        if selected_auth_store is None:
            raise HTTPException(status_code=503, detail="authentication is not configured")
        authenticated = selected_auth_store.authenticate(payload.username, payload.password)
        if authenticated is None:
            audit(request, "auth.login", "failed", details={"username": payload.username.strip().lower()})
            raise HTTPException(status_code=401, detail="invalid credentials")
        token, identity = authenticated
        response.set_cookie("omnicheck_session", token, httponly=True,
                            secure=os.environ.get("OMNICHECK_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
                            samesite="strict", max_age=12 * 60 * 60)
        audit(request, "auth.login", "success", identity=identity)
        return identity

    @app.post("/api/auth/logout", status_code=204)
    def logout(request: Request, response: Response,
               identity: dict | None = Depends(current_identity)) -> Response:
        token = request_token(request)
        if token and selected_auth_store:
            selected_auth_store.revoke(token)
        audit(request, "auth.logout", "success", identity=identity)
        response.delete_cookie("omnicheck_session")
        response.status_code = 204
        return response

    @app.get("/api/auth/me")
    def me(identity: dict | None = Depends(current_identity)) -> dict:
        return identity or {"authentication": "disabled"}

    @app.get("/api/auth/context")
    def auth_context(identity: dict | None = Depends(current_identity)) -> dict:
        if selected_auth_store is None or identity is None:
            return {"identity": identity or {"authentication": "disabled"}, "customers": [], "systems": []}
        return selected_auth_store.context(identity)

    @app.get("/api/config-options")
    def config_options(identity: dict | None = Depends(current_identity)) -> dict:
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
    def create_job(request: Request, config: JobConfig,
                   customer_id: str | None = Query(None), system_id: str | None = Query(None),
                   identity: dict | None = Depends(current_identity)) -> dict:
        if bool(customer_id) != bool(system_id):
            raise HTTPException(status_code=422, detail="customer_id and system_id are required together")
        if selected_auth_required and not customer_id:
            raise HTTPException(status_code=422, detail="authenticated jobs require customer scope")
        if not can(identity, "create", customer_id):
            audit(request, "job.create", "denied", identity=identity, customer_id=customer_id)
            raise HTTPException(status_code=403, detail="permission denied")
        if customer_id and system_id:
            application = ApplicationDataStore(engine=selected_auth_store.engine)
            try:
                application.get_system(customer_id, system_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="system not found") from exc
        created = store.create(config)
        if customer_id and system_id:
            ApplicationDataStore(engine=selected_auth_store.engine).associate_job(
                customer_id, system_id, created["job_id"]
            )
            created = store.get(created["job_id"])
        audit(request, "job.create", "success", identity=identity,
              customer_id=customer_id, job_id=created["job_id"])
        return created

    @app.post("/api/topology/discover")
    def discover_uploaded_topology(files: list[UploadFile] = File(...),
                                   identity: dict | None = Depends(current_identity)) -> dict:
        if selected_auth_required and not any(
            selected_auth_store.allowed(identity, "create", membership["customer_id"])
            for membership in identity["memberships"]
        ) and identity.get("platform_role") != "platform_admin":
            raise HTTPException(status_code=403, detail="permission denied")
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
    def list_jobs(identity: dict | None = Depends(current_identity)) -> list[dict]:
        return [job for job in store.list() if can(identity, "read", job.get("customer_id"))]

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, identity: dict | None = Depends(current_identity)) -> dict:
        metadata = job_or_404(job_id, identity)
        outputs = store.outputs(job_id) if metadata["status"] == "succeeded" else []
        return {**metadata, "outputs": outputs}

    @app.post("/api/jobs/{job_id}/files", status_code=201)
    def upload_files(
        job_id: str,
        request: Request,
        files: list[UploadFile] = File(...),
        identity: dict | None = Depends(current_identity),
    ) -> dict:
        metadata = job_or_404(job_id, identity, "upload")
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
        audit(request, "job.upload", "success", identity=identity,
              customer_id=metadata.get("customer_id"), job_id=job_id,
              details={"file_count": len(saved)})
        return {"files": saved}

    @app.post("/api/jobs/{job_id}/run", status_code=202)
    def run_job(job_id: str, request: Request, background: BackgroundTasks,
                identity: dict | None = Depends(current_identity)) -> dict:
        metadata = job_or_404(job_id, identity, "run")
        if metadata["status"] not in {"draft", "failed"}:
            raise HTTPException(status_code=409, detail="job is already running or complete")
        if metadata["input_files"] == 0:
            raise HTTPException(status_code=409, detail="job has no input evidence")
        reset = {"attempts": 0} if store.database_backed and metadata["status"] == "failed" else {}
        store.update(job_id, status="queued", error=None, **reset)
        if not store.database_backed:
            background.add_task(_run_job, store, job_id, selected_rules)
        audit(request, "job.run", "success", identity=identity,
              customer_id=metadata.get("customer_id"), job_id=job_id)
        return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}/events")
    def list_job_events(job_id: str, identity: dict | None = Depends(current_identity)) -> list[dict]:
        job_or_404(job_id, identity)
        return store.events(job_id)

    @app.get("/api/jobs/{job_id}/outputs")
    def list_outputs(job_id: str, identity: dict | None = Depends(current_identity)) -> list[dict]:
        metadata = job_or_404(job_id, identity)
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        return store.outputs(job_id)

    @app.get("/api/jobs/{job_id}/outputs/{filename}")
    def download_output(job_id: str, filename: str, request: Request,
                        identity: dict | None = Depends(current_identity)) -> FileResponse:
        metadata = job_or_404(job_id, identity, "download")
        if metadata["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="job output is not ready")
        try:
            path = store.output_path(job_id, filename)
        except (FileNotFoundError, UnsafeUploadPathError) as exc:
            raise HTTPException(status_code=404, detail="output not found") from exc
        audit(request, "artifact.download", "success", identity=identity,
              customer_id=metadata.get("customer_id"), job_id=job_id,
              details={"filename": path.name})
        return FileResponse(path, filename=path.name)

    @app.get("/api/audit-events")
    def list_audit_events(customer_id: str | None = Query(None),
                          identity: dict | None = Depends(current_identity)) -> list[dict]:
        if selected_auth_store is None or identity is None:
            raise HTTPException(status_code=503, detail="audit is not configured")
        try:
            return selected_auth_store.list_audit(identity, customer_id=customer_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="permission denied") from exc

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
