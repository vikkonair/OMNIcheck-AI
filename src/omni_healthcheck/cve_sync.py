"""Controlled M13 cache import command.

The downloader is intentionally separated from the matcher: a scheduled
operator-owned task downloads only the fixed official sources, validates its
snapshot, then imports it atomically.  A report never performs network I/O.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence
from urllib.request import Request, urlopen

from omni_healthcheck.cve import CVECacheStore, SOURCE_POLICY


POSTGRESQL_VERSIONS_URL = "https://www.postgresql.org/versions.json"
POSTGRESQL_SECURITY_URL = "https://www.postgresql.org/support/security/"
EDB_ADVISORIES_URL = "https://www.enterprisedb.com/docs/security/advisories/"
NVD_CVE_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


class _TableParser(HTMLParser):
    """Small dependency-free table extractor for fixed public source pages."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _fetch_text(url: str, timeout_seconds: int = 30) -> str:
    request = Request(url, headers={"User-Agent": "OMNIcheck-AI-CVE-Sync/1"})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - fixed official URL or operator test URL
        return response.read().decode("utf-8")


def _major_floor(major: str) -> str:
    return f"{major}.0" if "." not in major else f"{major}.0"


def _iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _postgresql_security_snapshot(html: str, *, source_url: str = POSTGRESQL_SECURITY_URL) -> dict:
    parser = _TableParser(); parser.feed(html)
    records: list[dict] = []
    for row in parser.rows:
        if len(row) != 5:
            continue
        reference, affected, fixed, component_cvss, description = row
        cve = re.search(r"CVE-\d{4}-\d{4,}", reference, re.I)
        if not cve or "core server" not in component_cvss.casefold():
            continue
        majors = re.findall(r"\b\d+(?:\.\d+)?\b", affected)
        fixed_versions = re.findall(r"\b\d+(?:\.\d+){1,2}\b", fixed)
        vector = re.search(r"(AV:[A-Z](?:/[A-Z]+:[A-Z]){5,})", component_cvss)
        score = re.search(r"\b(10(?:\.0)?|[0-9](?:\.\d)?)\b", component_cvss)
        if not majors or len(fixed_versions) != len(majors):
            continue
        for major, fixed_version in zip(majors, fixed_versions, strict=True):
            if fixed_version.split(".", 1)[0] != major.split(".", 1)[0]:
                continue
            records.append({
                "cve_id": cve.group(0).upper(), "summary": " ".join(description.split()),
                "affected_major": major.split(".", 1)[0], "affected_from": _major_floor(major),
                "affected_before": fixed_version, "fixed_versions": [fixed_version],
                "cvss_score": float(score.group(1)) if score else None,
                "severity": "未公布／待確認", "cvss_version": "3.1" if vector else "未公布／待確認",
                "cvss_vector": vector.group(1) if vector else "未公布／待確認",
                "source_url": source_url, "affected_expression": affected,
            })
    if not records:
        raise ValueError("PostgreSQL Security page yielded no core-server CVE records")
    return {"product_id": "postgresql", "source_key": "postgresql_security", "releases": [], "cves": records}


def postgresql_security_snapshot(*, url: str = POSTGRESQL_SECURITY_URL, timeout_seconds: int = 30) -> dict:
    return _postgresql_security_snapshot(_fetch_text(url, timeout_seconds), source_url=url)


