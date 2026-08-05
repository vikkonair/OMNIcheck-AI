"""M9.5 idempotent persistence of deterministic Pipeline results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.engine import Engine, RowMapping

from omni_healthcheck.database import SCHEMA, create_database_engine, metadata


pipeline_snapshots = Table(
    "pipeline_snapshots",
    metadata,
    Column("snapshot_id", String(32), primary_key=True),
    Column("customer_id", String(32), nullable=False),
    Column("system_id", String(32), nullable=False),
    Column("job_id", String(32), nullable=False),
    Column("schema_version", String(16), nullable=False),
    Column("pipeline_version", String(32), nullable=False),
    Column("ruleset_version", String(32), nullable=False),
    Column("canonical_sha256", String(64), nullable=False),
    Column("source_snapshot_at", DateTime(timezone=True), nullable=False),
    Column("document_hashes", JSON, nullable=False),
    Column("scope_summary", JSON, nullable=False),
    Column("assessment_summary", JSON, nullable=False),
    Column("coverage_summary", JSON, nullable=False),
    Column("persisted_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["job_id", "customer_id", "system_id"],
        [f"{SCHEMA}.jobs.job_id", f"{SCHEMA}.jobs.customer_id", f"{SCHEMA}.jobs.system_id"],
        ondelete="CASCADE",
        name="fk_pipeline_snapshots_job_tenant",
    ),
    UniqueConstraint(
        "job_id", "schema_version", "canonical_sha256",
        name="uq_pipeline_snapshot_identity",
    ),
    UniqueConstraint(
        "snapshot_id", "customer_id", "system_id", "job_id",
        name="uq_pipeline_snapshots_tenant_scope",
    ),
)


def _child_table(name: str, *columns: Column, unique_name: str) -> Table:
    return Table(
        name,
        metadata,
        Column("record_id", String(32), primary_key=True),
        Column("snapshot_id", String(32), nullable=False),
        Column("customer_id", String(32), nullable=False),
        Column("system_id", String(32), nullable=False),
        Column("job_id", String(32), nullable=False),
        Column("ordinal", Integer, nullable=False),
        *columns,
        Column("payload", JSON, nullable=False),
        ForeignKeyConstraint(
            ["snapshot_id", "customer_id", "system_id", "job_id"],
            [
                f"{SCHEMA}.pipeline_snapshots.snapshot_id",
                f"{SCHEMA}.pipeline_snapshots.customer_id",
                f"{SCHEMA}.pipeline_snapshots.system_id",
                f"{SCHEMA}.pipeline_snapshots.job_id",
            ],
            ondelete="CASCADE",
            name=f"fk_{name}_snapshot_tenant",
        ),
        UniqueConstraint("snapshot_id", "ordinal", name=unique_name),
    )


scope_decisions = _child_table(
    "scope_decisions",
    Column("evidence_sha256", String(64), nullable=False),
    Column("evidence_domain", String(32), nullable=False),
    Column("node", Text),
    Column("node_role", String(16)),
    Column("decision", String(16), nullable=False),
    Column("reason", Text, nullable=False),
    unique_name="uq_scope_decisions_snapshot_ordinal",
)

normalized_checks = _child_table(
    "normalized_checks",
    Column("check_id", String(80), nullable=False),
    Column("section_id", String(24), nullable=False),
    Column("node", Text, nullable=False),
    Column("node_role", String(16), nullable=False),
    Column("product", String(32), nullable=False),
    Column("parser_id", String(96), nullable=False),
    Column("evidence_sha256", String(64), nullable=False),
    Column("collected_at", Text),
    unique_name="uq_normalized_checks_snapshot_ordinal",
)

normalized_unparsed = _child_table(
    "normalized_unparsed",
    Column("evidence_sha256", String(64), nullable=False),
    Column("reason", Text, nullable=False),
    unique_name="uq_normalized_unparsed_snapshot_ordinal",
)

configuration_comparisons = _child_table(
    "configuration_comparisons",
    Column("comparison_type", String(32), nullable=False),
    Column("comparison_key", Text, nullable=False),
    Column("status", String(24)),
    unique_name="uq_configuration_comparisons_snapshot_ordinal",
)

pipeline_assessments = _child_table(
    "pipeline_assessments",
    Column("check_id", String(80), nullable=False),
    Column("section_id", String(24), nullable=False),
    Column("node", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("rule_id", String(96), nullable=False),
    Column("rule_version", String(32), nullable=False),
    Column("observation", Text, nullable=False),
    Column("recommendation", Text, nullable=False),
    unique_name="uq_pipeline_assessments_snapshot_ordinal",
)

coverage_items = _child_table(
    "coverage_items",
    Column("node", Text, nullable=False),
    Column("node_role", String(16), nullable=False),
    Column("domain", String(32), nullable=False),
    Column("check_id", String(80), nullable=False),
    Column("required", Boolean, nullable=False),
    Column("evidence_status", String(24), nullable=False),
    Column("assessment_status", String(24), nullable=False),
    unique_name="uq_coverage_items_snapshot_ordinal",
)

quality_results = _child_table(
    "quality_results",
    Column("quality_type", String(24), nullable=False),
    Column("status", String(16), nullable=False),
    Column("delivery_allowed", Boolean, nullable=False),
    unique_name="uq_quality_results_snapshot_ordinal",
)


REQUIRED_DOCUMENTS = {
    "inventory": "inventory.json",
    "scope": "scope-ledger.json",
    "normalized": "normalized.json",
    "configuration": "configuration-comparison.json",
    "assessment": "assessment.json",
    "coverage": "coverage-ledger.json",
    "qa": "qa-result.json",
    "v4_qa": "v4-qa-result.json",
}


def _id() -> str:
    return uuid4().hex


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"pipeline output must be a JSON object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _serialize(row: RowMapping) -> dict:
    result = dict(row)
    for key in ("source_snapshot_at", "persisted_at"):
        value = result.get(key)
        if isinstance(value, datetime):
            result[key] = (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    return result


class PipelineResultStore:
    """Persist one immutable Pipeline snapshot and query its row counts."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None):
        if engine is None and database_url is None:
            raise ValueError("database_url or engine is required")
        self.engine = engine or create_database_engine(str(database_url))

    def persist(self, *, job_id: str, customer_id: str, system_id: str, output_dir: Path) -> dict:
        paths = {key: output_dir / filename for key, filename in REQUIRED_DOCUMENTS.items()}
        missing = [path.name for path in paths.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError("missing pipeline outputs: " + ", ".join(sorted(missing)))
        documents = {key: _load(path) for key, path in paths.items()}
        normalized = documents["normalized"]
        assessment = documents["assessment"]
        snapshot_identity = (
            job_id,
            str(normalized["schema_version"]),
            _sha256(paths["normalized"]),
        )
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(pipeline_snapshots).where(
                    pipeline_snapshots.c.job_id == snapshot_identity[0],
                    pipeline_snapshots.c.schema_version == snapshot_identity[1],
                    pipeline_snapshots.c.canonical_sha256 == snapshot_identity[2],
                )
            ).mappings().first()
            if existing is not None:
                return {**_serialize(existing), "created": False}

            snapshot_id = _id()
            common = {
                "snapshot_id": snapshot_id,
                "customer_id": customer_id,
                "system_id": system_id,
                "job_id": job_id,
            }
            record = {
                **common,
                "schema_version": snapshot_identity[1],
                "pipeline_version": str(normalized["pipeline_version"]),
                "ruleset_version": str(assessment["ruleset_version"]),
                "canonical_sha256": snapshot_identity[2],
                "source_snapshot_at": _time(str(documents["inventory"]["generated_at"])),
                "document_hashes": {key: _sha256(path) for key, path in paths.items()},
                "scope_summary": documents["scope"]["summary"],
                "assessment_summary": assessment["summary"],
                "coverage_summary": documents["coverage"]["summary"],
                "persisted_at": datetime.now(UTC),
            }
            connection.execute(insert(pipeline_snapshots).values(**record))

            def add(table: Table, values: list[dict]) -> None:
                if values:
                    connection.execute(insert(table), [
                        {"record_id": _id(), **common, "ordinal": index, **value}
                        for index, value in enumerate(values)
                    ])

            add(scope_decisions, [{
                "evidence_sha256": item["sha256"], "evidence_domain": item["evidence_domain"],
                "node": item.get("node"), "node_role": item.get("node_role"),
                "decision": item["decision"], "reason": item["reason"], "payload": item,
            } for item in documents["scope"]["evidence"]])
            add(normalized_checks, [{
                "check_id": item["check_id"], "section_id": item["section_id"],
                "node": item["node"], "node_role": item["node_role"], "product": item["product"],
                "parser_id": item["trace"]["parser_id"],
                "evidence_sha256": item["trace"]["evidence_sha256"],
                "collected_at": item.get("collected_at"), "payload": item,
            } for item in normalized["checks"]])
            add(normalized_unparsed, [{
                "evidence_sha256": item["sha256"], "reason": item["reason"],
                "payload": item,
            } for item in normalized.get("unparsed_allowed_evidence", [])])
            comparisons = [{
                "comparison_type": "parameter", "comparison_key": item["parameter"],
                "status": item.get("status"), "payload": item,
            } for item in documents["configuration"].get("parameter_comparisons", [])]
            comparisons.append({
                "comparison_type": "pg_hba", "comparison_key": "pg_hba",
                "status": None, "payload": documents["configuration"].get("pg_hba", {}),
            })
            add(configuration_comparisons, comparisons)
            add(pipeline_assessments, [{
                "check_id": item["check_id"], "section_id": item["section_id"],
                "node": item["node"], "status": item["status"],
                "rule_id": item["trace"]["rule_id"], "rule_version": item["trace"]["rule_version"],
                "observation": item["observation"], "recommendation": item["recommendation"],
                "payload": item,
            } for item in assessment["assessments"]])
            add(coverage_items, [{**item, "payload": item} for item in documents["coverage"]["items"]])
            add(quality_results, [{
                "quality_type": key, "status": documents[key]["status"],
                "delivery_allowed": bool(documents[key]["delivery_allowed"]),
                "payload": documents[key],
            } for key in ("qa", "v4_qa")])
        return {**_serialize(record), "created": True}

    def get(self, customer_id: str, snapshot_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(select(pipeline_snapshots).where(
                pipeline_snapshots.c.snapshot_id == snapshot_id,
                pipeline_snapshots.c.customer_id == customer_id,
            )).mappings().first()
        if row is None:
            raise KeyError(snapshot_id)
        return _serialize(row)

    def counts(self, customer_id: str, snapshot_id: str) -> dict[str, int]:
        result = {}
        with self.engine.connect() as connection:
            for table in (
                scope_decisions, normalized_checks, normalized_unparsed, configuration_comparisons,
                pipeline_assessments, coverage_items, quality_results,
            ):
                result[table.name] = len(connection.execute(select(table.c.record_id).where(
                    table.c.snapshot_id == snapshot_id,
                    table.c.customer_id == customer_id,
                )).all())
        return result
