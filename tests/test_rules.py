from pathlib import Path

from omni_healthcheck.rules import evaluate_rules, load_rules
from omni_healthcheck.schema import CheckResult, NormalizedDocument, TableEvidence, Trace


ROOT = Path(__file__).parents[1]


def check(
    check_id: str,
    headers: list[str],
    rows: list[list[str]],
    *,
    node: str = "primary",
    role: str = "Primary",
    product: str = "OS",
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        section_id="4.1",
        node=node,
        node_role=role,
        product=product,
        evidence=TableEvidence(headers=headers, rows=rows),
        trace=Trace(
            parser_id="test.rule.input.v1",
            evidence_sha256="a" * 64,
        ),
    )


def test_rule_engine_is_deterministic_and_evidence_backed() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "filesystem_usage",
                ["Output"],
                [["Filesystem Size Used Avail Use% Mounted"], ["/dev/sda 100G 91G 9G 91% /"]],
            ),
            check(
                "transaction_id_age",
                ["database", "txid_age"],
                [["app", "200000000"]],
                product="EPAS",
            ),
            check(
                "connections",
                ["Output"],
                [["idle_in_transaction_count"], ["1"]],
                product="EPAS",
            ),
            check(
                "replication_state",
                ["application_name", "state"],
                [["standby", "streaming"]],
                product="EPAS",
            ),
            check(
                "rarely_used_indexes",
                ["index", "idx_scan"],
                [["idx_a", "0"]],
                product="EPAS",
            ),
            check(
                "roles_privileges",
                [
                    "role_name",
                    "is_superuser",
                    "can_create_role",
                    "can_create_db",
                ],
                [
                    ["enterprisedb", "t", "t", "t"],
                    ["app_admin", "f", "f", "t"],
                ],
                product="EPAS",
            ),
            check(
                "postgresql_conf",
                ["Output"],
                [["shared_buffers = 8GB"]],
                product="EPAS",
            ),
            check(
                "postgresql_conf",
                ["Output"],
                [["shared_buffers = 4GB"]],
                node="standby",
                role="Standby",
                product="EPAS",
            ),
            check(
                "pg_hba_conf",
                ["Output"],
                [["host all all 0.0.0.0/0 trust"]],
                product="EPAS",
            ),
        ],
        unparsed_allowed_evidence=[],
    )
    comparison = {
        "parameter_comparisons": [
            {
                "configuration": "postgresql_conf",
                "parameter": "shared_buffers",
                "values": {"primary": "8GB", "standby": "4GB"},
                "status": "different",
            },
            {
                "configuration": "postgresql_auto_conf",
                "parameter": "primary_conninfo",
                "values": {"primary": "standby", "standby": "primary"},
                "status": "different",
            },
        ],
        "pg_hba": {
            "rules_by_node": {
                "primary": ["host all all 0.0.0.0/0 trust"],
                "standby": [],
            }
        },
    }
    rules = load_rules(ROOT / "config/rules.default.yaml")

    first = evaluate_rules(normalized, comparison, rules)
    second = evaluate_rules(normalized, comparison, rules)

    assert first == second
    assert first.summary == {
        "normal": 2,
        "attention": 4,
        "critical": 0,
        "pending": 2,
    }
    by_rule = {item.trace.rule_id: item for item in first.assessments}
    assert by_rule["os.filesystem_usage.v1"].status == "attention"
    assert by_rule["database.txid_age.v1"].status == "normal"
    assert by_rule["database.idle_in_transaction.v1"].status == "attention"
    assert by_rule["database.replication_state.v1"].status == "normal"
    assert by_rule["database.rarely_used_indexes.candidate.v1"].status == "pending"
    assert by_rule["database.roles_privileges.v1"].status == "pending"
    assert by_rule["database.configuration_consistency.v1"].status == "attention"
    assert by_rule["database.hba_trust.v1"].status == "attention"
    assert all(item.evidence_refs for item in first.assessments)
    assert all("\n結論：" in item.observation for item in first.assessments)
    assert all(item.recommendation for item in first.assessments)
    assert all(
        "primary_conninfo" not in item.observation for item in first.assessments
    )


def test_filesystem_observes_growth_from_50_and_attention_from_70() -> None:
    rules = load_rules(ROOT / "config/rules.default.yaml")

    def assess(usage: int):
        normalized = NormalizedDocument(
            pipeline_version="test",
            checks=[check("filesystem_usage", ["Output"], [[f"/dev/sda {usage}% /data"]])],
            unparsed_allowed_evidence=[],
        )
        return evaluate_rules(
            normalized,
            {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
            rules,
        ).assessments[0]

    below = assess(49)
    observe = assess(50)
    attention = assess(70)

    assert below.status == "normal"
    assert "隨時觀察量體成長速度" not in below.recommendation
    assert observe.status == "normal"
    assert "隨時觀察量體成長速度" in observe.recommendation
    assert attention.status == "attention"


def test_bloat_assessment_lists_every_top_ten_object_above_two() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "table_bloat",
                ["current_database", "schemaname", "tablename", "tbloat"],
                [
                    ["appdb", "public", "small", "1.9"],
                    ["appdb", "public", "orders", "8.5"],
                    ["appdb", "audit", "events", "3.1"],
                ],
                product="EPAS",
            ),
            check(
                "index_bloat",
                ["schemaname", "iname", "ibloat"],
                [["public", "idx_small", "2"], ["public", "idx_orders", "6.2"]],
                product="EPAS",
            ),
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )
    by_id = {item.check_id: item for item in result.assessments}

    table = by_id["table_bloat"]
    assert "appdb.public.orders（8.5）" in table.observation
    assert "appdb.audit.events（3.1）" in table.observation
    assert "small" not in table.observation
    assert "appdb.public.orders：VACUUM FULL" in table.recommendation
    assert "appdb.audit.events：VACUUM FULL" in table.recommendation

    index = by_id["index_bloat"]
    assert "public.idx_orders（6.2）" in index.observation
    assert "idx_small" not in index.observation
    assert "public.idx_orders：REINDEX" in index.recommendation


