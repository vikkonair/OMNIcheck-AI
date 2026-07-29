"""Filesystem-backed job metadata and immutable evidence storage for M9."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import BinaryIO
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

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

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
        metadata = {
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
        self._write_json(job_dir / "job.json", metadata)
        return metadata

    def get(self, job_id: str) -> dict:
        path = self._job_dir(job_id) / "job.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> list[dict]:
        jobs = []
        for path in self.root.glob("*/job.json"):
            try:
                jobs.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(jobs, key=lambda item: item["created_at"], reverse=True)

    def update(self, job_id: str, **changes: object) -> dict:
        with self._lock:
            metadata = self.get(job_id)
            metadata.update(changes)
            metadata["updated_at"] = _now()
            self._write_json(self._job_dir(job_id) / "job.json", metadata)
            return metadata

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
