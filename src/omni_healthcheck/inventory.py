"""Recursive evidence inventory and hashing."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from omni_healthcheck import __version__
from omni_healthcheck.config import JobConfig


CATEGORY_BY_EXTENSION = {
    ".txt": "text",
    ".log": "text",
    ".out": "text",
    ".csv": "table",
    ".tsv": "table",
    ".sql": "sql",
    ".json": "structured",
    ".yaml": "structured",
    ".yml": "structured",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".docx": "document",
    ".pdf": "document",
}


@dataclass(frozen=True)
class InventoryEntry:
    path: str
    size: int
    extension: str
    media_type: str
    preliminary_category: str
    sha256: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_file(path: Path) -> tuple[str, str]:
    extension = path.suffix.lower()
    category = CATEGORY_BY_EXTENSION.get(extension, "unknown")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return category, media_type


def iter_regular_files(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            continue
        if path.is_file():
            yield path


def build_inventory(input_dir: Path, job: JobConfig) -> dict:
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"input path is not a directory: {input_dir}")

    entries: list[InventoryEntry] = []
    for path in iter_regular_files(input_dir):
        category, media_type = classify_file(path)
        entries.append(
            InventoryEntry(
                path=path.relative_to(input_dir).as_posix(),
                size=path.stat().st_size,
                extension=path.suffix.lower(),
                media_type=media_type,
                preliminary_category=category,
                sha256=sha256_file(path),
            )
        )

    unknown_paths = [
        entry.path for entry in entries if entry.preliminary_category == "unknown"
    ]
    return {
        "schema_version": "1.0",
        "pipeline_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "job": {
            "customer": job.customer,
            "system_name": job.system_name,
            "period": job.period,
            "product": job.product,
        },
        "summary": {
            "total_files": len(entries),
            "unknown_files": len(unknown_paths),
        },
        "unknown_paths": unknown_paths,
        "files": [asdict(entry) for entry in entries],
    }

