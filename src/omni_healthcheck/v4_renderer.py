"""Wrapper for the immutable, approved Jiuxing V4 renderer."""

from __future__ import annotations

import importlib.util
from pathlib import Path


VENDOR_RENDERER = (
    Path(__file__).parents[2]
    / "vendor"
    / "omni-v4-renderer"
    / "scripts"
    / "build_report.py"
)


def render_v4_docx(report: dict, output_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("omni_approved_v4_renderer", VENDOR_RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load approved V4 renderer: {VENDOR_RENDERER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build(report, output_path)
