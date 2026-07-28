import hashlib
from pathlib import Path

from omni_healthcheck.config import load_job
from omni_healthcheck.inventory import build_inventory


ROOT = Path(__file__).parents[1]


def test_inventory_recurses_hashes_and_keeps_unknown_files() -> None:
    job = load_job(ROOT / "config/job.example.yaml")
    inventory = build_inventory(ROOT / "tests/fixtures/input", job)

    assert inventory["summary"] == {"total_files": 4, "unknown_files": 1}
    assert inventory["unknown_paths"] == ["misc/notes.bin"]
    assert [item["path"] for item in inventory["files"]] == [
        "db/check.sql",
        "misc/notes.bin",
        "monitoring/cpu.png",
        "os/node-a.txt",
    ]
    text_entry = next(
        item for item in inventory["files"] if item["path"] == "os/node-a.txt"
    )
    expected = hashlib.sha256(
        (ROOT / "tests/fixtures/input/os/node-a.txt").read_bytes()
    ).hexdigest()
    assert text_entry["sha256"] == expected
    assert text_entry["preliminary_category"] == "text"
    assert all(not Path(item["path"]).is_absolute() for item in inventory["files"])


def test_inventory_ignores_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("evidence", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "alias.txt").symlink_to(target)

    job = load_job(ROOT / "config/job.example.yaml")
    inventory = build_inventory(tmp_path, job)
    assert [item["path"] for item in inventory["files"]] == ["target.txt"]

