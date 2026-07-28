from pathlib import Path

from omni_healthcheck.config import load_job
from omni_healthcheck.inventory import build_inventory
from omni_healthcheck.parsers import normalize_allowed_evidence
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