def test_barman_failure_is_assessed_without_primary_database_scope() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "backup_configuration",
                ["Output"],
                [["Provider: Barman"], ["backup maximum age: FAILED"]],
                node="backup-witness",
                role="Witness",
                product="Backup",
            )
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {
            "parameter_comparisons": [],
            "pg_hba": {"rules_by_node": {}},
        },
        load_rules(ROOT / "config/rules.default.yaml"),
    )

    assert len(result.assessments) == 1
    assessment = result.assessments[0]
    assert assessment.status == "attention"
    assert "Barman" in assessment.observation
    assert assessment.node == "backup-witness"


def test_pgbackrest_uses_primary_stanza_status_without_dr_pollution() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "backup_configuration",
                ["Output"],
                [
                    ["Provider: pgBackRest"],
                    ["stanza: edb"],
                    ["    status: ok"],
                    ["    full backup: 20260810-010000F"],
                    ["stanza: edbdr"],
                    ["    status: error (no valid backups)"],
                ],
                node="db-primary",
                role="Primary",
                product="Backup",
            )
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )

    assessment = result.assessments[0]
    assert assessment.status == "normal"
    assert "stanza `edb`" in assessment.observation
    assert "`status: ok`" in assessment.observation
    assert "edbdr=error (no valid backups)" in assessment.observation
    assert "還原驗證" in assessment.recommendation
    assert assessment.trace.rule_id == "os.backup_configuration.pgbackrest_stanza.v2"


def test_pgbackrest_primary_stanza_error_is_attention() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "backup_configuration",
                ["Output"],
                [["Provider: pgBackRest"], ["stanza: app"], ["status: error"]],
                product="Backup",
            )
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )

    assessment = result.assessments[0]
    assert assessment.status == "attention"
    assert "stanza `app`" in assessment.observation
    assert "最近成功備份" in assessment.recommendation


def test_pem_server_log_error_creates_actionable_assessment() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "pem_server_status",
                ["Output"],
                [["WARNING: probe execution error: schema monitor does not exist"]],
                node="pem-witness",
                role="Witness",
                product="PEM",
            )
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )

    assessment = result.assessments[0]
    assert assessment.status == "attention"
    assert "PEM Server" in assessment.observation
    assert "probe execution error" in assessment.observation
    assert "schema、function、權限" in assessment.recommendation
    assert assessment.trace.rule_id == "service.explicit_error.v1"


def test_capacity_slru_and_dead_tuple_sections_receive_evidence_based_narratives() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "largest_tables",
                ["database_name", "schemaname", "tablename", "table_size", "total_size_including_indexes"],
                [["app", "public", "orders", "80 GB", "120 GB"], ["app", "audit", "events", "40 GB", "60 GB"]],
                product="EPAS",
            ),
            check(
                "slru_status",
                ["name", "blks_hit", "blks_read"],
                [["Xact", "900", "100"], ["Subtrans", "90", "10"]],
                product="EPAS",
            ),
            check(
                "dead_tuples",
                ["schema_name", "table_name", "dead_tuples"],
                [["public", "orders", "6000000"], ["audit", "events", "2000000"]],
                product="EPAS",
            ),
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )
    by_id = {item.check_id: item for item in result.assessments}

    largest = by_id["largest_tables"]
    assert largest.status == "normal"
    assert "public.orders（含索引 120 GB）" in largest.observation
    assert "成長基準" in largest.recommendation

    slru = by_id["slru_status"]
    assert slru.status == "pending"
    assert "90.00%" in slru.observation
    assert "單次累積快照" in slru.observation
    assert "pg_stat_slru" in slru.recommendation

    dead = by_id["dead_tuples"]
    assert dead.status == "attention"
    assert "public.orders（6,000,000）" in dead.observation
    assert "VACUUM (ANALYZE)" in dead.recommendation
    assert dead.trace.rule_id == "database.dead_tuples.profile.v1"


def test_zero_row_database_locks_are_assessed_as_normal() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            check(
                "database_locks",
                ["結果"],
                [["0 rows（未發現項目）"]],
                product="PostgreSQL",
            )
        ],
        unparsed_allowed_evidence=[],
    )

    result = evaluate_rules(
        normalized,
        {"parameter_comparisons": [], "pg_hba": {"rules_by_node": {}}},
        load_rules(ROOT / "config/rules.default.yaml"),
    )

    assert result.assessments[0].trace.rule_id == "database.locks.v1"
    assert result.assessments[0].status == "normal"
