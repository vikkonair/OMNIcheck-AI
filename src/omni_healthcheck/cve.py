"""Deterministic M13 CVE cache, version matching and report projection.

This module deliberately does *not* fetch data during report generation.
The sync worker writes a versioned cache first; jobs only read one recorded
snapshot from that cache.  AI may later explain these records but cannot alter
them.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable, Literal
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text,
    UniqueConstraint, and_, delete, insert, select, update,
)
from sqlalchemy.engine import Engine

from omni_healthcheck.database import SCHEMA, create_database_engine, metadata
from omni_healthcheck.schema import NormalizedDocument


PARSER_VERSION = "m13.version-parser.v2"
MATCHER_VERSION = "m13.version-matcher.v2"
VALID_MATCHES = {
    "applicable", "fixed", "not_applicable", "potentially_applicable",
    "pending_confirmation",
}
SOURCE_POLICY = {
    "postgresql_security": {
        "name": "PostgreSQL Security", "url": "https://www.postgresql.org/support/security/",
        "type": "vendor", "priority": 10,
    },
    "edb_security": {
        "name": "EDB Security Advisories", "url": "https://www.enterprisedb.com/docs/security/advisories/",
        "type": "vendor", "priority": 10,
    },
    "nvd": {
        "name": "NVD", "url": "https://nvd.nist.gov/", "type": "enrichment", "priority": 30,
    },
}
# Official PostgreSQL Versioning Policy support dates.  EPAS is flagged against
# its PostgreSQL-compatible Major and the report explicitly asks the engineer
# to confirm the customer's EDB support entitlement.  Cache sync is the long
# term source of release facts; this compact policy prevents report-time web
# access while retaining deterministic EOL warnings for supported Majors.
POSTGRESQL_MAJOR_EOL = {
    "14": date(2026, 11, 12), "15": date(2027, 11, 11),
    "16": date(2028, 11, 9), "17": date(2029, 11, 8),
    "18": date(2030, 11, 14),
}


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


cve_sources = Table(
    "cve_sources", metadata,
    Column("source_id", String(32), primary_key=True),
    Column("source_key", String(96), nullable=False, unique=True),
    Column("source_name", Text, nullable=False), Column("source_url", Text, nullable=False),
    Column("source_type", String(24), nullable=False), Column("priority", Integer, nullable=False),
    Column("active", Boolean, nullable=False), Column("last_success_at", DateTime(timezone=True)),
    Column("last_error", Text()), Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False), schema=SCHEMA,
)
cve_sync_runs = Table(
    "cve_sync_runs", metadata,
    Column("sync_run_id", String(32), primary_key=True), Column("sync_type", String(16), nullable=False),
    Column("product_id", String(64)), Column("component_id", String(64)), Column("status", String(16), nullable=False),
    Column("requested_by", String(128)), Column("source_count", Integer, nullable=False),
    Column("item_count", Integer, nullable=False), Column("error", Text()),
    Column("started_at", DateTime(timezone=True)), Column("completed_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False), schema=SCHEMA,
)
product_releases = Table(
    "product_releases", metadata,
    Column("release_id", String(32), primary_key=True), Column("product_id", String(64), nullable=False),
    Column("product_name", Text, nullable=False), Column("version", String(128), nullable=False),
    Column("release_family", String(64)), Column("released_at", DateTime(timezone=True)),
    Column("source_id", String(32), nullable=False), Column("source_url", Text, nullable=False),
    Column("raw_hash", String(64), nullable=False), Column("sync_run_id", String(32), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False), Column("active", Boolean, nullable=False),
    UniqueConstraint("product_id", "version", name="uq_product_releases_product_version"), schema=SCHEMA,
)
cve_entries = Table(
    "cve_entries", metadata,
    Column("cve_id", String(32), primary_key=True), Column("summary", Text, nullable=False),
    Column("published_at", DateTime(timezone=True)), Column("modified_at", DateTime(timezone=True)),
    Column("cvss_score", Numeric(4, 1)), Column("severity", String(24)),
    Column("cvss_version", String(16)), Column("cvss_vector", Text()), Column("cwe", JSON, nullable=False),
    Column("rejected", Boolean, nullable=False), Column("raw", JSON, nullable=False),
    Column("raw_hash", String(64), nullable=False), Column("updated_at", DateTime(timezone=True), nullable=False), schema=SCHEMA,
)
cve_product_impacts = Table(
    "cve_product_impacts", metadata,
    Column("impact_id", String(32), primary_key=True), Column("cve_id", String(32), nullable=False),
    Column("product_id", String(64), nullable=False), Column("component_id", String(64)),
    Column("affected_major", String(32), nullable=False, default="__all__"),
    Column("applicability_status", String(32), nullable=False), Column("affected_expression", Text()),
    Column("affected_from", String(128)), Column("affected_before", String(128)),
    Column("fixed_versions", JSON, nullable=False), Column("vendor_assessment", Text()),
    Column("source_id", String(32), nullable=False), Column("source_priority", Integer, nullable=False),
    Column("raw", JSON, nullable=False), Column("sync_run_id", String(32), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("cve_id", "product_id", "component_id", "source_id", "affected_major", name="uq_cve_product_impacts_source_major"), schema=SCHEMA,
)
job_product_versions = Table(
    "job_product_versions", metadata,
    Column("job_product_version_id", String(32), primary_key=True), Column("job_id", String(32), nullable=False),
    Column("product_id", String(64), nullable=False), Column("component_id", String(64)),
    Column("installed_version", String(128), nullable=False), Column("evidence", JSON, nullable=False),
    Column("parser_version", String(32), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", "product_id", "component_id", name="uq_job_product_versions_component"), schema=SCHEMA,
)
job_cve_matches = Table(
    "job_cve_matches", metadata,
    Column("job_cve_match_id", String(32), primary_key=True), Column("job_id", String(32), nullable=False),
    Column("cve_id", String(32), nullable=False), Column("product_id", String(64), nullable=False),
    Column("component_id", String(64)), Column("installed_version", String(128), nullable=False),
    Column("match_status", String(32), nullable=False), Column("match_reason", Text, nullable=False),
    Column("match_evidence", JSON, nullable=False), Column("matcher_version", String(32), nullable=False),
    Column("source_snapshot_at", DateTime(timezone=True), nullable=False), Column("cve_sync_run_id", String(32), nullable=False),
    Column("review_status", String(24), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", "cve_id", "product_id", "component_id", name="uq_job_cve_matches_scope"), schema=SCHEMA,
)


@dataclass(frozen=True)
class ProductVersion:
    product_id: Literal["postgresql", "epas"]
    installed_version: str
    evidence: dict[str, str]


def parse_product_versions(normalized: NormalizedDocument) -> list[ProductVersion]:
    """Extract only Primary database version Output into stable product records."""
    values: list[ProductVersion] = []
    pattern = re.compile(r"(?i)\b(PostgreSQL|EnterpriseDB|EDB Postgres Advanced Server|EPAS)\s+(\d+(?:\.\d+){0,2})")
    for check in normalized.checks:
        if check.check_id != "database_version" or check.node_role != "Primary":
            continue
        text = "\n".join(" ".join(row) for row in check.evidence.rows)
        match = pattern.search(text)
        if not match:
            continue
        # The parser which created normalized.json already classifies the
        # database product.  EPAS's `select version()` commonly contains the
        # upstream words "PostgreSQL 16.14", so that free text must not undo
        # the canonical product identity supplied by the parser.
        declared = str(check.product or "").casefold()
        if declared in {"epas", "edb", "edb postgres advanced server"}:
            product = "epas"
        elif declared in {"postgresql", "postgres"}:
            product = "postgresql"
        else:
            product = "postgresql" if match.group(1).casefold() == "postgresql" else "epas"
        values.append(ProductVersion(product, match.group(2), {
            "node": check.node, "check_id": check.check_id,
            "evidence_sha256": check.trace.evidence_sha256, "value": match.group(0),
        }))
    unique = {(value.product_id, value.installed_version): value for value in values}
    return list(unique.values())


def _version(value: str) -> tuple[int, ...] | None:
    match = re.fullmatch(r"\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*", value)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _in_range(installed: str, affected_from: str | None, affected_before: str | None) -> bool | None:
    current = _version(installed)
    lower = _version(affected_from) if affected_from else None
    upper = _version(affected_before) if affected_before else None
    # A generic CVE mention with no precise version bounds is not an
    # applicability decision.  It may be retained in an external knowledge
    # catalogue, but it must never become a customer report row.
    if not affected_from or not affected_before:
        return None
    if current is None or lower is None or upper is None:
        return None
    return (lower is None or current >= lower) and (upper is None or current < upper)


def _eol_message(product_id: str, version: str) -> str | None:
    major = version.split(".", 1)[0]
    end = POSTGRESQL_MAJOR_EOL.get(major)
    if end is None:
        return None
    days = (end - _now().date()).days
    product_note = "；EPAS 請同時向 EDB 確認合約支援期限" if product_id == "epas" else ""
    if days < 0:
        return f"注意：PostgreSQL 相容 Major {major} 已於 {end.isoformat()} EOL{product_note}。"
    if days <= 365:
        return f"注意：PostgreSQL 相容 Major {major} 將於 {end.isoformat()} EOL（剩餘約 {days} 天）{product_note}。"
    return None


class CVECacheStore:
    """M13 cache writer and deterministic matcher; production schema is Alembic-managed."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def create_schema_for_test(self) -> None:
        import omni_healthcheck.application_data  # noqa: F401
        metadata.create_all(self.engine)

    def seed_source_policy(self) -> dict[str, str]:
        now, identifiers = _now(), {}
        with self.engine.begin() as connection:
            for key, source in SOURCE_POLICY.items():
                current = connection.execute(select(cve_sources).where(cve_sources.c.source_key == key)).mappings().first()
                if current:
                    identifiers[key] = str(current["source_id"])
                    continue
                source_id = _id(); identifiers[key] = source_id
                connection.execute(insert(cve_sources).values(source_id=source_id, source_key=key, source_name=source["name"], source_url=source["url"], source_type=source["type"], priority=source["priority"], active=True, last_success_at=None, last_error=None, created_at=now, updated_at=now))
        return identifiers

    def import_snapshot(self, *, product_id: str, source_key: str, releases: Iterable[dict[str, Any]], cves: Iterable[dict[str, Any]], requested_by: str = "system") -> dict[str, Any]:
        """Import already-downloaded, validated source records as one immutable sync snapshot."""
        sources = self.seed_source_policy()
        if source_key not in sources:
            raise ValueError(f"source is not part of fixed policy: {source_key}")
        if product_id not in {"postgresql", "epas"}:
            raise ValueError("product_id must be postgresql or epas")
        now, sync_id = _now(), _id()
        release_values, cve_values = list(releases), list(cves)
        with self.engine.begin() as connection:
            sync_type = "cve" if cve_values else "release"
            connection.execute(insert(cve_sync_runs).values(sync_run_id=sync_id, sync_type=sync_type, product_id=product_id, component_id=None, status="running", requested_by=requested_by, source_count=1, item_count=0, error=None, started_at=now, completed_at=None, created_at=now))
            for record in release_values:
                version = str(record["version"])
                existing = connection.execute(select(product_releases.c.release_id).where(and_(product_releases.c.product_id == product_id, product_releases.c.version == version))).scalar_one_or_none()
                values = dict(release_id=existing or _id(), product_id=product_id, product_name="EDB Postgres Advanced Server" if product_id == "epas" else "PostgreSQL", version=version, release_family=version.split(".", 1)[0], released_at=record.get("released_at"), source_id=sources[source_key], source_url=str(record.get("source_url") or SOURCE_POLICY[source_key]["url"]), raw_hash=_hash(record), sync_run_id=sync_id, fetched_at=now, active=True)
                if existing: connection.execute(update(product_releases).where(product_releases.c.release_id == existing).values(**values))
                else: connection.execute(insert(product_releases).values(**values))
            for record in cve_values:
                cve_id = str(record["cve_id"]).upper()
                required = {"affected_from", "affected_before", "fixed_versions"}
                if not required <= record.keys(): raise ValueError(f"{cve_id} is missing impact range")
                entry = dict(cve_id=cve_id, summary=str(record.get("summary") or "未提供摘要"), published_at=record.get("published_at"), modified_at=record.get("modified_at"), cvss_score=record.get("cvss_score"), severity=record.get("severity") or "未公布／待確認", cvss_version=record.get("cvss_version") or "未公布／待確認", cvss_vector=record.get("cvss_vector") or "未公布／待確認", cwe=list(record.get("cwe") or []), rejected=bool(record.get("rejected", False)), raw=dict(record), raw_hash=_hash(record), updated_at=now)
                exists = connection.execute(select(cve_entries.c.cve_id).where(cve_entries.c.cve_id == cve_id)).scalar_one_or_none()
                if exists: connection.execute(update(cve_entries).where(cve_entries.c.cve_id == cve_id).values(**entry))
                else: connection.execute(insert(cve_entries).values(**entry))
                affected_major = str(record.get("affected_major") or "__all__")
                impact = connection.execute(select(cve_product_impacts.c.impact_id).where(and_(cve_product_impacts.c.cve_id == cve_id, cve_product_impacts.c.product_id == product_id, cve_product_impacts.c.component_id.is_(None), cve_product_impacts.c.source_id == sources[source_key], cve_product_impacts.c.affected_major == affected_major))).scalar_one_or_none()
                values = dict(impact_id=impact or _id(), cve_id=cve_id, product_id=product_id, component_id=None, affected_major=affected_major, applicability_status="pending_confirmation", affected_expression=str(record.get("affected_expression") or ""), affected_from=str(record["affected_from"] or "") or None, affected_before=str(record["affected_before"] or "") or None, fixed_versions=list(record["fixed_versions"]), vendor_assessment=record.get("vendor_assessment"), source_id=sources[source_key], source_priority=SOURCE_POLICY[source_key]["priority"], raw=dict(record), sync_run_id=sync_id, fetched_at=now)
                if impact: connection.execute(update(cve_product_impacts).where(cve_product_impacts.c.impact_id == impact).values(**values))
                else: connection.execute(insert(cve_product_impacts).values(**values))
            connection.execute(update(cve_sync_runs).where(cve_sync_runs.c.sync_run_id == sync_id).values(status="succeeded", item_count=len(release_values)+len(cve_values), completed_at=_now()))
            connection.execute(update(cve_sources).where(cve_sources.c.source_id == sources[source_key]).values(last_success_at=_now(), last_error=None, updated_at=_now()))
        return {"sync_run_id": sync_id, "product_id": product_id, "release_count": len(release_values), "cve_count": len(cve_values)}

    def enrich_nvd(self, *, records: Iterable[dict[str, Any]], requested_by: str = "scheduled-cve-sync") -> dict[str, Any]:
        """Supplement cached CVE facts from NVD without changing any impact range."""
        values, now, sync_id = list(records), _now(), _id()
        sources = self.seed_source_policy()
        with self.engine.begin() as connection:
            connection.execute(insert(cve_sync_runs).values(sync_run_id=sync_id, sync_type="cve", product_id=None, component_id=None, status="running", requested_by=requested_by, source_count=1, item_count=0, error=None, started_at=now, completed_at=None, created_at=now))
            updated = 0
            for record in values:
                cve_id = str(record["cve_id"]).upper()
                current = connection.execute(select(cve_entries).where(cve_entries.c.cve_id == cve_id)).mappings().first()
                if current is None:
                    continue
                raw = dict(current["raw"] or {}); raw["nvd"] = json.loads(json.dumps(record, default=lambda value: value.isoformat()))
                merged = dict(summary=current["summary"], published_at=record.get("published_at") or current["published_at"], modified_at=record.get("modified_at") or current["modified_at"], cvss_score=record.get("cvss_score") if record.get("cvss_score") is not None else current["cvss_score"], severity=record.get("severity") or current["severity"], cvss_version=record.get("cvss_version") or current["cvss_version"], cvss_vector=record.get("cvss_vector") or current["cvss_vector"], cwe=list(record.get("cwe") or current["cwe"] or []), rejected=bool(record.get("rejected", current["rejected"])), raw=raw, raw_hash=_hash(raw), updated_at=now)
                connection.execute(update(cve_entries).where(cve_entries.c.cve_id == cve_id).values(**merged)); updated += 1
            connection.execute(update(cve_sync_runs).where(cve_sync_runs.c.sync_run_id == sync_id).values(status="succeeded", item_count=updated, completed_at=_now()))
            connection.execute(update(cve_sources).where(cve_sources.c.source_id == sources["nvd"]).values(last_success_at=_now(), last_error=None, updated_at=_now()))
        return {"sync_run_id": sync_id, "enriched_count": updated}

    def match_job(self, *, job_id: str, normalized: NormalizedDocument) -> list[dict[str, Any]]:
        products = parse_product_versions(normalized)
        now = _now()
        results: list[dict[str, Any]] = []
        with self.engine.begin() as connection:
            for product in products:
                connection.execute(delete(job_product_versions).where(and_(job_product_versions.c.job_id == job_id, job_product_versions.c.product_id == product.product_id, job_product_versions.c.component_id.is_(None))))
                connection.execute(insert(job_product_versions).values(job_product_version_id=_id(), job_id=job_id, product_id=product.product_id, component_id=None, installed_version=product.installed_version, evidence=product.evidence, parser_version=PARSER_VERSION, created_at=now))
                candidate_products = [product.product_id]
                if product.product_id == "epas":
                    # An upstream PostgreSQL advisory is useful for EPAS triage, but
                    # does not prove applicability: EDB may have backported a fix.
                    candidate_products.append("postgresql")
                installed_major = product.installed_version.split(".", 1)[0]
                # NVD is enrichment only.  It may supplement CVSS/CWE for a
                # CVE already accepted by the vendor source, but generic NVD
                # keyword/CPE results must never be treated as PostgreSQL or
                # EPAS server applicability evidence.
                allowed_sources = ["edb_security"] if product.product_id == "epas" else ["postgresql_security"]
                if product.product_id == "epas":
                    allowed_sources.append("postgresql_security")
                impacts = connection.execute(select(cve_product_impacts, cve_entries, cve_sources).join(cve_entries, cve_entries.c.cve_id == cve_product_impacts.c.cve_id).join(cve_sources, cve_sources.c.source_id == cve_product_impacts.c.source_id).where(and_(cve_product_impacts.c.product_id.in_(candidate_products), cve_product_impacts.c.component_id.is_(None), cve_product_impacts.c.affected_major.in_([installed_major, "__all__"]), cve_sources.c.source_key.in_(allowed_sources), cve_product_impacts.c.affected_from.is_not(None), cve_product_impacts.c.affected_before.is_not(None))).order_by(cve_product_impacts.c.source_priority)).mappings().all()
                impacts.sort(key=lambda item: (0 if item["product_id"] == product.product_id else 1, item["source_priority"]))
                seen: set[str] = set()
                for impact in impacts:
                    cve_id = str(impact["cve_id"])
                    if cve_id in seen: continue
                    seen.add(cve_id)
                    in_range = _in_range(product.installed_version, impact["affected_from"], impact["affected_before"])
                    if impact["rejected"]: status, reason = "not_applicable", "CVE 已被權威來源標示為 rejected"
                    elif in_range is None: status, reason = "pending_confirmation", "版本範圍格式不足以確定比對結果"
                    elif in_range and product.product_id == "epas" and impact["product_id"] == "postgresql":
                        status, reason = "potentially_applicable", "PostgreSQL 上游公告顯示版本可能受影響；須由 EDB 公告或 backport 資訊確認"
                    elif in_range: status, reason = "applicable", "安裝版本位於權威來源定義的影響範圍內"
                    else: status, reason = "fixed", "安裝版本不在影響範圍內，已達修補版本或不受影響"
                    sync_at = impact["fetched_at"] or now
                    match = dict(job_cve_match_id=_id(), job_id=job_id, cve_id=cve_id, product_id=product.product_id, component_id=None, installed_version=product.installed_version, match_status=status, match_reason=reason, match_evidence={"product_version_evidence": product.evidence, "affected_from": impact["affected_from"], "affected_before": impact["affected_before"], "fixed_versions": impact["fixed_versions"], "source_url": impact["source_url"], "source_key": impact["source_key"], "source_product": impact["product_id"]}, matcher_version=MATCHER_VERSION, source_snapshot_at=sync_at, cve_sync_run_id=impact["sync_run_id"], review_status="unreviewed", created_at=now)
                    connection.execute(delete(job_cve_matches).where(and_(job_cve_matches.c.job_id == job_id, job_cve_matches.c.cve_id == cve_id, job_cve_matches.c.product_id == product.product_id, job_cve_matches.c.component_id.is_(None))))
                    connection.execute(insert(job_cve_matches).values(**match)); results.append(match)
        return results

    def _latest_same_major(self, connection, product_id: str, installed_version: str) -> str | None:
        """Return the cached official latest minor for the installed Major.

        EPAS shares PostgreSQL's Major/minor baseline.  We prefer an EPAS
        record when available, and otherwise use the PostgreSQL official
        release catalogue only for the version path—not for CVE applicability.
        """
        major = installed_version.split(".", 1)[0]
        product_ids = [product_id]
        if product_id == "epas":
            product_ids.extend(["edb", "postgresql"])
        rows = connection.execute(select(product_releases.c.version).where(and_(product_releases.c.product_id.in_(product_ids), product_releases.c.release_family == major, product_releases.c.active.is_(True)))).scalars().all()
        parsed = [(value, _version(str(value))) for value in rows]
        parsed = [(value, version) for value, version in parsed if version is not None]
        return str(max(parsed, key=lambda item: item[1])[0]) if parsed else None

    def report_section(self, *, job_id: str, stale_after_days: int = 14) -> dict[str, Any]:
        if stale_after_days < 1: raise ValueError("stale_after_days must be positive")
        with self.engine.connect() as connection:
            rows = connection.execute(select(job_cve_matches, cve_entries).join(cve_entries, cve_entries.c.cve_id == job_cve_matches.c.cve_id).where(job_cve_matches.c.job_id == job_id).order_by(job_cve_matches.c.cve_id)).mappings().all()
        if not rows:
            return {"status": "pending_confirmation", "delivery_allowed": True, "message": "未取得可辨識的 Primary 資料庫版本；CVE 適用性待確認。", "version_updates": [], "quality_gate": {"status": "warning", "reason": "no_product_version"}}
        snapshot_at = min(row["source_snapshot_at"] for row in rows)
        if snapshot_at.tzinfo is None:
            snapshot_at = snapshot_at.replace(tzinfo=UTC)
        stale = snapshot_at < _now() - timedelta(days=stale_after_days)
        applicable = [row for row in rows if row["match_status"] in {"applicable", "potentially_applicable"}]
        current = str(rows[0]["installed_version"])
        product_name = "EDB Postgres Advanced Server" if rows[0]["product_id"] == "epas" else "PostgreSQL"
        with self.engine.connect() as connection:
            latest = self._latest_same_major(connection, str(rows[0]["product_id"]), current)
        current_version, latest_version = _version(current), _version(latest) if latest else None
        is_current = bool(current_version and latest_version and current_version >= latest_version)
        cves = [] if is_current else [{"id": row["cve_id"], "summary": row["summary"], "cvss_score": str(row["cvss_score"] or "未公布／待確認"), "severity": row["severity"] or "未公布／待確認", "cvss_version": row["cvss_version"] or "未公布／待確認", "vector": row["cvss_vector"] or "未公布／待確認", "score_source": row["match_evidence"].get("source_url", "未提供"), "match_status": row["match_status"], "affected_version": f">= {row['match_evidence'].get('affected_from') or '-'}，< {row['match_evidence'].get('affected_before') or '-'}", "fixed_version": "、".join(row["match_evidence"].get("fixed_versions") or []) or "待確認", "source": row["match_evidence"].get("source_url", "未提供"), "component": "核心資料庫" } for row in applicable]
        status = "stale" if stale else "ready"
        eol_message = _eol_message(str(rows[0]["product_id"]), current)
        if stale:
            message = "CVE data stale：權威資料快取已超過政策期限；請完成同步後再正式交付。"
        elif latest is None:
            message = f"已依 {product_name} {current} 的權威快取完成 CVE 比對；尚未取得同 Major 官方最新版本資料。"
        elif is_current:
            message = f"目前已是 {current.split('.', 1)[0]} Major 的最新維護版本 {latest}；無需進行同 Major minor 更新。"
        else:
            message = f"目前版本 {current} 可更新至同 Major 最新維護版本 {latest}；下列為此更新路徑中可修正的 CVE。"
        if eol_message:
            message = f"{message}\n{eol_message}"
        recommended = f"{product_name} {latest}" if latest else "同 Major 最新維護版本待確認"
        return {"status": status, "delivery_allowed": not stale, "message": message, "source_snapshot_at": snapshot_at.isoformat(), "matcher_version": MATCHER_VERSION, "version_updates": [{"current": f"{product_name} {current}", "recommended": recommended, "summary": message, "cves": cves, "eol_message": eol_message}], "quality_gate": {"status": "failed" if stale else "passed", "reason": "cve_data_stale" if stale else "current"}}
