from pathlib import Path

from omni_healthcheck.config import load_job
from omni_healthcheck.inventory import build_inventory
from omni_healthcheck.topology import build_scope_ledger, build_topology


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/multi_node"


def test_topology_has_one_confirmed_primary() -> None:
    job = load_job(FIXTURE / "job.yaml")
    topology = build_topology(job)

    assert topology["primary"] == {
        "hostname": "db-primary",
        "confirmed": True,
        "confirmation_source": "job_config",
    }
    assert [node["role"] for node in topology["nodes"]] == [
        "Primary",
        "Standby",
        "DR",
        "Witness",
    ]
    witness = next(node for node in topology["nodes"] if node["role"] == "Witness")
    assert witness["services"] == ["PEM", "EFM"]
    assert witness["os_evidence_allowed"] is True
    assert witness["target_database_evidence_allowed"] is False


def test_scope_allows_all_os_and_only_primary_database() -> None:
    job = load_job(FIXTURE / "job.yaml")
    input_dir = FIXTURE / "input"
    inventory = build_inventory(input_dir, job)
    ledger = build_scope_ledger(input_dir, inventory, job)
    by_path = {item["path"]: item for item in ledger["evidence"]}

    assert by_path["os/db-primary/host.txt"]["decision"] == "allowed"
    assert by_path["os/db-standby/host.txt"]["decision"] == "allowed"
    assert by_path["os/db-dr/host.txt"]["decision"] == "allowed"
    assert by_path["os/pem-witness/host.txt"]["decision"] == "allowed"
    assert by_path["monitoring/pem-witness/cpu.png"]["decision"] == "allowed"
    assert by_path["db/db-primary/connections.sql"]["decision"] == "allowed"
    assert by_path["db/db-standby/connections.sql"]["decision"] == "excluded"
    assert by_path["db/db-dr/connections.sql"]["decision"] == "excluded"
    assert by_path["db/pem-witness/pem_backend.sql"]["decision"] == "excluded"
    assert "not Primary" in by_path["db/pem-witness/pem_backend.sql"]["reason"]
    assert by_path["db/unresolved.sql"]["decision"] == "pending"
    assert by_path["os/ambiguous.txt"]["resolution_status"] == "ambiguous"
    assert by_path["os/ambiguous.txt"]["decision"] == "pending"
    assert ledger["summary"] == {"allowed": 7, "excluded": 3, "pending": 2}
