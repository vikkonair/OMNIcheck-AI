"""Command-line interface."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from omni_healthcheck.config import JobConfigError, load_job
from omni_healthcheck.inventory import build_inventory


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omni-healthcheck")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser(
        "generate", help="validate a job and inventory its input evidence"
    )
    generate.add_argument("--job", required=True, type=Path)
    generate.add_argument("--input", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    return parser


def run_generate(job_path: Path, input_dir: Path, output_dir: Path) -> int:
    job = load_job(job_path)
    inventory = build_inventory(input_dir, job)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "inventory.json"
    output_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for unknown_path in inventory["unknown_paths"]:
        print(f"warning: unknown file category: {unknown_path}", file=sys.stderr)
    print(
        f"Wrote {output_path} "
        f"({inventory['summary']['total_files']} files, "
        f"{inventory['summary']['unknown_files']} unknown)"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    args = create_parser().parse_args(argv)
    try:
        if args.command == "generate":
            code = run_generate(args.job, args.input, args.output)
        else:  # pragma: no cover - argparse enforces known subcommands
            code = 2
    except (JobConfigError, FileNotFoundError, NotADirectoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)

