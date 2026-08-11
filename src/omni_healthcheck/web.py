"""M9 FastAPI application for local job creation and pipeline execution."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

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
from omni_healthcheck.web_ui_integrated import INTEGRATED_INDEX_HTML


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

    def job_or_404(job_id: str) -> dict:
        try:
            return store.get(job_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

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
        return store.create(config)

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
        return store.list()

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
        job_or_404(job_id)
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
        metadata = job_or_404(job_id)
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
