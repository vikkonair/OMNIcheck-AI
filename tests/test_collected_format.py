from pathlib import Path

from omni_healthcheck.config import JobConfig
from omni_healthcheck.parsers import (
    HealthCheckOSLogParser,
    ParserContext,
)
from omni_healthcheck.topology import classify_evidence_domain, resolve_node


def collected_job() -> JobConfig:
    return JobConfig.model_validate(
        {
            "customer": "Sanitized",
            "period": "2026-06-16",
            "product": "EPAS",
            "first_healthcheck": False,
            "nodes": [
                {"hostname": "dbp1", "role": "Primary", "services": ["EFM"]},
                {"hostname": "dbp2", "role": "Standby", "services": ["EFM"]},
                {"hostname": "dbdr1", "role": "DR", "services": ["EFM"]},
                {"hostname": "dbwitness", "role": "Witness", "services": ["EFM"]},
                {"hostname": "pemp1", "role": "Witness", "services": ["PEM"]},
            ],
            "scope": {
                "include_os_from_all_nodes": True,
                "database_primary_only": True,
            },
            "report": {
                "template": "omni-v4",
                "output_docx": True,
                "output_pdf": True,
            },
            "ai": {"enabled": False, "provider": "disabled"},
        }
    )


def test_collected_filenames_override_generic_path_hints() -> None:
    assert (
        classify_evidence_domain(
            "20260616_PEM_check/20260616_DB_check.txt", ".txt"
        )
        == "database"
    )
    assert (
        classify_evidence_domain(
            "20260616_dbp1_check/HealthChekOS-LOG-dbp1-20260616.txt",
            ".txt",
        )
        == "os"
    )


def test_path_hostname_wins_over_hosts_file_content(tmp_path: Path) -> None:
    path = tmp_path / "HealthChekOS-LOG-dbp1-20260616.txt"
    path.write_text(
        "dbp1\ndbp2\ndbdr1\ndbwitness\n",
        encoding="utf-8",
    )

    resolution = resolve_node(
        path,
        "20260616_dbp1_check/HealthChekOS-LOG-dbp1-20260616.txt",
        collected_job(),
    )

    assert resolution.status == "resolved"
    assert resolution.hostname == "dbp1"
    assert resolution.sources == ["relative_path"]


def test_unique_service_directory_maps_pem_backend_to_pem_node(
    tmp_path: Path,
) -> None:
    path = tmp_path / "20260616_DB_check.txt"
    path.write_text("PostgreSQL 16.14\n", encoding="utf-8")

    resolution = resolve_node(
        path,
        "20260616_PEM_check/20260616_DB_check.txt",
        collected_job(),
    )

    assert resolution.hostname == "pemp1"
    assert resolution.role == "Witness"
    assert resolution.sources == ["service_path"]


def test_healthcheck_os_section_parser_supports_collected_format(
    tmp_path: Path,
) -> None:
    path = tmp_path / "HealthChekOS-LOG-dbp1-20260616.txt"
    path.write_text(
        """Job start
================ 主機名稱 ================
Example Hardware
dbp1
================ OS 版本 ================
Example Linux release 9.4
================ CPU Core 數 ================
96
================ RAM 大小 ================
MemTotal: 1024 kB
""",
        encoding="utf-8",
    )
    context = ParserContext(
        path=path,
        inventory_item={"sha256": "a" * 64},
        scope_item={
            "node": "dbp1",
            "node_role": "Primary",
            "evidence_domain": "os",
        },
        job=collected_job(),
    )

    checks = HealthCheckOSLogParser().parse(context)

    assert {check.check_id for check in checks} == {
        "hostname",
        "os_version",
        "cpu_count",
    }


def test_legacy_named_check_is_classified_by_database_content() -> None:
    content = """資料庫訊息查看
db_ver | PostgreSQL 16.6
List of databases
pg_stat_activity 查看
"""
    assert classify_evidence_domain("ENGDB_check.txt", ".txt", content) == "database"
