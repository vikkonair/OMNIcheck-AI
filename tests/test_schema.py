import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omni_healthcheck.schema import CheckResult


ROOT = Path(__file__).parents[1]


def test_checked_in_schema_is_versioned_and_closed() -> None:
    schema = json.loads(
        (ROOT / "schemas/canonical-check-result-1.0.json").read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert schema["additionalProperties"] is False
    assert "trace" in schema["required"]


def test_canonical_check_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        CheckResult.model_validate(
            {
                "schema_version": "1.0",
                "check_id": "hostname",
                "section_id": "3.1",
                "node": "db-primary",
                "node_role": "Primary",
                "product": "OS",
                "collected_at": None,
                "evidence": {
                    "type": "table",
                    "headers": ["Metric", "Value"],
                    "rows": [["Hostname", "db-primary"]],
                },
                "assessment": None,
                "trace": {
                    "parser_id": "os.key_value.v1",
                    "rule_id": None,
                    "evidence_sha256": "a" * 64,
                },
                "unexpected": True,
            }
        )
