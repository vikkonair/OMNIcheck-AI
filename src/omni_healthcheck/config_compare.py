"""Cross-node comparison for target-cluster configuration files."""

from __future__ import annotations

import re

from omni_healthcheck.schema import NormalizedDocument


TARGET_ROLES = {"Primary", "Standby", "DR"}
PARAMETER_CHECKS = {"postgresql_conf", "postgresql_auto_conf"}


def _output_lines(check) -> list[str]:
    if check.evidence.headers != ["Output"]:
        return []
    return [row[0] for row in check.evidence.rows if row]


def _parse_parameters(lines: list[str]) -> dict[str, str]:
    parameters = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z_][\w.]*)\s*=\s*(.*?)\s*$", stripped)
        if match:
            parameters[match.group(1)] = match.group(2)
    return parameters


def _parse_hba_rules(lines: list[str]) -> set[str]:
    rules = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        normalized = " ".join(stripped.split())
        if normalized:
            rules.add(normalized)
    return rules


def build_configuration_comparison(
    normalized: NormalizedDocument,
    topology: dict,
) -> dict:
    nodes = [
        node["hostname"]
        for node in topology["nodes"]
        if node["role"] in TARGET_ROLES
    ]
    parameter_values: dict[str, dict[str, dict[str, str]]] = {
        check_id: {} for check_id in PARAMETER_CHECKS
    }
    hba_by_node: dict[str, set[str]] = {node: set() for node in nodes}

    for check in normalized.checks:
        if check.node_role not in TARGET_ROLES:
            continue
        if check.check_id in PARAMETER_CHECKS:
            parameter_values[check.check_id][check.node] = _parse_parameters(
                _output_lines(check)
            )
        elif check.check_id == "pg_hba_conf":
            hba_by_node.setdefault(check.node, set()).update(
                _parse_hba_rules(_output_lines(check))
            )

    parameter_comparisons = []
    for check_id in sorted(PARAMETER_CHECKS):
        all_parameters = sorted(
            {
                parameter
                for values in parameter_values[check_id].values()
                for parameter in values
            }
        )
        for parameter in all_parameters:
            values = {
                node: parameter_values[check_id].get(node, {}).get(parameter)
                for node in nodes
            }
            present_values = [value for value in values.values() if value is not None]
            if len(present_values) != len(nodes):
                status = "missing"
            elif len(set(present_values)) == 1:
                status = "matching"
            else:
                status = "different"
            parameter_comparisons.append(
                {
                    "configuration": check_id,
                    "parameter": parameter,
                    "values": values,
                    "status": status,
                }
            )

    hba_sets = [hba_by_node.get(node, set()) for node in nodes]
    common_rules = set.intersection(*hba_sets) if hba_sets else set()
    hba_rules = {node: sorted(hba_by_node.get(node, set())) for node in nodes}

    return {
        "schema_version": "1.0",
        "nodes": nodes,
        "summary": {
            "matching_parameters": sum(
                item["status"] == "matching" for item in parameter_comparisons
            ),
            "different_parameters": sum(
                item["status"] == "different" for item in parameter_comparisons
            ),
            "missing_parameters": sum(
                item["status"] == "missing" for item in parameter_comparisons
            ),
        },
        "parameter_comparisons": parameter_comparisons,
        "pg_hba": {
            "common_rules": sorted(common_rules),
            "rules_by_node": hba_rules,
            "unique_rules_by_node": {
                node: sorted(rules - common_rules)
                for node, rules in hba_by_node.items()
            },
        },
    }
