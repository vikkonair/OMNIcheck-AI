"""Job configuration loading and validation."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from omni_healthcheck.services import canonical_service_name, service_definition


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeConfig(StrictModel):
    hostname: str = Field(min_length=1)
    role: Literal["Primary", "Standby", "DR", "Witness"]
    services: list[str] = Field(default_factory=list)

    @field_validator("services")
    @classmethod
    def normalize_services(cls, values: list[str]) -> list[str]:
        normalized = [canonical_service_name(value) for value in values]
        if any(not value for value in normalized):
            raise ValueError("service names must not be empty")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("node services must be unique")
        return normalized

    @model_validator(mode="after")
    def registered_service_roles_are_valid(self) -> "NodeConfig":
        for service in self.services:
            definition = service_definition(service)
            if (
                definition
                and definition.allowed_roles
                and self.role not in definition.allowed_roles
            ):
                if definition.name == "PEM":
                    raise ValueError("PEM service must run on a Witness node")
                roles = ", ".join(sorted(definition.allowed_roles))
                raise ValueError(
                    f"{definition.name} service must run on role: {roles}"
                )
        return self


class BackupConfig(StrictModel):
    provider: Literal["pgbackrest", "barman"]
    node: str = Field(min_length=1)


class ScopeConfig(StrictModel):
    include_os_from_all_nodes: bool = True
    database_primary_only: bool = True


class ReportConfig(StrictModel):
    template: str = Field(min_length=1)
    output_docx: bool = True
    output_pdf: bool = True


class AIConfig(StrictModel):
    enabled: bool = False
    provider: str = "disabled"

    @model_validator(mode="after")
    def disabled_provider_when_ai_is_off(self) -> "AIConfig":
        if not self.enabled and self.provider != "disabled":
            raise ValueError("provider must be 'disabled' when AI is disabled")
        return self


class JobConfig(StrictModel):
    customer: str = Field(min_length=1)
    system_name: str | None = None
    period: str = Field(min_length=1)
    engineer: str = "XXX"
    product: Literal["PostgreSQL", "EPAS"]
    first_healthcheck: bool
    nodes: list[NodeConfig] = Field(min_length=1)
    backup: BackupConfig | None = None
    scope: ScopeConfig
    report: ReportConfig
    ai: AIConfig

    @model_validator(mode="after")
    def require_unique_nodes_and_primary(self) -> "JobConfig":
        hostnames = [node.hostname.casefold() for node in self.nodes]
        if len(hostnames) != len(set(hostnames)):
            raise ValueError("node hostnames must be unique")
        primary_count = sum(node.role == "Primary" for node in self.nodes)
        if primary_count != 1:
            raise ValueError("exactly one node must have role Primary")
        if self.backup:
            backup_node = next(
                (
                    node
                    for node in self.nodes
                    if node.hostname.casefold() == self.backup.node.casefold()
                ),
                None,
            )
            if backup_node is None:
                raise ValueError("backup.node must reference a configured node")
            expected_service = canonical_service_name(self.backup.provider)
            if expected_service.casefold() not in {
                service.casefold() for service in backup_node.services
            }:
                raise ValueError(
                    f"backup provider {expected_service} must be listed in "
                    f"{backup_node.hostname} services"
                )
        if not self.scope.include_os_from_all_nodes:
            raise ValueError("scope.include_os_from_all_nodes must be true")
        if not self.scope.database_primary_only:
            raise ValueError("scope.database_primary_only must be true")
        return self


class JobConfigError(ValueError):
    """Raised when a job YAML cannot be loaded or validated."""


def load_job(path: Path) -> JobConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise JobConfigError(f"cannot read job file: {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise JobConfigError(f"invalid YAML in job file: {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise JobConfigError("job YAML root must be a mapping")

    try:
        return JobConfig.model_validate(raw)
    except ValidationError as exc:
        raise JobConfigError(f"invalid job configuration:\n{exc}") from exc
