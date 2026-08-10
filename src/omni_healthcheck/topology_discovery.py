"""Deterministic topology discovery from an unconfigured evidence bundle."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath


TEXT_EXTENSIONS = {".txt", ".log", ".out", ".sql", ".csv", ".tsv", ".conf"}
ROLE_ORDER = {"Primary": 0, "Standby": 1, "DR": 2, "Witness": 3, "Unknown": 4}


@dataclass(frozen=True)
class DiscoveryEvidence:
    path: str
    content: bytes


def _safe_text(item: DiscoveryEvidence) -> str:
    if PurePosixPath(item.path).suffix.casefold() not in TEXT_EXTENSIONS:
        return ""
    return item.content.decode("utf-8", errors="ignore")


def _hostname_from_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    filename = PurePosixPath(normalized).name
    match = re.search(
        r"healthche?kos-log-(.+?)(?:-\d{8})?\.(?:txt|log|out)$",
        filename,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    for part in reversed(PurePosixPath(normalized).parts[:-1]):
        match = re.fullmatch(r"(?:\d{8}_)?(.+?)_check", part, re.IGNORECASE)
        if match and match.group(1).casefold() not in {"pem"}:
            return match.group(1)
    return None


def _hostname_from_os_text(text: str) -> str | None:
    match = re.search(
        r"主機名稱\s*=+\s*\n(?:[^\n]*\n)?([a-z0-9][a-z0-9._-]*)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1) if match else None


def _add_signal(
    signals: dict[str, list[str]], role: str, description: str
) -> None:
    if description not in signals[role]:
        signals[role].append(description)


def _discover_node(hostname: str, texts: list[str], file_count: int) -> dict:
    combined = "\n".join(texts)
    folded = combined.casefold()
    host_folded = hostname.casefold()
    signals: dict[str, list[str]] = defaultdict(list)
    services: list[str] = []

    bind = re.search(r"^bind\.address\s*=\s*([^:\s]+)", combined, re.MULTILINE | re.IGNORECASE)
    if bind:
        alias = bind.group(1).casefold()
        if "primary" in alias:
            _add_signal(signals, "Primary", "EFM bind.address 標示 primary")
        elif "standby" in alias:
            _add_signal(signals, "Standby", "EFM bind.address 標示 standby")
        elif "witness" in alias:
            _add_signal(signals, "Witness", "EFM bind.address 標示 witness")

    if re.search(r"^is\.witness\s*=\s*true\s*$", combined, re.MULTILINE | re.IGNORECASE):
        _add_signal(signals, "Witness", "EFM is.witness=true")
    if re.search(r"dr\d*(?:$|[-_.])", host_folded):
        _add_signal(signals, "DR", "主機名稱含 DR 標記")
    if "primary_conninfo" in folded and not signals:
        _add_signal(signals, "Standby", "偵測到 primary_conninfo；需人工確認 Standby／DR")

    if "db.user=efm" in folded or "cluster status: efm" in folded:
        services.append("EFM")
    pem_server = bool(
        re.search(r"(?:^|[-_.])pem[a-z0-9]*(?:$|[-_.])", host_folded)
        or "/usr/edb/pem/server" in folded
        or "pemserver.service" in folded
    )
    if pem_server:
        services.append("PEM")
        if not any(role in signals for role in ("Primary", "Standby", "DR")):
            _add_signal(signals, "Witness", "偵測到 PEM Server，依標準架構歸為 Witness 候選")
    if re.search(r"(?:^|[/\s])barman(?:[./\s]|$)", folded):
        services.append("Barman")
    if (
        "pgbackrest --stanza" in folded
        and re.search(r"backup\s+--type=(?:full|diff|incr)", folded)
    ):
        services.append("pgBackRest")
    if re.search(r"(?:xdb\.conf|xdb-server|xdb service)", folded):
        services.append("XDB")

    role_candidates = [role for role, evidence in signals.items() if evidence]
    conflicts = []
    if len(role_candidates) > 1:
        conflicts.append("同一節點出現多個角色訊號，必須人工判斷")
        suggested_role = "Unknown"
        confidence = "conflict"
    elif role_candidates:
        suggested_role = role_candidates[0]
        strong = any(
            marker in " ".join(signals[suggested_role])
            for marker in ("bind.address", "is.witness=true", "PEM Server")
        )
        confidence = "high" if strong else "medium"
    else:
        suggested_role = "Unknown"
        confidence = "low"

    return {
        "hostname": hostname,
        "suggested_role": suggested_role,
        "services": list(dict.fromkeys(services)),
        "confidence": confidence,
        "role_evidence": [
            {"role": role, "reason": reason}
            for role in sorted(signals, key=lambda value: ROLE_ORDER[value])
            for reason in signals[role]
        ],
        "conflicts": conflicts,
        "evidence_file_count": file_count,
    }


def discover_topology(items: list[DiscoveryEvidence]) -> dict:
    """Return role suggestions that must be confirmed by an operator."""
    grouped_text: dict[str, list[str]] = defaultdict(list)
    grouped_files: dict[str, int] = defaultdict(int)
    unassigned = 0

    for item in items:
        text = _safe_text(item)
        hostname = _hostname_from_path(item.path) or _hostname_from_os_text(text)
        if hostname:
            grouped_files[hostname] += 1
            if text:
                grouped_text[hostname].append(text)
        else:
            unassigned += 1

    nodes = [
        _discover_node(hostname, grouped_text[hostname], grouped_files[hostname])
        for hostname in sorted(grouped_files, key=str.casefold)
    ]
    primary_count = sum(node["suggested_role"] == "Primary" for node in nodes)
    unresolved = [node["hostname"] for node in nodes if node["suggested_role"] == "Unknown"]
    warnings = []
    if primary_count != 1:
        warnings.append(f"Primary 候選數為 {primary_count}；正式執行前必須確認且只能保留一台")
    if unresolved:
        warnings.append("下列節點角色無法確定：" + "、".join(unresolved))
    if unassigned:
        warnings.append(f"有 {unassigned} 個檔案尚未映射節點；圖片將沿用既有 Primary 規則")

    return {
        "schema_version": "1.0",
        "confirmation_required": True,
        "can_confirm": bool(nodes) and primary_count == 1 and not unresolved,
        "summary": {
            "node_count": len(nodes),
            "primary_candidates": primary_count,
            "unresolved_nodes": len(unresolved),
            "unassigned_files": unassigned,
        },
        "nodes": nodes,
        "warnings": warnings,
    }
