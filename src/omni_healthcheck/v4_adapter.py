"""Adapter from the M7 report model to the approved Jiuxing V4 report contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from omni_healthcheck.reporting import ReportModel


STATUS_MAP = {
    "normal": "正常",
    "attention": "注意",
    "critical": "異常",
    "pending": "待確認",
}
MONITORING_TITLES = {
    "cpu": "CPU 使用率趨勢",
    "memory": "記憶體使用率趨勢",
    "disk": "磁碟使用率趨勢",
    "process": "程序狀態趨勢",
    "transaction": "Transaction 趨勢",
    "commit": "Commit / Rollback 趨勢",
}
PRODUCT_NAMES = {
    "EPAS": "EDB Postgres Advanced Server",
    "PostgreSQL": "PostgreSQL",
}
INFORMATION_ONLY_TITLES = {
    "主機與作業系統組態彙整",
    "版本資訊",
    "Extension 清單",
    "資料庫清單",
    "PEM / EFM 服務摘要",
    "PEM / EFM / XDB 服務摘要",
}


def _split_numbered_title(value: str, fallback: str) -> tuple[str, str]:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)[.\s]+(.+?)\s*$", value)
    return (match.group(1), match.group(2)) if match else (fallback, value)


def _assessment(value: dict | None) -> dict[str, str]:
    if value:
        observation = str(value.get("observation", "")).strip()
        if "結論：" not in observation:
            observation = f"{observation}\n結論：本項狀態為{STATUS_MAP[value['status']]}"
        return {
            "status": STATUS_MAP[value["status"]],
            "observation": observation,
            "recommendation": str(value.get("recommendation", "")).strip()
            or "確認當期 Output 並持續追蹤",
        }
    return {
        "status": "待確認",
        "observation": "已彙整當期可見 Output，仍需完成工程師覆核\n結論：本項仍待確認",
        "recommendation": "確認 Output 與適用條件後完成覆核",
    }


def _evidence(unit: dict) -> dict[str, Any]:
    headers = list(unit["headers"])
    rows = [list(row) for row in unit["rows"]]
    if headers == ["Output"]:
        return {
            "type": "text",
            "content": "\n".join(str(row[0]) for row in rows if row),
            "font_size": (
                7.2
                if any(
                    token in unit["title"]
                    for token in (
                        "postgresql.auto.conf",
                        "postgresql.conf",
                        "pg_hba.conf",
                    )
                )
                else 8.0
            ),
        }
    return {"type": "table", "headers": headers, "rows": rows}


def _select_columns(unit: dict, wanted: list[tuple[str, str]]) -> dict:
    headers = [str(header) for header in unit.get("headers") or []]
    normalized = [header.casefold().replace("_", " ").strip() for header in headers]
    indexes = []
    labels = []
    for source, label in wanted:
        key = source.casefold().replace("_", " ")
        if key in normalized:
            indexes.append(normalized.index(key))
            labels.append(label)
    if not indexes:
        return unit
    return {
        **unit,
        "headers": labels,
        "rows": [
            [row[index] if index < len(row) else "" for index in indexes]
            for row in unit.get("rows") or []
        ],
    }


def _prepare_unit(unit: dict) -> dict:
    prepared = {**unit, "rows": [list(row) for row in unit.get("rows") or []]}
    if prepared["title"] == "資料庫清單":
        return _select_columns(
            prepared,
            [
                ("Name", "資料庫名稱"),
                ("Owner", "擁有者"),
                ("Access privileges", "權限"),
                ("Size", "大小"),
            ],
        )
    if prepared["title"] == "同步狀態":
        return _select_columns(
            prepared,
            [
                ("pid", "pid"),
                ("usename", "usename"),
                ("client_hostname", "client_hostname"),
                ("state", "state"),
                ("sync_state", "sync_state"),
            ],
        )
    if prepared["title"] == "Transaction ID 年齡":
        headers = [str(header).casefold() for header in prepared["headers"]]
        if "txid_age" in headers:
            index = headers.index("txid_age")
            prepared["rows"] = sorted(
                prepared["rows"],
                key=lambda row: int(str(row[index]).replace(",", ""))
                if index < len(row) and str(row[index]).replace(",", "").isdigit()
                else -1,
                reverse=True,
            )[:10]
        else:
            prepared["rows"] = prepared["rows"][:10]
    if prepared["title"] == "罕用索引":
        headers = [
            str(header).casefold().replace("_", "").replace(" ", "")
            for header in prepared["headers"]
        ]
        scan_index = next(
            (
                index for index, header in enumerate(headers)
                if header in {"scan", "idxscan", "indexscan"}
            ),
            None,
        )
        if scan_index is not None:
            zero = []
            other = []
            for row in prepared["rows"]:
                value = row[scan_index] if scan_index < len(row) else ""
                (zero if str(value).strip().replace(",", "") == "0" else other).append(row)
            prepared["rows"] = (zero + other)[:10]
        else:
            prepared["rows"] = prepared["rows"][:10]
    return prepared


def _environment_nodes(model: ReportModel) -> list[dict[str, Any]]:
    values: dict[str, dict[str, str]] = {
        node["hostname"]: {} for node in model.nodes
    }
    os_section = next(
        (section for section in model.sections if section["section_id"] == "3"),
        None,
    )
    if os_section:
        for group in os_section["groups"]:
            for unit in group["units"]:
                headers = unit.get("headers") or []
                if not headers or headers[0] != "項目":
                    continue
                hosts = [str(header).splitlines()[0] for header in headers[1:]]
                for row in unit.get("rows") or []:
                    for host, value in zip(hosts, row[1:]):
                        values.setdefault(host, {})[str(row[0])] = str(value)

    result = []
    for node in model.nodes:
        host_values = values.get(node["hostname"], {})
        services = list(node.get("services") or [])
        if node["role"] in {"Primary", "Standby", "DR"}:
            database = PRODUCT_NAMES.get(model.product, model.product)
        elif any(service.casefold() == "pem" for service in services):
            # PEM Server requires its own backend database. It is infrastructure
            # inventory only and must never enter the target Primary-only scope.
            database = "PostgreSQL"
        else:
            database = ""
        result.append(
            {
                "hostname": node["hostname"],
                "role": node["role"],
                "os": host_values.get("作業系統", ""),
                "database": database,
                "cpu": (
                    f"{host_values['CPU Core 數']} cores"
                    if host_values.get("CPU Core 數")
                    else ""
                ),
                "ram": host_values.get("記憶體", ""),
                "service_ip": "",
                "components": services,
            }
        )
    return result


def _product_version(model: ReportModel) -> str:
    for section in model.sections:
        for group in section["groups"]:
            for unit in group["units"]:
                if unit["title"] != "版本資訊":
                    continue
                for row in unit.get("rows") or []:
                    if len(row) >= 2 and "version" in str(row[0]).casefold():
                        value = str(row[1])
                        match = re.search(r"\b(\d+(?:\.\d+)+)\b", value)
                        return match.group(1) if match else value
    return ""


def _monitoring_items(
    scope_ledger: dict, input_dir: Path, primary: str
) -> list[dict[str, Any]]:
    items = []
    title_counts: dict[str, int] = {}
    for entry in scope_ledger["evidence"]:
        if entry["evidence_domain"] != "monitoring" or entry["decision"] != "allowed":
            continue
        stem = Path(entry["path"]).stem.casefold()
        metric = next((key for key in MONITORING_TITLES if key in stem), "monitoring")
        title = MONITORING_TITLES.get(metric, "PEM 監控趨勢")
        title_counts[title] = title_counts.get(title, 0) + 1
        if title_counts[title] > 1:
            title = f"{title} {title_counts[title]}"
        items.append(
            {
                "title": title,
                "node": entry["node"] or primary,
                "evidence": {
                    "type": "image",
                    "path": str((input_dir / entry["path"]).resolve()),
                    "caption": f"{title}／{entry['node'] or primary}／當期監控區間",
                    "width_cm": 16.2,
                },
                "status": "待確認",
                "observation": "監控圖已完成節點與項目映射，趨勢仍需由工程師覆核\n結論：本項仍待確認",
                "recommendation": "依圖示期間確認尖峰、趨勢與告警門檻",
            }
        )
    return items


def build_v4_report(
    model: ReportModel,
    scope_ledger: dict,
    input_dir: Path,
) -> dict[str, Any]:
    """Return report JSON accepted by the approved V4 renderer."""
    primary = next(
        node["hostname"] for node in model.nodes if node["role"] == "Primary"
    )
    chapters = []
    for chapter_index, section in enumerate(model.sections, start=3):
        chapter_number = str(section.get("section_id") or chapter_index)
        report_sections = []
        for section_index, group in enumerate(section["groups"], start=1):
            number, title = _split_numbered_title(
                group["title"], f"{chapter_number}.{section_index}"
            )
            items = []
            for unit in group["units"]:
                unit = _prepare_unit(unit)
                if unit["title"] == "版本資訊" and model.product == "EPAS":
                    unit = {
                        **unit,
                        "rows": [
                            [
                                row[0],
                                re.sub(
                                    r"(?i)^PostgreSQL\s*",
                                    "EDB Postgres Advanced Server ",
                                    str(row[1]),
                                ),
                                *row[2:],
                            ]
                            if len(row) >= 2 and "version" in str(row[0]).casefold()
                            else row
                            for row in unit.get("rows") or []
                        ],
                    }
                rows = [list(row) for row in unit.get("rows") or []]
                if unit["title"] in {
                    "PEM / EFM 服務摘要",
                    "PEM / EFM / XDB 服務摘要",
                }:
                    configured = {
                        (node["hostname"], service)
                        for node in model.nodes
                        for service in node.get("services") or []
                    }
                    service_name = {
                        "PEM Server": "PEM",
                        "PEM Agent": "PEM",
                    }
                    relevant_configured = {
                        pair for pair in configured if pair[1] in {"PEM", "EFM", "XDB"}
                    }
                    if relevant_configured:
                        rows = [
                            row for row in rows
                            if len(row) >= 2
                            and (
                                row[0],
                                service_name.get(row[1], row[1]),
                            ) in relevant_configured
                        ][:10]
                    else:
                        rows = rows[:10]
                    unit = {**unit, "rows": rows}
                assessment_value = unit.get("assessment")
                if unit["title"] == "罕用索引" and assessment_value:
                    assessment_value = {
                        **assessment_value,
                        "observation": str(
                            assessment_value.get("observation", "")
                        ).replace("20 筆", "10 筆"),
                    }
                item = {
                    "title": unit["title"],
                    "evidence": _evidence(unit),
                    **_assessment(assessment_value),
                }
                if unit["title"] in INFORMATION_ONLY_TITLES:
                    item["assessment_display"] = False
                    item.pop("status", None)
                    item.pop("observation", None)
                    item.pop("recommendation", None)
                if chapter_number == "4":
                    item["node"] = primary
                if unit.get("omitted_rows"):
                    item["controlled_continuation"] = True
                if any(
                    token in unit["title"]
                    for token in ("pg_hba.conf", "postgresql.auto.conf")
                ):
                    item["controlled_continuation"] = True
                items.append(item)
            if chapter_number == "3" and number == "3.2":
                items.extend(_monitoring_items(scope_ledger, input_dir, primary))
            if items:
                report_sections.append(
                    {"number": number, "title": title, "items": items}
                )
        if report_sections:
            chapter = {
                "number": chapter_number,
                "title": section["title"],
                "sections": report_sections,
            }
            if chapter_number == "4":
                chapter["source_scope"] = "database"
            chapters.append(chapter)

    return {
        "customer": model.customer,
        "system_name": model.system_name,
        "period": model.period,
        "report_date": model.period,
        "engineer_name": model.engineer,
        "database_source_hostname": primary,
        "product": {
            "name": PRODUCT_NAMES.get(model.product, model.product),
            "version": _product_version(model),
        },
        "cover_company_name": "Omniwaresoft Tech",
        "maintenance_period": f"本次健檢期間：{model.period}",
        "purpose": [
            "確認各節點、作業系統與資料庫運行狀態",
            "檢查交易、權限、設定與容量風險",
            "提出可執行的改善建議",
        ],
        "nodes": _environment_nodes(model),
        "show_components": False,
        "architecture_image": None,
        "chapters": chapters,
        "version_updates": [],
        "summary": [],
    }
