"""Central registry for optional health-check services and components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDefinition:
    name: str
    category: str
    allowed_roles: frozenset[str] | None = None


SERVICE_REGISTRY = {
    "pem": ServiceDefinition(
        name="PEM",
        category="monitoring",
        allowed_roles=frozenset({"Witness"}),
    ),
    "efm": ServiceDefinition(name="EFM", category="failover"),
    "xdb": ServiceDefinition(
        name="XDB",
        category="supporting_component",
        allowed_roles=frozenset({"Witness"}),
    ),
    "pgbackrest": ServiceDefinition(name="pgBackRest", category="backup"),
    "barman": ServiceDefinition(name="Barman", category="backup"),
}


def service_definition(value: str) -> ServiceDefinition | None:
    """Return a registered service using case-insensitive alias matching."""
    key = "".join(character for character in value.casefold() if character.isalnum())
    return SERVICE_REGISTRY.get(key)


def canonical_service_name(value: str) -> str:
    """Normalize registered names while preserving explicit custom components."""
    definition = service_definition(value)
    return definition.name if definition else value.strip()
