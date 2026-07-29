"""M9 FastAPI application for local job creation and pipeline execution."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from omni_healthcheck.cli import run_generate
from omni_healthcheck.config import JobConfig
from omni_healthcheck.job_store import (
    JobNotFoundError,
    JobStore,
    UnsafeUploadPathError,
)


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
) -> FastAPI:
    store = JobStore(data_root or _default_data_root())
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
        return _INDEX_HTML

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": "OMNIcheck AI"}

    @app.post("/api/jobs", status_code=201)
    def create_job(config: JobConfig) -> dict:
        return store.create(config)

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return store.list()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        metadata = job_or_404(job_id)
        return {**metadata, "outputs": store.outputs(job_id)}

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
        store.update(job_id, status="queued", error=None)
        background.add_task(_run_job, store, job_id, selected_rules)
        return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}/outputs")
    def list_outputs(job_id: str) -> list[dict]:
        job_or_404(job_id)
        return store.outputs(job_id)

    @app.get("/api/jobs/{job_id}/outputs/{filename}")
    def download_output(job_id: str, filename: str) -> FileResponse:
        job_or_404(job_id)
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


_INDEX_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OMNIcheck AI</title>
  <style>
    :root { color-scheme: light; font-family: Arial, "Noto Sans TC", sans-serif; }
    body { margin: 0; background: #f4f7f9; color: #18323f; }
    header { padding: 24px 6vw; color: white; background: #087c91; }
    main { max-width: 1100px; margin: 28px auto; padding: 0 24px; }
    section { background: white; padding: 22px; margin-bottom: 18px; border-radius: 10px;
      box-shadow: 0 4px 18px #19384516; }
    textarea { width: 100%; min-height: 260px; box-sizing: border-box; font: 13px monospace; }
    button { border: 0; border-radius: 6px; padding: 10px 16px; color: white;
      background: #087c91; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 9px; text-align: left; border-bottom: 1px solid #dbe5e9; }
    .muted { color: #69808b; }
  </style>
</head>
<body>
<header><h1>OMNIcheck AI</h1><div>On-premises Database Health Check</div></header>
<main>
  <section>
    <h2>建立健檢案件</h2>
    <p class="muted">先建立案件，再透過 API 上傳資料並啟動 Pipeline。</p>
    <textarea id="config">{
  "customer": "測試客戶",
  "system_name": "db-system",
  "period": "2026-H1",
  "engineer": "XXX",
  "product": "PostgreSQL",
  "first_healthcheck": true,
  "nodes": [{"hostname": "db-primary", "role": "Primary", "services": []}],
  "scope": {"include_os_from_all_nodes": true, "database_primary_only": true},
  "report": {"template": "omni-v4", "output_docx": true, "output_pdf": true},
  "ai": {"enabled": false, "provider": "disabled"}
}</textarea>
    <p><button onclick="createJob()">建立案件</button></p>
    <pre id="result"></pre>
  </section>
  <section>
    <h2>案件列表</h2>
    <table><thead><tr><th>客戶</th><th>期間</th><th>產品</th><th>狀態</th><th>Job ID</th></tr></thead>
      <tbody id="jobs"></tbody></table>
  </section>
</main>
<script>
async function refreshJobs() {
  const jobs = await (await fetch('/api/jobs')).json();
  document.getElementById('jobs').innerHTML = jobs.map(j =>
    `<tr><td>${j.customer}</td><td>${j.period}</td><td>${j.product}</td>` +
    `<td>${j.status}</td><td><code>${j.job_id}</code></td></tr>`).join('');
}
async function createJob() {
  const result = document.getElementById('result');
  try {
    const response = await fetch('/api/jobs', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:document.getElementById('config').value});
    const body = await response.json();
    result.textContent = JSON.stringify(body, null, 2);
    await refreshJobs();
  } catch (error) { result.textContent = String(error); }
}
refreshJobs();
</script>
</body>
</html>"""
