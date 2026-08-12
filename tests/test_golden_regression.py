import json
from pathlib import Path

import pytest

from omni_healthcheck.cli import run_generate


ROOT = Path(__file__).parents[1]
GOLDEN = ROOT / "tests/fixtures/golden"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_fixture(name: str, tmp_path: Path) -> tuple[dict, dict]:
    fixture = GOLDEN / name
    output = tmp_path / name
    assert run_generate(
        fixture / "job.yaml",
        fixture / "input",
        output,
    ) == 0
    return (
        {path.stem: _load(path) for path in output.glob("*.json")},
        _load(fixture / "expected.json"),
    )


def _items(report: dict) -> list[dict]:
    return [
        item
        for chapter in report["chapters"]
        for section in chapter["sections"]
        for item in section["items"]
    ]


def test_golden_manifest_records_contract_versions() -> None:
    manifest = _load(GOLDEN / "manifest.json")

    assert manifest == {
        "schema_version": "1.0",
        "fixture_version": "m8.1",
        "classification": "synthetic_and_sanitized",
        "contains_customer_evidence": False,
        "contracts": {
            "canonical_schema": "1.0",
            "pipeline": "0.6.0",
            "ruleset": "2026.1",
            "report_template": "omni-v4-m7.2",
            "v4_fixture": "jiuxing_v4",
            "monitoring_fixture": "globalwafers_pem",
            "scope_fixture": "multi_node_scope",
        },
    }


@pytest.mark.parametrize(
    "name",
    ["jiuxing_v4", "globalwafers_pem", "multi_node_scope"],
)
def test_golden_jobs_are_delivery_safe(name: str, tmp_path: Path) -> None:
    documents, expected = _run_fixture(name, tmp_path)

    assert documents["inventory"]["summary"]["total_files"] == expected[
        "inventory_total"
    ]
    assert documents["scope-ledger"]["summary"] == expected["scope"]
    assert documents["qa-result"]["delivery_allowed"] is True
    assert documents["v4-qa-result"]["delivery_allowed"] is True
    assert documents["normalized"]["schema_version"] == "1.0"
    assert documents["assessment"]["ruleset_version"] == "2026.4"
    assert documents["report-model"]["template_version"] == "omni-v4-m7.2"


def test_jiuxing_golden_preserves_approved_v4_contract(
    tmp_path: Path,
) -> None:
    documents, expected = _run_fixture("jiuxing_v4", tmp_path)
    normalized = documents["normalized"]
    report = documents["v4-report"]

    check_ids = {check["check_id"] for check in normalized["checks"]}
    assert set(expected["required_checks"]) <= check_ids
    assert report["database_source_hostname"] == expected["primary"]
    assert report["product"]["name"] == expected["product"]
    assert [chapter["title"] for chapter in report["chapters"]] == expected[
        "chapter_titles"
    ]
    assert report["show_components"] is expected["show_components"]
    assert all(
        item.get("node", expected["primary"]) == expected["primary"]
        for chapter in report["chapters"]
        if chapter.get("source_scope") == "database"
        for section in chapter["sections"]
        for item in section["items"]
    )


def test_globalwafers_golden_uses_primary_mapped_pem_output(
    tmp_path: Path,
) -> None:
    documents, expected = _run_fixture("globalwafers_pem", tmp_path)
    monitoring = next(
        item
        for item in documents["scope-ledger"]["evidence"]
        if item["evidence_domain"] == "monitoring"
    )
    image = next(
        item
        for item in _items(documents["v4-report"])
        if item["evidence"]["type"] == "image"
    )

    assert monitoring["node"] == expected["monitoring"]["node"]
    assert monitoring["resolution_sources"] == [
        expected["monitoring"]["resolution_source"]
    ]
    assert image["title"] == expected["monitoring"]["report_title"]
    assert image["node"] == expected["monitoring"]["node"]
    assert image["evidence"]["caption"].startswith(
        f"{expected['monitoring']['report_title']}／"
        f"{expected['monitoring']['node']}／"
    )

    witness = next(
        node
        for node in documents["topology"]["nodes"]
        if node["role"] == "Witness"
    )
    assert witness["services"] == expected["witness_services"]
    assert documents["v4-report"]["chapters"][-1]["title"] == expected[
        "service_chapter"
    ]
    backup = next(
        item
        for item in _items(documents["v4-report"])
        if item["title"] == expected["backup_title"]
    )
    assert backup["evidence"]["type"] == "text"
    assert "Provider: Barman" in backup["evidence"]["content"]
    assert "Last backup:" in backup["evidence"]["content"]
    assert backup["status"] == "正常"
    service_summary = next(
        item
        for item in _items(documents["v4-report"])
        if item["title"] == expected["service_summary_title"]
    )
    assert {
        (row[0], row[1])
        for row in service_summary["evidence"]["rows"]
    } == {
        ("pem-witness", "PEM Server"),
        ("pem-witness", "XDB"),
    }


def test_multi_node_golden_excludes_standby_and_dr_logical_database_output(
    tmp_path: Path,
) -> None:
    documents, expected = _run_fixture("multi_node_scope", tmp_path)
    normalized = documents["normalized"]
    comparison = documents["configuration-comparison"]
    report_text = json.dumps(documents["v4-report"], ensure_ascii=False)

    logical_database_nodes = sorted(
        {
            check["node"]
            for check in normalized["checks"]
            if check["product"] in {"PostgreSQL", "EPAS"}
            and check["check_id"]
            not in {"postgresql_conf", "postgresql_auto_conf", "pg_hba_conf"}
        }
    )
    configuration_nodes = sorted(
        {
            check["node"]
            for check in normalized["checks"]
            if check["check_id"]
            in {"postgresql_conf", "postgresql_auto_conf", "pg_hba_conf"}
        }
    )

    assert logical_database_nodes == expected["logical_database_nodes"]
    assert configuration_nodes == expected["configuration_nodes"]
    assert comparison["nodes"] == [
        "scope-primary",
        "scope-standby",
        "scope-dr",
    ]
    assert comparison["summary"]["different_parameters"] == 1
    assert all(value not in report_text for value in expected["forbidden_report_values"])
