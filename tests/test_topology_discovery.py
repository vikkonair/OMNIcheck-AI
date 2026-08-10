from omni_healthcheck.topology_discovery import DiscoveryEvidence, discover_topology


def _item(path: str, text: str) -> DiscoveryEvidence:
    return DiscoveryEvidence(path=path, content=text.encode())


def test_discovery_proposes_standard_cluster_and_witness_services() -> None:
    result = discover_topology(
        [
            _item(
                "20260616_dbp1_check/HealthChekOS-LOG-dbp1-20260616.txt",
                "db.user=efm\nbind.address=efm1-primary:7800\nis.witness=false\n"
                "pgbackrest --stanza=edb backup --type=full",
            ),
            _item(
                "20260616_dbp2_check/HealthChekOS-LOG-dbp2-20260616.txt",
                "db.user=efm\nbind.address=efm2-standby:7800\nis.witness=false",
            ),
            _item(
                "20260616_dbdr1_check/HealthChekOS-LOG-dbdr1-20260616.txt",
                "primary_conninfo='host=dbp1'",
            ),
            _item(
                "20260616_witness_check/HealthChekOS-LOG-db-witness-20260616.txt",
                "db.user=efm\nbind.address=efm4-witness:7800\nis.witness=true",
            ),
            _item(
                "20260616_PEM_check/HealthChekOS-LOG-pemp1-20260616.txt",
                "Postgres Enterprise Manager\n=========== PEM Server ===========",
            ),
            DiscoveryEvidence(path="CPU.jpeg", content=b"image"),
        ]
    )

    assert result["can_confirm"] is True
    assert result["summary"] == {
        "node_count": 5,
        "primary_candidates": 1,
        "unresolved_nodes": 0,
        "unassigned_files": 1,
    }
    by_host = {node["hostname"]: node for node in result["nodes"]}
    assert by_host["dbp1"]["suggested_role"] == "Primary"
    assert by_host["dbp1"]["services"] == ["EFM", "pgBackRest"]
    assert by_host["dbp2"]["suggested_role"] == "Standby"
    assert by_host["dbdr1"]["suggested_role"] == "DR"
    assert by_host["db-witness"]["suggested_role"] == "Witness"
    assert by_host["pemp1"]["suggested_role"] == "Witness"
    assert by_host["pemp1"]["services"] == ["PEM"]


def test_discovery_fails_closed_when_primary_is_unknown() -> None:
    result = discover_topology(
        [_item("os/HealthChekOS-LOG-db01-20260616.txt", "hostname db01")]
    )

    assert result["can_confirm"] is False
    assert result["summary"]["primary_candidates"] == 0
    assert result["nodes"][0]["suggested_role"] == "Unknown"
    assert "必須確認" in result["warnings"][0]
