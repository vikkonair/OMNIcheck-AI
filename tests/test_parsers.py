from pathlib import Path

from omni_healthcheck.config import load_job
from omni_healthcheck.inventory import build_inventory
from omni_healthcheck.parsers import (
    OSSectionParser,
    ParserContext,
    PsqlReportParser,
    normalize_allowed_evidence,
)
from omni_healthcheck.schema import NormalizedDocument
from omni_healthcheck.topology import build_scope_ledger


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/multi_node"


def test_normalization_parses_allowed_os_and_primary_database_only() -> None:
    job = load_job(FIXTURE / "job.yaml")
    input_dir = FIXTURE / "input"
    inventory = build_inventory(input_dir, job)
    scope = build_scope_ledger(input_dir, inventory, job)

    document = normalize_allowed_evidence(input_dir, inventory, scope, job)
    serialized = document.model_dump(mode="json")
    validated = NormalizedDocument.model_validate(serialized)

    assert len(validated.checks) == 10
    assert {check.node_role for check in validated.checks} <= {
        "Primary",
        "Standby",
        "DR",
        "Witness",
    }
    database_checks = [
        check for check in validated.checks if check.product in {"PostgreSQL", "EPAS"}
    ]
    assert len(database_checks) == 1
    assert database_checks[0].node == "db-primary"
    assert database_checks[0].node_role == "Primary"
    assert database_checks[0].check_id == "database_version"
    assert database_checks[0].evidence.rows == [
        ["Database Version", "PostgreSQL 15.8"]
    ]
    assert all(check.assessment is None for check in validated.checks)
    assert all(check.trace.rule_id is None for check in validated.checks)


def test_normalization_tracks_allowed_but_unparsed_evidence_by_hash() -> None:
    job = load_job(FIXTURE / "job.yaml")
    input_dir = FIXTURE / "input"
    inventory = build_inventory(input_dir, job)
    scope = build_scope_ledger(input_dir, inventory, job)

    document = normalize_allowed_evidence(input_dir, inventory, scope, job)

    assert len(document.unparsed_allowed_evidence) == 2
    assert all(
        len(item.sha256) == 64 for item in document.unparsed_allowed_evidence
    )


def parser_context(
    path: Path,
    domain: str = "database",
    role: str = "Primary",
) -> ParserContext:
    return ParserContext(
        path=path,
        inventory_item={"sha256": "b" * 64},
        scope_item={
            "node": "db-primary",
            "node_role": role,
            "evidence_domain": domain,
        },
        job=load_job(FIXTURE / "job.yaml"),
    )


def test_os_sections_preserve_output_and_mask_inline_password(
    tmp_path: Path,
) -> None:
    path = tmp_path / "HealthChekOS-LOG-db-primary.txt"
    path.write_text(
        """========== OS 磁碟設備類型 ==========
NAME ROTA TYPE
sda 0 disk
========== postgresql.auto.conf ==========
primary_conninfo = 'host=db-standby password=secret port=5432'
""",
        encoding="utf-8",
    )

    checks = OSSectionParser().parse(parser_context(path, "os"))
    by_id = {check.check_id: check for check in checks}

    assert by_id["disk_devices"].evidence.rows == [
        ["NAME ROTA TYPE"],
        ["sda 0 disk"],
    ]
    rendered = by_id["postgresql_auto_conf"].evidence.rows[0][0]
    assert "secret" not in rendered
    assert "password=***MASKED***" in rendered


def test_os_sections_parse_node_local_db_config_from_standby(
    tmp_path: Path,
) -> None:
    path = tmp_path / "HealthChekOS-LOG-db-standby.txt"
    path.write_text(
        """========== CPU 型號 ==========
Example CPU
========== postgresql.auto.conf ==========
primary_conninfo = 'host=db-primary password=secret'
========== pg_hba.conf ==========
host all all 10.0.0.0/8 scram-sha-256
""",
        encoding="utf-8",
    )

    checks = OSSectionParser().parse(parser_context(path, "os", "Standby"))

    assert {check.check_id for check in checks} == {
        "cpu_model",
        "postgresql_auto_conf",
        "pg_hba_conf",
    }


def test_os_sections_reject_pem_backend_config_from_witness(
    tmp_path: Path,
) -> None:
    path = tmp_path / "HealthChekOS-LOG-pem-witness.txt"
    path.write_text(
        """========== postgresql ==========
shared_buffers = 1GB
========== pg_hba.conf ==========
host all all 10.0.0.0/8 scram-sha-256
========== PEM Server ==========
active
""",
        encoding="utf-8",
    )

    checks = OSSectionParser().parse(parser_context(path, "os", "Witness"))

    assert {check.check_id for check in checks} == {"pem_server_status"}


def test_psql_report_parser_applies_fixed_row_policies(tmp_path: Path) -> None:
    schema_rows = "\n".join(
        f" schema{i} | role{i} | USAGE" for i in range(25)
    )
    rare_rows = "\n".join(
        f" public | table{i} | idx{i} | {0 if i % 3 == 0 else i}"
        for i in range(25)
    )
    path = tmp_path / "DB_check.txt"
    path.write_text(
        f"""Schema 權限列表
 schema | role | privileges
--------+------+-----------
{schema_rows}
(25 rows)
罕用索引可能清單
 schemaname | tablename | indexname | idx_scan
------------+-----------+-----------+---------
{rare_rows}
(25 rows)
最後 AutoVacuum 執行時間清單
 schemaname | relname | last_autovacuum
------------+---------+----------------
 public | app | yesterday
(1 row)
pg_hba 設定
 type | database | user_name | address | auth_method
------+----------+-----------+---------+------------
 host | all | app | 10.0.0.0/8 | scram-sha-256
 local | all | all |  | peer
(2 rows)
""",
        encoding="utf-8",
    )

    checks = PsqlReportParser().parse(parser_context(path))
    by_id = {check.check_id: check for check in checks}

    assert len(by_id["schema_privileges"].evidence.rows) == 20
    assert len(by_id["rarely_used_indexes"].evidence.rows) == 20
    scan_index = by_id["rarely_used_indexes"].evidence.headers.index("idx_scan")
    assert by_id["rarely_used_indexes"].evidence.rows[0][scan_index] == "0"
    assert "pg_hba_conf" not in by_id
    assert "last_autovacuum" not in by_id
