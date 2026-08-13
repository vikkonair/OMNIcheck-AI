"""Wrapper for the immutable, approved Jiuxing V4 renderer."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


VENDOR_RENDERER = (
    Path(__file__).parents[2]
    / "vendor"
    / "omni-v4-renderer"
    / "scripts"
    / "build_report.py"
)


def _vendor_renderer() -> Path:
    """Locate the approved renderer in a source tree or isolated release venv."""
    explicit = os.environ.get("OMNICHECK_VENDOR_RENDERER")
    candidates = [
        Path(explicit) if explicit else None,
        Path.cwd() / "vendor" / "omni-v4-renderer" / "scripts" / "build_report.py",
        VENDOR_RENDERER,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise RuntimeError("cannot locate approved V4 renderer; set OMNICHECK_VENDOR_RENDERER")


def render_v4_docx(report: dict, output_path: Path) -> None:
    renderer = _vendor_renderer()
    spec = importlib.util.spec_from_file_location("omni_approved_v4_renderer", renderer)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load approved V4 renderer: {renderer}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build(report, output_path)
