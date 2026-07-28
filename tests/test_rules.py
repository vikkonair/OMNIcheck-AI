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
        "attention": 3,
        "critical": 1,
        "pending": 2,
    }
    by_rule = {item.trace.rule_id: item for item in first.assessments}
    assert by_rule["os.filesystem_usage.v1"].status == "critical"
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
