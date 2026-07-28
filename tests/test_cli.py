import json
from pathlib import Path

from omni_healthcheck.cli import run_generate


ROOT = Path(__file__).parents[1]


def test_generate_writes_inventory_and_warns_for_unknown(
    tmp_path: Path, capsys
) -> None:
    output_dir = tmp_path / "output"
    result = run_generate(
        ROOT / "config/job.example.yaml",
        ROOT / "tests/fixtures/input",
        output_dir,
    )

    assert result == 0
    inventory = json.loads((output_dir / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["summary"]["total_files"] == 4
    assert (output_dir / "topology.json").is_file()
    normalized = json.loads(
        (output_dir / "normalized.json").read_text(encoding="utf-8")
    )
    comparison = json.loads(
        (output_dir / "configuration-comparison.json").read_text(encoding="utf-8")
    )
    assert comparison["nodes"] == ["gwcymsedb"]
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
