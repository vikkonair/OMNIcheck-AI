"""Versioned canonical models shared by parsers and later renderers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TableEvidence(CanonicalModel):
    type: Literal["table"] = "table"
    headers: list[str] = Field(min_length=1)
    rows: list[list[str]] = Field(min_length=1)


class Trace(CanonicalModel):
    parser_id: str = Field(min_length=1)
    rule_id: str | None = None
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CheckResult(CanonicalModel):
    schema_version: Literal["1.0"] = "1.0"
    check_id: str = Field(pattern=r"^[a-z0-9_]+$")
    section_id: str = Field(min_length=1)
    node: str = Field(min_length=1)
    node_role: Literal["Primary", "Standby", "DR", "Witness"]
    product: Literal["OS", "PostgreSQL", "EPAS", "PEM", "EFM"]
    collected_at: str | None = None
    evidence: TableEvidence
    assessment: None = None
    trace: Trace


class UnparsedEvidence(CanonicalModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1)


class NormalizedDocument(CanonicalModel):
    schema_version: Literal["1.0"] = "1.0"
    pipeline_version: str = Field(min_length=1)
    checks: list[CheckResult]
    unparsed_allowed_evidence: list[UnparsedEvidence]
