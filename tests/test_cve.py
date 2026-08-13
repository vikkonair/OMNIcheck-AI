from __future__ import annotations

from datetime import UTC, datetime, timedelta

from omni_healthcheck.cve import CVECacheStore, MATCHER_VERSION, parse_product_versions
from omni_healthcheck.cve_sync import (
    _edb_advisory_snapshot,
    _postgresql_security_snapshot,
    import_snapshot,
    nvd_enrichment,
    postgresql_release_snapshot,
)
from omni_healthcheck.schema import CheckResult, NormalizedDocument, TableEvidence, Trace


def normalized(version: str = "16.4", product: str = "EPAS") -> NormalizedDocument:
    return NormalizedDocument(checks=[CheckResult(
        check_id="database_version", section_id="4.1", node="db-primary",
        node_role="Primary", product=product, evidence=TableEvidence(
            headers=["Metric", "Value"], rows=[["Database Version", f"EDB Postgres Advanced Server {version}" if product == "EPAS" else f"PostgreSQL {version}"]],
        ), trace=Trace(parser_id="test", evidence_sha256="a" * 64),
    )], unparsed_allowed_evidence=[], pipeline_version="test")


def test_parser_is_primary_only_and_supports_non_17_versions() -> None:
    versions = parse_product_versions(normalized("15.7"))
    assert [(item.product_id, item.installed_version) for item in versions] == [("epas", "15.7")]


def test_parser_keeps_canonical_epas_product_when_version_text_says_postgresql() -> None:
    document = normalized("16.14")
    document.checks[0].evidence.rows[0][1] = "PostgreSQL 16.14"
    versions = parse_product_versions(document)
    assert [(item.product_id, item.installed_version) for item in versions] == [("epas", "16.14")]


def test_cache_matcher_is_deterministic_and_report_has_required_cve_metadata(tmp_path) -> None:
    store = CVECacheStore(f"sqlite+pysqlite:///{tmp_path / 'cve.sqlite'}")
    store.create_schema_for_test()
    sync = store.import_snapshot(
        product_id="epas", source_key="edb_security",
        releases=[{"version": "15.8", "source_url": "https://example.invalid/epas-15-8"}],
        cves=[{
            "cve_id": "CVE-2026-0001", "summary": "測試修補項目", "affected_from": "15.0", "affected_before": "15.8", "fixed_versions": ["15.8"],
            "cvss_score": 8.1, "severity": "HIGH", "cvss_version": "3.1", "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
        }, {
            "cve_id": "CVE-2026-0002", "summary": "已修補項目", "affected_from": "15.0", "affected_before": "15.6", "fixed_versions": ["15.6"],
            "cvss_score": 5.0, "severity": "MEDIUM", "cvss_version": "3.1", "cvss_vector": "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L",
        }],
    )
    matches = store.match_job(job_id="a" * 32, normalized=normalized("15.7"))
    assert sync["cve_count"] == 2
    assert {row["cve_id"]: row["match_status"] for row in matches} == {
        "CVE-2026-0001": "applicable", "CVE-2026-0002": "fixed",
    }
    assert all(row["matcher_version"] == MATCHER_VERSION for row in matches)
    report = store.report_section(job_id="a" * 32)
    assert report["status"] == "ready"
    cve = report["version_updates"][0]["cves"][0]
    assert cve["id"] == "CVE-2026-0001"
    assert {"cvss_score", "severity", "cvss_version", "vector", "score_source", "match_status", "fixed_version"} <= cve.keys()


def test_stale_cache_blocks_formal_delivery(tmp_path) -> None:
    store = CVECacheStore(f"sqlite+pysqlite:///{tmp_path / 'stale.sqlite'}")
    store.create_schema_for_test()
    store.import_snapshot(product_id="postgresql", source_key="postgresql_security", releases=[], cves=[{
        "cve_id": "CVE-2026-1000", "summary": "stale", "affected_from": "16.0", "affected_before": "16.5", "fixed_versions": ["16.5"],
    }])
    store.match_job(job_id="b" * 32, normalized=normalized("16.4", "PostgreSQL"))
    with store.engine.begin() as connection:
        from omni_healthcheck.cve import job_cve_matches
        connection.execute(job_cve_matches.update().values(source_snapshot_at=datetime.now(UTC) - timedelta(days=15)))
    section = store.report_section(job_id="b" * 32, stale_after_days=14)
    assert section["status"] == "stale"
    assert section["delivery_allowed"] is False


def test_epas_upstream_postgresql_cve_is_not_reported_as_confirmed(tmp_path) -> None:
    store = CVECacheStore(f"sqlite+pysqlite:///{tmp_path / 'inherit.sqlite'}")
    store.create_schema_for_test()
    store.import_snapshot(product_id="postgresql", source_key="postgresql_security", releases=[], cves=[{
        "cve_id": "CVE-2026-2000", "summary": "upstream only", "affected_from": "15.0",
        "affected_before": "15.9", "fixed_versions": ["15.9"],
    }])
    matches = store.match_job(job_id="c" * 32, normalized=normalized("15.7"))
    assert matches[0]["match_status"] == "potentially_applicable"
    assert "EDB" in matches[0]["match_reason"]


