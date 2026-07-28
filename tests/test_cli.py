import json
from pathlib import Path

import pytest

from omni_healthcheck.cli import run_generate
from omni_healthcheck.quality import QualityGateError


ROOT = Path(__file__).parents[1]


def test_generate_writes_inventory_and_warns_for_unknown(
    tmp_path: Path, capsys
) -> None:
    output_dir = tmp_path / "output"
    with pytest.raises(QualityGateError, match="primary_database_present"):
        run_generate(
            ROOT / "config/job.example.yaml",
            ROOT / "tests/fixtures/input",
            output_dir,
        )

    inventory = json.loads((output_dir / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["summary"]["total_files"] == 4
    assert (output_dir / "topology.json").is_file()
    normalized = json.loads(
        (output_dir / "normalized.json").read_text(encoding="utf-8")
    )
    comparison = json.loads(
        (output_dir / "configuration-comparison.json").read_text(encoding="utf-8")
    )
    assessment = json.loads(
        (output_dir / "assessment.json").read_text(encoding="utf-8")
    )
    coverage = json.loads(
        (output_dir / "coverage-ledger.json").read_text(encoding="utf-8")
    )
    qa_result = json.loads(
        (output_dir / "qa-result.json").read_text(encoding="utf-8")
    )
    assert comparison["nodes"] == ["gwcymsedb"]
    assert assessment["ruleset_version"] == "2026.1"
    assert coverage["summary"]["missing"] > 0
    assert qa_result["delivery_allowed"] is False
    assert normalized["schema_version"] == "1.0"
    assert {check["check_id"] for check in normalized["checks"]} == {
        "hostname",
        "cpu_count",
    }
    scope = json.loads(
        (output_dir / "scope-ledger.json").read_text(encoding="utf-8")
    )
    assert scope["summary"]["pending"] == 3
    captured = capsys.readouterr()
    assert "misc/notes.bin" in captured.err
    assert "Wrote" in captured.out


def test_generate_passes_delivery_gates_for_multi_node_fixture(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    result = run_generate(
        ROOT / "tests/fixtures/multi_node/job.yaml",
        ROOT / "tests/fixtures/multi_node/input",
        output_dir,
    )

    assert result == 0
    qa_result = json.loads(
        (output_dir / "qa-result.json").read_text(encoding="utf-8")
    )
    assert qa_result["status"] == "passed"
    assert qa_result["delivery_allowed"] is True
    assert qa_result["summary"]["failed"] == 0