def _edb_advisory_snapshot(html: str, *, source_url: str = EDB_ADVISORIES_URL) -> dict:
    """Extract direct EPAS advisories only; other EDB products are out of scope."""
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = re.sub(r"\s+", " ", text)
    records: list[dict] = []
    blocks = re.split(r"(?=CVE-\d{4}-\d{4,})", text)
    for block in blocks:
        cve = re.match(r"(CVE-\d{4}-\d{4,})", block, re.I)
        if not cve or not re.search(r"(?:EPAS|EDB Postgres Advanced Server)", block, re.I):
            continue
        score = re.search(r"Score:\s*(\d+(?:\.\d+)?)", block, re.I)
        # Vendor text commonly says "from 15.0 and prior to 15.7.0" or
        # "prior to 11.21.32, 12.16.20".  Each fixed version is its own major.
        fixed_versions = re.findall(r"(?:prior to\s+)(\d+(?:\.\d+){1,2})", block, re.I)
        if not fixed_versions:
            continue
        for fixed_version in dict.fromkeys(fixed_versions):
            major = fixed_version.split(".", 1)[0]
            records.append({
                "cve_id": cve.group(1).upper(), "summary": block[:800],
                "affected_major": major, "affected_from": f"{major}.0",
                "affected_before": fixed_version, "fixed_versions": [fixed_version],
                "cvss_score": float(score.group(1)) if score else None,
                "severity": "未公布／待確認", "cvss_version": "未公布／待確認",
                "cvss_vector": "未公布／待確認", "source_url": source_url,
                "affected_expression": block[:1000], "vendor_assessment": "EDB official advisory",
            })
    if not records:
        raise ValueError("EDB advisory page yielded no direct EPAS CVE records")
    return {"product_id": "epas", "source_key": "edb_security", "releases": [], "cves": records}


def edb_advisory_snapshot(*, url: str = EDB_ADVISORIES_URL, timeout_seconds: int = 30) -> dict:
    return _edb_advisory_snapshot(_fetch_text(url, timeout_seconds), source_url=url)