def test_latest_minor_suppresses_historical_cves_and_ignores_generic_nvd(tmp_path) -> None:
    store = CVECacheStore(f"sqlite+pysqlite:///{tmp_path / 'latest.sqlite'}")
    store.create_schema_for_test()
    store.import_snapshot(
        product_id="epas", source_key="edb_security",
        releases=[{"version": "16.14"}],
        cves=[{
            "cve_id": "CVE-2026-3001", "summary": "old EPAS fix",
            "affected_from": "16.0", "affected_before": "16.14",
            "fixed_versions": ["16.14"],
        }],
    )
    # It is valid knowledge data, but NVD is never a server applicability
    # source.  It intentionally has no version range.
    store.import_snapshot(
        product_id="postgresql", source_key="nvd", releases=[], cves=[{
            "cve_id": "CVE-2026-3999", "summary": "unrelated package",
            "affected_from": "", "affected_before": "", "fixed_versions": [],
        }],
    )
    store.match_job(job_id="d" * 32, normalized=normalized("16.14"))
    report = store.report_section(job_id="d" * 32)
    update = report["version_updates"][0]
    assert update["current"] == "EDB Postgres Advanced Server 16.14"
    assert update["recommended"] == "EDB Postgres Advanced Server 16.14"
    assert update["cves"] == []
    assert "最新維護版本" in update["summary"]


def test_major_eol_within_one_year_is_reported(tmp_path) -> None:
    store = CVECacheStore(f"sqlite+pysqlite:///{tmp_path / 'eol.sqlite'}")
    store.create_schema_for_test()
    store.import_snapshot(
        product_id="postgresql", source_key="postgresql_security",
        releases=[{"version": "14.23"}],
        cves=[{
            "cve_id": "CVE-2026-4014", "summary": "14 test",
            "affected_from": "14.0", "affected_before": "14.23",
            "fixed_versions": ["14.23"],
        }],
    )
    store.match_job(job_id="e" * 32, normalized=normalized("14.23", "PostgreSQL"))
    report = store.report_section(job_id="e" * 32)
    assert "EOL" in report["version_updates"][0]["summary"]


def test_import_command_rejects_non_policy_source(tmp_path) -> None:
    snapshot = tmp_path / "bad.json"
    snapshot.write_text('{"product_id":"postgresql","source_key":"random","releases":[],"cves":[]}', encoding="utf-8")
    try:
        import_snapshot(snapshot, database_url=f"sqlite+pysqlite:///{tmp_path / 'bad.sqlite'}", requested_by="test")
    except ValueError as exc:
        assert "fixed official-source policy" in str(exc)
    else:
        raise AssertionError("unapproved source must be rejected")


def test_postgresql_official_release_catalogue_keeps_supported_majors(monkeypatch) -> None:
    class Response:
        def read(self) -> bytes:
            return b'[{"major":"17","latestMinor":"10","relDate":"2026-08-01","supported":true},{"major":"12","latestMinor":"22","supported":false}]'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("omni_healthcheck.cve_sync.urlopen", lambda *_args, **_kwargs: Response())
    snapshot = postgresql_release_snapshot(url="https://official.example/versions.json")
    assert snapshot["product_id"] == "postgresql"
    assert snapshot["cves"] == []
    assert snapshot["releases"][0]["version"] == "17.10"


def test_postgresql_security_snapshot_keeps_fixed_version_per_major() -> None:
    snapshot = _postgresql_security_snapshot("""
    <table><tr><th>Reference</th><th>Affected</th><th>Fixed</th><th>Component & CVSS</th><th>Description</th></tr>
    <tr><td>CVE-2026-6638</td><td>18, 17, 16</td><td>18.4, 17.10, 16.14</td>
    <td>core server 3.7 AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:L/A:N</td><td>test finding</td></tr></table>
    """)
    assert [(item["affected_major"], item["affected_before"]) for item in snapshot["cves"]] == [
        ("18", "18.4"), ("17", "17.10"), ("16", "16.14"),
    ]


def test_edb_advisory_snapshot_extracts_direct_epas_range() -> None:
    snapshot = _edb_advisory_snapshot("""
    CVE-2024-4545 Updated: 2024/05/09 Score: 7.7
    EDB Postgres Advanced Server (EPAS) authenticated file read permissions bypass using edbldr
    All versions of EDB Postgres Advanced Server (EPAS) edbldr from 15.0 and prior to 15.7.0
    """)
    record = snapshot["cves"][0]
    assert record["affected_major"] == "15"
    assert record["affected_before"] == "15.7.0"


def test_nvd_enrichment_reads_cvss_and_cwe(monkeypatch) -> None:
    class Response:
        def read(self) -> bytes:
            return b'{"vulnerabilities":[{"cve":{"published":"2026-01-01T00:00:00.000","lastModified":"2026-01-02T00:00:00.000","vulnStatus":"Analyzed","metrics":{"cvssMetricV31":[{"type":"Primary","cvssData":{"baseScore":7.5,"baseSeverity":"HIGH","version":"3.1","vectorString":"CVSS:3.1/AV:N"}}]},"weaknesses":[{"description":[{"value":"CWE-79"}]}]}}]}'

        def __enter__(self): return self
        def __exit__(self, *_args): return False

    monkeypatch.setattr("omni_healthcheck.cve_sync.urlopen", lambda *_args, **_kwargs: Response())
    result = nvd_enrichment(cve_ids=["CVE-2026-0001"], url="https://nvd.example/api")
    assert result[0]["cvss_score"] == 7.5
    assert result[0]["cwe"] == ["CWE-79"]
