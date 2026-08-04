"""Filesystem-backed job metadata and immutable evidence storage for M9."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any, BinaryIO
from uuid import uuid4

import yaml

from omni_healthcheck.config import JobConfig


class JobNotFoundError(KeyError):
    """Raised when a requested job ID does not exist."""


class UnsafeUploadPathError(ValueError):
    """Raised when an upload attempts to escape its job input directory."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    """Persist jobs beneath one application-owned data root."""

    def __init__(self, root: Path, metadata_store: Any | None = None):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.metadata_store = metadata_store
        self._lock = Lock()

    @property
    def database_backed(self) -> bool:
        return self.metadata_store is not None

    def ping(self) -> None:
        if self.metadata_store is not None:
            self.metadata_store.ping()

    def _job_dir(self, job_id: str) -> Path:
        if not job_id or any(character not in "0123456789abcdef" for character in job_id):
            raise JobNotFoundError(job_id)
        path = self.root / job_id
        if not path.is_dir():
            raise JobNotFoundError(job_id)
        return path

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            Path(temporary).replace(path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def _write_snapshot(self, job_id: str, metadata: dict) -> None:
        job_dir = self.root / job_id
        if job_dir.is_dir():
            self._write_json(job_dir / "job.json", metadata)

    def create(self, config: JobConfig) -> dict:
        job_id = uuid4().hex
        job_dir = self.root / job_id
        (job_dir / "input").mkdir(parents=True)
        (job_dir / "output").mkdir()
        (job_dir / "job.yaml").write_text(
            yaml.safe_dump(
                config.model_dump(mode="json", exclude_none=True),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        metadata: dict[str, object] = {
            "job_id": job_id,
            "customer": config.customer,
            "system_name": config.system_name,
            "period": config.period,
            "product": config.product,
            "status": "draft",
            "created_at": _now(),
            "updated_at": _now(),
            "error": None,
            "input_files": 0,
        }
        if self.metadata_store is not None:
            metadata = self.metadata_store.create(metadata)
        self._write_snapshot(job_id, metadata)
        return metadata

    def get(self, job_id: str) -> dict:
        job_dir = self._job_dir(job_id)
        if self.metadata_store is not None:
            try:
                return self.metadata_store.get(job_id)
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc
        path = job_dir / "job.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> list[dict]:
        if self.metadata_store is not None:
            return self.metadata_store.list()
        jobs = []
        for path in self.root.glob("*/job.json"):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(jobs, key=lambda item: item["created_at"], reverse=True)

    def update(self, job_id: str, **changes: object) -> dict:
        with self._lock:
            if self.metadata_store is not None:
                try:
                    metadata = self.metadata_store.update(job_id, **changes)
                except KeyError as exc:
                    raise JobNotFoundError(job_id) from exc
                self._write_snapshot(job_id, metadata)
                return metadata
            metadata = self.get(job_id)
            metadata.update(changes)
            metadata["updated_at"] = _now()
            self._write_json(self._job_dir(job_id) / "job.json", metadata)
            return metadata

    def claim_next(self, worker_id: str) -> dict | None:
        if self.metadata_store is None:
            raise RuntimeError("durable job claiming requires a database metadata store")
        metadata = self.metadata_store.claim_next(worker_id)
        if metadata is not None:
            self._write_snapshot(metadata["job_id"], metadata)
        return metadata

    def succeed(self, job_id: str, worker_id: str) -> dict:
        if self.metadata_store is None:
            return self.update(job_id, status="succeeded", error=None)
        metadata = self.metadata_store.succeed(job_id, worker_id)
        self._write_snapshot(job_id, metadata)
        return metadata

    def fail(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        retry_seconds: int,
    ) -> dict:
        if self.metadata_store is None:
            return self.update(job_id, status="failed", error=error)
        metadata = self.metadata_store.fail(
            job_id,
            worker_id,
            error,
            retry_seconds=retry_seconds,
        )
        self._write_snapshot(job_id, metadata)
        return metadata

    def events(self, job_id: str) -> list[dict]:
        self._job_dir(job_id)
        if self.metadata_store is None:
            return []
        return self.metadata_store.events(job_id)

    def heartbeat(self, job_id: str, worker_id: str) -> bool:
        if self.metadata_store is None:
            return True
        return self.metadata_store.heartbeat(job_id, worker_id)

    @staticmethod
    def safe_relative_path(filename: str) -> Path:
        normalized = filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or any(part in {"", "."} for part in path.parts)
        ):
            raise UnsafeUploadPathError(filename)
        return Path(*path.parts)

    def save_upload(self, job_id: str, filename: str, stream: BinaryIO) -> dict:
        job_dir = self._job_dir(job_id)
        metadata = self.get(job_id)
        if metadata["status"] != "draft":
            raise ValueError("uploads are only allowed while a job is draft")
        relative = self.safe_relative_path(filename)
        destination = job_dir / "input" / relative
        if destination.exists():
            raise FileExistsError(f"input evidence already exists: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".upload.",
            dir=destination.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
            Path(temporary).replace(destination)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        metadata = self.update(
            job_id,
            input_files=metadata["input_files"] + 1,
        )
        return {
            "path": relative.as_posix(),
            "size": destination.stat().st_size,
            "input_files": metadata["input_files"],
        }

    def validate_upload_batch(self, job_id: str, filenames: list[str]) -> None:
        """Validate a complete request before writing any of its files."""
        job_dir = self._job_dir(job_id)
        metadata = self.get(job_id)
        if metadata["status"] != "draft":
            raise ValueError("uploads are only allowed while a job is draft")
        relative_paths = [self.safe_relative_path(name) for name in filenames]
        if len(set(relative_paths)) != len(relative_paths):
            raise FileExistsError("duplicate input evidence path in upload request")
        for relative in relative_paths:
            if (job_dir / "input" / relative).exists():
                raise FileExistsError(f"input evidence already exists: {relative}")

    def paths(self, job_id: str) -> dict[str, Path]:
        job_dir = self._job_dir(job_id)
        return {
            "job": job_dir / "job.yaml",
            "input": job_dir / "input",
            "output": job_dir / "output",
        }

    def outputs(self, job_id: str) -> list[dict]:
        output = self.paths(job_id)["output"]
        return [
            {
                "name": path.name,
                "size": path.stat().st_size,
            }
            for path in sorted(output.iterdir())
            if path.is_file()
        ]

    def output_path(self, job_id: str, filename: str) -> Path:
        relative = self.safe_relative_path(filename)
        if len(relative.parts) != 1:
            raise UnsafeUploadPathError(filename)
        path = self.paths(job_id)["output"] / relative
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path
