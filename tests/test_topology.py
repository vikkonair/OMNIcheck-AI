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


def test_unresolved_monitoring_image_defaults_to_primary(tmp_path: Path) -> None:
    job = load_job(FIXTURE / "job.yaml")
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "CPU.jpeg").write_bytes(b"monitoring-image")

    inventory = build_inventory(input_dir, job)
    ledger = build_scope_ledger(input_dir, inventory, job)
    item = ledger["evidence"][0]

    assert item["evidence_domain"] == "monitoring"
    assert item["node"] == "db-primary"
    assert item["node_role"] == "Primary"
    assert item["resolution_status"] == "resolved"
    assert item["resolution_sources"] == [
        "policy.monitoring_images_default_to_primary"
    ]
    assert item["decision"] == "allowed"


def test_topology_records_operator_confirmed_discovery() -> None:
    job = load_job(FIXTURE / "job.yaml")
    raw = job.model_dump(mode="json")
    raw["topology_confirmation"] = {
        "source": "deterministic_discovery",
        "confirmed": True,
        "discovery_schema_version": "1.0",
        "nodes": [
            {
                "hostname": node["hostname"],
                "suggested_role": node["role"],
                "confidence": "high",
                "role_evidence": [],
                "conflicts": [],
            }
            for node in raw["nodes"]
        ],
    }
    raw["topology_confirmation"]["nodes"][0]["suggested_role"] = "Unknown"
    from omni_healthcheck.config import JobConfig

    topology = build_topology(JobConfig.model_validate(raw))

    assert topology["primary"]["confirmation_source"] == (
        "operator_confirmed_discovery"
    )
    assert all(
        node["role_source"] == "operator_confirmed_discovery"
        for node in topology["nodes"]
    )
