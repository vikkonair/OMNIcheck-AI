"""Deterministic node resolution and Primary-only evidence scope control."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from omni_healthcheck.config import JobConfig


TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".out",
    ".csv",
    ".tsv",
    ".sql",
    ".json",
    ".yaml",
    ".yml",
}
OS_HINTS = {"os", "system", "sar", "vmstat", "iostat", "filesystem", "df"}
DB_HINTS = {"db", "database", "postgres", "postgresql", "epas", "edb", "sql"}
MONITORING_HINTS = {"monitoring", "pem", "screenshot", "trend", "graph"}
DOCUMENT_HINTS = {"document", "documents", "report", "reports", "prior"}


@dataclass(frozen=True)
class NodeResolution:
    hostname: str | None
    role: str | None
    status: Literal["resolved", "unresolved", "ambiguous"]
    matched_nodes: list[str]
    sources: list[str]


def _contains_hostname(value: str, hostname: str) -> bool:
    pattern = rf"(?<![a-z0-9_-]){re.escape(hostname.casefold())}(?![a-z0-9_-])"
    return re.search(pattern, value.casefold()) is not None


def _sample_text(path: Path, limit: int = 128 * 1024) -> str:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        return path.read_bytes()[:limit].decode("utf-8", errors="ignore")
    except OSError:
        return ""


def resolve_node(path: Path, relative_path: str, job: JobConfig) -> NodeResolution:
    path_matches = [
        node.hostname
        for node in job.nodes
        if _contains_hostname(relative_path, node.hostname)
    ]
    content = _sample_text(path)
    content_matches = [
        node.hostname
        for node in job.nodes
        if content and _contains_hostname(content, node.hostname)
    ]
    matches = list(dict.fromkeys(path_matches + content_matches))
    sources = []
    if path_matches:
        sources.append("relative_path")
    if content_matches:
        sources.append("content")

    if len(matches) == 1:
        node = next(
            configured
            for configured in job.nodes
            if configured.hostname.casefold() == matches[0].casefold()
        )
        return NodeResolution(
            hostname=node.hostname,
            role=node.role,
            status="resolved",
            matched_nodes=matches,
            sources=sources,
        )
    if len(matches) > 1:
        return NodeResolution(
            hostname=None,
            role=None,
            status="ambiguous",
            matched_nodes=matches,
            sources=sources,
        )
    return NodeResolution(
        hostname=None,
        role=None,
        status="unresolved",
        matched_nodes=[],
        sources=[],
    )


def classify_evidence_domain(relative_path: str, extension: str) -> str:
    top_level = relative_path.casefold().split("/", 1)[0]
    if top_level in OS_HINTS:
        return "os"
    if top_level in DB_HINTS:
        return "database"
    if top_level in MONITORING_HINTS:
        return "monitoring"
    if top_level in DOCUMENT_HINTS:
        return "document"

    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", relative_path.casefold())
        if token
    }
    if tokens & MONITORING_HINTS:
        return "monitoring"
    if tokens & DB_HINTS or extension == ".sql":
        return "database"
    if tokens & OS_HINTS:
        return "os"
    if tokens & DOCUMENT_HINTS or extension in {".docx", ".pdf"}:
        return "document"
    if extension in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        return "monitoring"
    return "unknown"


def scope_decision(domain: str, resolution: NodeResolution) -> tuple[str, str]:
    if domain == "database":
        if resolution.status != "resolved":
            return "pending", "database evidence node is not uniquely resolved"
        if resolution.role == "Primary":
            return "allowed", "database evidence belongs to confirmed Primary"
        return "excluded", f"database evidence belongs to {resolution.role}, not Primary"

    if domain == "os":
        if resolution.status == "resolved":
            return "allowed", "OS evidence is allowed from every configured node"
        return "pending", "OS evidence node is not uniquely resolved"

    if domain == "monitoring":
        if resolution.status == "resolved":
            return "allowed", "monitoring evidence is mapped to a configured node"
        return "pending", "monitoring evidence node is not uniquely resolved"

    if domain == "document":
        return "pending", "document evidence requires later prior-report classification"
    return "pending", "evidence domain is unknown"


def build_topology(job: JobConfig) -> dict:
    primary = next(node for node in job.nodes if node.role == "Primary")
    return {
        "schema_version": "1.0",
        "primary": {
            "hostname": primary.hostname,
            "confirmed": True,
            "confirmation_source": "job_config",
        },
        "nodes": [
            {
                "hostname": node.hostname,
                "role": node.role,
                "role_source": "job_config",
            }
            for node in job.nodes
        ],
    }


def build_scope_ledger(input_dir: Path, inventory: dict, job: JobConfig) -> dict:
    evidence = []
    for item in inventory["files"]:
        relative_path = item["path"]
        resolution = resolve_node(input_dir / relative_path, relative_path, job)
        domain = classify_evidence_domain(relative_path, item["extension"])
        decision, reason = scope_decision(domain, resolution)
        evidence.append(
            {
                "path": relative_path,
                "sha256": item["sha256"],
                "evidence_domain": domain,
                "node": resolution.hostname,
                "node_role": resolution.role,
                "resolution_status": resolution.status,
                "matched_nodes": resolution.matched_nodes,
                "resolution_sources": resolution.sources,
                "decision": decision,
                "reason": reason,
            }
        )

    return {
        "schema_version": "1.0",
        "policy": {
            "include_os_from_all_nodes": job.scope.include_os_from_all_nodes,
            "database_primary_only": job.scope.database_primary_only,
        },
        "summary": {
            state: sum(item["decision"] == state for item in evidence)
            for state in ("allowed", "excluded", "pending")
        },
        "evidence": evidence,
    }