def nvd_enrichment(*, cve_ids: Sequence[str], url: str = NVD_CVE_API_URL, timeout_seconds: int = 30) -> list[dict]:
    """Fetch CVSS/CWE facts from NVD for CVEs already accepted into Cache."""
    records: list[dict] = []
    for cve_id in dict.fromkeys(item.upper() for item in cve_ids):
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve_id):
            raise ValueError(f"invalid CVE ID: {cve_id}")
        payload = json.loads(_fetch_text(f"{url}?cveId={cve_id}", timeout_seconds))
        vulnerabilities = payload.get("vulnerabilities") if isinstance(payload, dict) else None
        if not isinstance(vulnerabilities, list) or not vulnerabilities:
            continue
        cve = vulnerabilities[0].get("cve", {})
        metrics = cve.get("metrics", {}) if isinstance(cve, dict) else {}
        metric = next((item for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2") for item in metrics.get(key, []) if item.get("type") == "Primary"), None)
        metric = metric or next((item for values in metrics.values() if isinstance(values, list) for item in values), {})
        data = metric.get("cvssData", {}) if isinstance(metric, dict) else {}
        weaknesses = cve.get("weaknesses", []) if isinstance(cve, dict) else []
        cwe = sorted({description.get("value") for weakness in weaknesses if isinstance(weakness, dict) for description in weakness.get("description", []) if isinstance(description, dict) and description.get("value")})
        records.append({
            "cve_id": cve_id, "published_at": _iso_datetime(cve.get("published")), "modified_at": _iso_datetime(cve.get("lastModified")),
            "cvss_score": data.get("baseScore"), "severity": data.get("baseSeverity") or metric.get("baseSeverity"),
            "cvss_version": data.get("version"), "cvss_vector": data.get("vectorString"), "cwe": cwe,
            "rejected": str(cve.get("vulnStatus", "")).casefold() == "rejected", "source_url": f"{url}?cveId={cve_id}",
        })
    return records


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omni-healthcheck-cve-import")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", type=Path, help="validated CVE snapshot JSON")
    mode.add_argument("--sync-postgresql-releases", action="store_true", help="download PostgreSQL official release catalogue")
    mode.add_argument("--sync-postgresql-cves", action="store_true", help="download PostgreSQL official Security CVE catalogue")
    mode.add_argument("--sync-edb-advisories", action="store_true", help="download direct EPAS records from EDB Security Advisories")
    mode.add_argument("--sync-nvd", action="store_true", help="enrich cached CVE IDs with NVD CVSS/CWE facts")
    parser.add_argument("--postgresql-versions-url", default=POSTGRESQL_VERSIONS_URL)
    parser.add_argument("--postgresql-security-url", default=POSTGRESQL_SECURITY_URL)
    parser.add_argument("--edb-advisories-url", default=EDB_ADVISORIES_URL)
    parser.add_argument("--nvd-url", default=NVD_CVE_API_URL)
    parser.add_argument("--cve-id", action="append", default=[], help="CVE ID for --sync-nvd; repeat as required")
    parser.add_argument("--snapshot-output", type=Path, help="write the exact downloaded snapshot for audit/archive")
    parser.add_argument("--requested-by", default="scheduled-cve-sync")
    return parser


def import_snapshot(path: Path, *, database_url: str, requested_by: str) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("CVE snapshot must be a JSON object")
    product_id = str(raw.get("product_id", ""))
    source_key = str(raw.get("source_key", ""))
    if source_key not in SOURCE_POLICY:
        raise ValueError("CVE snapshot source_key is not in fixed official-source policy")
    if not isinstance(raw.get("releases", []), list) or not isinstance(raw.get("cves", []), list):
        raise ValueError("CVE snapshot releases and cves must be arrays")
    return CVECacheStore(database_url).import_snapshot(
        product_id=product_id, source_key=source_key,
        releases=raw["releases"], cves=raw["cves"], requested_by=requested_by,
    )


def postgresql_release_snapshot(*, url: str = POSTGRESQL_VERSIONS_URL, timeout_seconds: int = 30) -> dict:
    """Return a validated snapshot from PostgreSQL's public release catalogue.

    This is deliberately the only network action in this module.  It is a
    scheduled cache-maintenance operation, never a report-generation action.
    """
    request = Request(url, headers={"User-Agent": "OMNIcheck-AI-CVE-Sync/1"})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - fixed official URL or operator test URL
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("PostgreSQL versions endpoint must return an array")
    releases: list[dict] = []
    for item in payload:
        # `current` means only the newest major.  Health checks may be on any
        # supported major, so cache every officially supported release family.
        if not isinstance(item, dict) or not item.get("supported"):
            continue
        major, latest_minor = str(item.get("major", "")), str(item.get("latestMinor", ""))
        if not major or not latest_minor or not major.replace(".", "").isdigit() or not latest_minor.isdigit():
            continue
        released_at = item.get("relDate")
        releases.append({
            "version": f"{major}.{latest_minor}",
            "released_at": datetime.fromisoformat(released_at) if isinstance(released_at, str) else None,
            "source_url": url,
            "official_record": item,
        })
    if not releases:
        raise ValueError("PostgreSQL versions endpoint returned no supported release")
    return {"product_id": "postgresql", "source_key": "postgresql_security", "releases": releases, "cves": []}


def main(argv: Sequence[str] | None = None) -> None:
    args = create_parser().parse_args(argv)
    database_url = os.environ.get("OMNICHECK_DATABASE_URL")
    if not database_url:
        raise SystemExit("OMNICHECK_DATABASE_URL is required")
    if args.sync_postgresql_releases:
        snapshot = postgresql_release_snapshot(url=args.postgresql_versions_url)
    elif args.sync_postgresql_cves:
        snapshot = postgresql_security_snapshot(url=args.postgresql_security_url)
    elif args.sync_edb_advisories:
        snapshot = edb_advisory_snapshot(url=args.edb_advisories_url)
    elif args.sync_nvd:
        if not args.cve_id:
            raise SystemExit("--sync-nvd requires at least one --cve-id")
        records = nvd_enrichment(cve_ids=args.cve_id, url=args.nvd_url)
        if args.snapshot_output:
            args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot_output.write_text(
                json.dumps(records, ensure_ascii=False, indent=2, default=lambda value: value.isoformat()),
                encoding="utf-8",
            )
        result = CVECacheStore(database_url).enrich_nvd(records=records, requested_by=args.requested_by)
        print(json.dumps(result, ensure_ascii=False))
        return
    else:
        result = import_snapshot(args.input, database_url=database_url, requested_by=args.requested_by)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.snapshot_output:
        args.snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_output.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, default=lambda value: value.isoformat()),
            encoding="utf-8",
        )
    result = CVECacheStore(database_url).import_snapshot(
        product_id=snapshot["product_id"], source_key=snapshot["source_key"],
        releases=snapshot["releases"], cves=snapshot["cves"], requested_by=args.requested_by,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
