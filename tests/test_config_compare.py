from omni_healthcheck.config_compare import build_configuration_comparison
from omni_healthcheck.schema import CheckResult, NormalizedDocument, TableEvidence, Trace


def config_check(
    node: str,
    role: str,
    check_id: str,
    lines: list[str],
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        section_id="4.13",
        node=node,
        node_role=role,
        product="EPAS",
        evidence=TableEvidence(
            headers=["Output"],
            rows=[[line] for line in lines],
        ),
        trace=Trace(
            parser_id="test.config.v1",
            evidence_sha256="c" * 64,
        ),
    )


def test_configuration_comparison_reports_matching_different_and_missing() -> None:
    normalized = NormalizedDocument(
        pipeline_version="test",
        checks=[
            config_check(
                "primary",
                "Primary",
                "postgresql_conf",
                ["shared_buffers = 8GB", "max_connections = 500"],
            ),
            config_check(
                "standby",
                "Standby",
                "postgresql_conf",
                ["shared_buffers = 8GB", "max_connections = 300"],
            ),
            config_check(
                "dr",
                "DR",
                "postgresql_conf",
                ["shared_buffers = 8GB"],
            ),
            config_check(
                "primary",
                "Primary",
                "pg_hba_conf",
                ["host all app 10.0.0.0/8 scram-sha-256"],
            ),
            config_check(
                "standby",
                "Standby",
                "pg_hba_conf",
                [
                    "host all app 10.0.0.0/8 scram-sha-256",
                    "host replication rep 10.1.0.0/16 scram-sha-256",
                ],
            ),
            config_check(
                "dr",
                "DR",
                "pg_hba_conf",
                ["host all app 10.0.0.0/8 scram-sha-256"],
            ),
            config_check(
                "pem",
                "Witness",
                "postgresql_conf",
                ["shared_buffers = 1GB"],
            ),
        ],
        unparsed_allowed_evidence=[],
    )
    topology = {
        "nodes": [
            {"hostname": "primary", "role": "Primary"},
            {"hostname": "standby", "role": "Standby"},
            {"hostname": "dr", "role": "DR"},
            {"hostname": "pem", "role": "Witness"},
        ]
    }

    comparison = build_configuration_comparison(normalized, topology)
    by_parameter = {
        item["parameter"]: item for item in comparison["parameter_comparisons"]
    }

    assert comparison["nodes"] == ["primary", "standby", "dr"]
    assert by_parameter["shared_buffers"]["status"] == "matching"
    assert by_parameter["max_connections"]["status"] == "missing"
    assert comparison["pg_hba"]["common_rules"] == [
        "host all app 10.0.0.0/8 scram-sha-256"
    ]
    assert comparison["pg_hba"]["unique_rules_by_node"]["standby"] == [
        "host replication rep 10.1.0.0/16 scram-sha-256"
    ]
    assert "pem" not in comparison["pg_hba"]["rules_by_node"]
