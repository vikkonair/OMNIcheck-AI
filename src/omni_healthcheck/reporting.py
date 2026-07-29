"""Customer-safe, versioned report assembly."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from omni_healthcheck.config import JobConfig
from omni_healthcheck.rules import AssessmentDocument
from omni_healthcheck.schema import NormalizedDocument


CHECK_TITLES = {
    "hostname": "主機名稱",
    "os_version": "作業系統版本",
    "kernel_version": "Kernel 版本",
    "cpu_count": "CPU Core 數",
    "cpu_model": "CPU 型號",
    "memory_total_kb": "記憶體",
    "swap_total_kb": "Swap",
    "filesystem_usage": "檔案系統使用率",
    "process_state": "程序狀態",
    "network_listeners": "網路連線",
    "hugepage_settings": "HugePages 設定",
    "selinux_status": "SELinux 狀態",
    "firewall_status": "防火牆狀態",
    "efm_status": "EFM 狀態",
    "pem_agent_status": "PEM Agent 狀態",
    "pem_server_status": "PEM Server 狀態",
    "xdb_status": "XDB 狀態",
    "backup_configuration": "備份狀態",
    "database_version": "資料庫版本",
    "database_inventory": "資料庫清單",
    "extensions": "Extension 清單",
    "roles_privileges": "資料庫帳號權限",
    "schema_privileges": "Schema 權限",
    "connections": "連線狀態",
    "transaction_id_age": "Transaction ID 年齡",
    "database_locks": "Lock 狀態",
    "replication_state": "資料庫同步狀態",
    "pg_hba_conf": "pg_hba.conf",
    "postgresql_conf": "postgresql.conf",
    "postgresql_auto_conf": "postgresql.auto.conf",
    "dead_tuples": "Dead Tuple",
    "table_bloat": "Table Bloat",
    "index_bloat": "Index Bloat",
    "rarely_used_indexes": "罕用索引",
}
STATUS_LABELS = {
    "normal": "正常",
    "attention": "注意",
    "critical": "嚴重",
    "pending": "待確認",
}
REPORT_ROW_LIMITS = {
    "process_state": 30,
    "pem_agent_status": 30,
    "pem_server_status": 30,
    "efm_status": 40,
    "network_listeners": 40,
    "backup_configuration": 40,
}
DEFAULT_REPORT_ROW_LIMIT = 100
COMPLETE_INVENTORIES = {"pg_hba_conf", "postgresql_auto_conf"}


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    template_version: str = "omni-v4-m7.2"
    customer: str
    system_name: str | None
    period: str
    engineer: str
    product: str
    nodes: list[dict]
    summary: dict
    sections: list[dict]
    findings: list[dict]
    coverage: dict
    cve: dict


def build_report_model(
    job: JobConfig,
    topology: dict,
    normalized: NormalizedDocument,
    assessment: AssessmentDocument,
    coverage: dict,
    configuration_comparison: dict,
) -> ReportModel:
    checks = {(c.node.casefold(), c.check_id): c for c in normalized.checks}
    assessments = {}
    for item in assessment.assessments:
        for ref in item.evidence_refs:
            assessments.setdefault((item.node.casefold(), ref.check_id), item)

    def find(node: str, check_id: str):
        return checks.get((node.casefold(), check_id))

    def value(node: str, check_id: str) -> str:
        check = find(node, check_id)
        if not check:
            return "-"
        rows = check.evidence.rows
        lines = [" ".join(row).strip() for row in rows]
        if check_id in {"memory_total_kb", "swap_total_kb"} and rows:
            try:
                return f"{int(rows[0][-1]) / 1048576:.1f} GB"
            except ValueError:
                pass
        if check_id == "firewall_status":
            active = next((line for line in lines if "Active:" in line), "")
            return "啟用" if "active (running)" in active else "未啟用"
        if check_id == "selinux_status":
            status = next((line for line in lines if "SELinux status:" in line), "")
            return status.partition(":")[2].strip() or "-"
        if check_id == "hugepage_settings":
            values = {
                line.partition(":")[0]: line.partition(":")[2].strip()
                for line in lines if ":" in line
            }
            return f"Total {values.get('HugePages_Total', '-')}; Free {values.get('HugePages_Free', '-')}"
        if check_id == "cron_configuration":
            jobs = [
                line for line in lines
                if line and not line.startswith(("#", "no crontab", "crontab:"))
            ]
            return f"{len(jobs)} 項排程" if jobs else "無排程"
        if len(check.evidence.headers) == 2 and rows:
            return "；".join(row[1] for row in rows[:3])
        return "；".join(" ".join(row) for row in rows[:3])

    def assessment_dict(item):
        if not item:
            return None
        return {
            "status": item.status,
            "status_label": STATUS_LABELS[item.status],
            "observation": item.observation,
            "recommendation": item.recommendation,
        }

    def unit(node: str, check_id: str, title: str | None = None, extra_observation=""):
        check = find(node, check_id)
        if not check:
            return None
        limit = (
            len(check.evidence.rows)
            if check_id in COMPLETE_INVENTORIES
            else REPORT_ROW_LIMITS.get(check_id, DEFAULT_REPORT_ROW_LIMIT)
        )
        def redact(value: str) -> str:
            value = re.sub(r"(?i)(pass(?:word)?[=:]\s*)[^\s'\";]+", r"\1[REDACTED]", value)
            return re.sub(r"(?i)(-pass\s+pass:)[^\s'\";]+", r"\1[REDACTED]", value)

        rows = [[redact(value) for value in row] for row in check.evidence.rows[:limit]]
        finding = assessment_dict(assessments.get((node.casefold(), check_id)))
        if finding and extra_observation:
            finding["observation"] = f"{finding['observation']} {extra_observation}"
        elif extra_observation:
            finding = {
                "status": "attention",
                "status_label": STATUS_LABELS["attention"],
                "observation": extra_observation,
                "recommendation": "請確認差異是否屬於角色必要設定；效能與安全相關參數建議維持一致，並保留核准紀錄。",
            }
        return {
            "title": title or CHECK_TITLES.get(check_id, check_id),
            "headers": check.evidence.headers,
            "rows": rows,
            "omitted_rows": len(check.evidence.rows) - len(rows),
            "assessment": finding,
        }

    node_rows = topology["nodes"]
    os_headers = ["項目"] + [
        f"{node['hostname']}\n{node['role']}" for node in node_rows
    ]
    os_items = [
        ("主機名稱", "hostname"),
        ("作業系統", "os_version"),
        ("CPU 型號", "cpu_model"),
        ("CPU Core 數", "cpu_count"),
        ("記憶體", "memory_total_kb"),
        ("Swap", "swap_total_kb"),
        ("防火牆", "firewall_status"),
        ("SELinux", "selinux_status"),
        ("HugePages", "hugepage_settings"),
        ("Cron", "cron_configuration"),
    ]
    os_rows = [
        [label] + [value(node["hostname"], check_id) for node in node_rows]
        for label, check_id in os_items
    ]
    os_matrix = {
        "title": "主機與作業系統組態彙整",
        "headers": os_headers,
        "rows": os_rows,
        "omitted_rows": 0,
        "assessment": None,
    }
    fs_rows = []
    fs_findings = []
    for node in node_rows:
        check = find(node["hostname"], "filesystem_usage")
        if check:
            for row in check.evidence.rows:
                values = row[0].split()
                if values and values[0] != "Filesystem" and len(values) >= 6:
                    fs_rows.append([node["hostname"], *values[:5], " ".join(values[5:])])
        finding = assessments.get((node["hostname"].casefold(), "filesystem_usage"))
        if finding:
            fs_findings.append(finding)
    worst = max(fs_findings, key=lambda x: ("normal", "pending", "attention", "critical").index(x.status), default=None)
    fs_assessment = assessment_dict(worst)
    if fs_assessment:
        fs_assessment["observation"] = "各節點檔案系統已集中檢視。" + fs_assessment["observation"]
    fs_unit = {
        "title": "檔案系統容量",
        "headers": ["節點", "Filesystem", "Size", "Used", "Avail", "Use%", "Mounted on"],
        "rows": fs_rows,
        "omitted_rows": 0,
        "assessment": fs_assessment,
    }

    primary = next(
        (node["hostname"] for node in node_rows if node["role"] == "Primary"), ""
    )
    hba = configuration_comparison["pg_hba"]
    unique = hba["unique_rules_by_node"]
    hba_note = (
        f"跨節點比較：Primary、Standby、DR 共有 {len(hba['common_rules'])} 條共同規則；"
        + "，".join(f"{node} 有 {len(rules)} 條特有規則" for node, rules in unique.items())
        + "。"
    )

    def config_note(check_id: str) -> str:
        items = [
            item for item in configuration_comparison["parameter_comparisons"]
            if item["configuration"] == check_id
        ]
        counts = {
            status: sum(item["status"] == status for item in items)
            for status in ("matching", "different", "missing")
        }
        return (
            "跨節點比較："
            f"{counts['matching']} 項一致、{counts['different']} 項值不同、"
            f"{counts['missing']} 項僅部分節點出現。"
        )

    def compact_units(specs):
        return [item for spec in specs if (item := unit(*spec))]

    hba_unit = unit(primary, "pg_hba_conf", "Primary pg_hba.conf", hba_note)
    conf_unit = unit(primary, "postgresql_conf", "Primary postgresql.conf", config_note("postgresql_conf"))
    auto_unit = unit(primary, "postgresql_auto_conf", "Primary postgresql.auto.conf", config_note("postgresql_auto_conf"))

    pem_rows = []
    for node in node_rows:
        for check_id, label in (
            ("efm_status", "EFM"),
            ("pem_agent_status", "PEM Agent"),
            ("pem_server_status", "PEM Server"),
            ("xdb_status", "XDB"),
        ):
            check = find(node["hostname"], check_id)
            if check:
                sample = "；".join(" ".join(row) for row in check.evidence.rows[:2])
                pem_rows.append([node["hostname"], label, sample])

    primary_backup_units = []
    supporting_backup_units = []
    for check in normalized.checks:
        if check.check_id != "backup_configuration":
            continue
        provider = next(
            (
                row[0].partition(":")[2].strip()
                for row in check.evidence.rows
                if row and row[0].casefold().startswith("provider:")
            ),
            "Backup",
        )
        is_primary_backup = check.node.casefold() == primary.casefold()
        backup_unit = unit(
            check.node,
            "backup_configuration",
            (
                f"{provider} 備份狀態"
                if is_primary_backup
                else f"{provider} 備份狀態（{check.node}）"
            ),
        )
        if backup_unit:
            (
                primary_backup_units
                if is_primary_backup
                else supporting_backup_units
            ).append(backup_unit)

    has_xdb = any(
        "XDB" in node.get("services", [])
        for node in node_rows
    )

    sections = [
        {
            "section_id": "3",
            "title": "作業系統健檢",
            "groups": [
                {"title": "3.1 主機與組態設定", "units": [os_matrix]},
                {"title": "3.2 系統資源與容量", "units": [fs_unit]},
            ],
        },
        {
            "section_id": "4",
            "title": "PostgreSQL 資料庫健檢",
            "groups": [
                {"title": "4.1 資料庫組態設定", "units": compact_units([
                    (primary, "database_version", "版本資訊"),
                    (primary, "extensions", "Extension 清單"),
                    (primary, "database_inventory", "資料庫清單"),
                ]) + [x for x in (hba_unit, conf_unit, auto_unit) if x]},
                {"title": "4.2 運行與效能狀態", "units": compact_units([
                    (primary, "connections", "連線狀態"),
                    (primary, "transaction_id_age", "Transaction ID 年齡"),
                    (primary, "checkpoint_activity", "Checkpoint 狀態"),
                    (primary, "slru_status", "SLRU 狀態"),
                    (primary, "largest_tables", "資料量與大型資料表"),
                    (primary, "dead_tuples", "Dead Tuple"),
                    (primary, "table_bloat", "Table Bloat"),
                    (primary, "index_bloat", "Index Bloat"),
                    (primary, "rarely_used_indexes", "罕用索引"),
                    (primary, "replication_state", "同步狀態"),
                ]) + primary_backup_units},
                {"title": "4.3 權限與 Schema", "units": compact_units([
                    (primary, "roles_privileges", "資料庫帳號權限"),
                    (primary, "schema_privileges", "Schema 權限"),
                    (primary, "schema_default_privileges", "Schema Default Privileges"),
                ])},
            ],
        },
        {
            "section_id": "5",
            "title": "PEM、EFM 與 XDB" if has_xdb else "PEM 與 EFM",
            "groups": [
                {"title": "5.1 服務狀態彙整", "units": [{
                    "title": (
                        "PEM / EFM / XDB 服務摘要"
                        if has_xdb
                        else "PEM / EFM 服務摘要"
                    ),
                    "headers": ["節點", "服務", "摘要"],
                    "rows": pem_rows,
                    "omitted_rows": 0,
                    "assessment": None,
                }]},
                *(
                    [{
                        "title": "5.2 備份服務狀態",
                        "units": supporting_backup_units,
                    }]
                    if supporting_backup_units
                    else []
                ),
            ],
        },
    ]
    findings = [
        {
            "section_id": item.section_id,
            "check_id": item.check_id,
            "title": CHECK_TITLES.get(item.check_id, item.check_id),
            "node": item.node,
            "status": item.status,
            "status_label": STATUS_LABELS[item.status],
            "observation": item.observation,
            "recommendation": item.recommendation,
        }
        for item in assessment.assessments
        if item.status != "normal"
    ]
    return ReportModel(
        customer=job.customer,
        system_name=job.system_name,
        period=job.period,
        engineer=job.engineer or "XXX",
        product=job.product,
        nodes=topology["nodes"],
        summary=assessment.summary,
        sections=sections,
        findings=findings,
        coverage=coverage["summary"],
        cve={
            "status": "pending",
            "version_summary": [],
            "fixable": [],
            "message": "尚未接入權威 CVE 資料來源，本節保留為待確認。",
        },
    )
