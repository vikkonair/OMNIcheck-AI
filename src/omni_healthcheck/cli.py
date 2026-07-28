"""Command-line interface."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from omni_healthcheck.config_compare import build_configuration_comparison
from omni_healthcheck.config import JobConfigError, load_job
from omni_healthcheck.inventory import build_inventory
from omni_healthcheck.parsers import normalize_allowed_evidence
from omni_healthcheck.quality import (
    QualityGateError,
    build_coverage_ledger,
    build_qa_result,
)
from omni_healthcheck.rules import RulesConfigError, evaluate_rules, load_rules
from omni_healthcheck.topology import build_scope_ledger, build_topology


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omni-healthcheck")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser(
        "generate", help="validate a job and inventory its input evidence"
    )
    generate.add_argument("--job", required=True, type=Path)
    generate.add_argument("--input", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    generate.add_argument(
        "--rules",
        type=Path,
        default=Path("config/rules.default.yaml"),
    )
    return parser


def run_generate(
    job_path: Path,
    input_dir: Path,
    output_dir: Path,
    rules_path: Path = Path("config/rules.default.yaml"),
) -> int:
    job = load_job(job_path)
    inventory = build_inventory(input_dir, job)
    topology = build_topology(job)
    scope_ledger = build_scope_ledger(input_dir, inventory, job)
    normalized = normalize_allowed_evidence(input_dir, inventory, scope_ledger, job)
    configuration_comparison = build_configuration_comparison(
        normalized,
        topology,
    )
    assessment = evaluate_rules(
        normalized,
        configuration_comparison,
        load_rules(rules_path),
    )
    coverage = build_coverage_ledger(job, normalized, assessment)
    qa_result = build_qa_result(
        job, inventory, scope_ledger, normalized, assessment, coverage
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "inventory.json": inventory,
        "topology.json": topology,
        "scope-ledger.json": scope_ledger,
        "normalized.json": normalized.model_dump(mode="json"),
        "configuration-comparison.json": configuration_comparison,
        "assessment.json": assessment.model_dump(mode="json"),
        "coverage-ledger.json": coverage,
        "qa-result.json": qa_result,
    }
    for filename, content in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    for unknown_path in inventory["unknown_paths"]:
        print(f"warning: unknown file category: {unknown_path}", file=sys.stderr)
    for item in scope_ledger["evidence"]:
        if item["decision"] == "pending":
            print(
                f"warning: evidence pending scope confirmation: {item['path']} "
                f"({item['reason']})",
                file=sys.stderr,
            )
    print(
        f"Wrote {', '.join(str(output_dir / name) for name in outputs)} "
        f"({inventory['summary']['total_files']} files, "
        f"{scope_ledger['summary']['excluded']} excluded, "
        f"{scope_ledger['summary']['pending']} pending)"
    )
    if not qa_result["delivery_allowed"]:
        raise QualityGateError(
            "delivery quality gates failed: "
            + ", ".join(qa_result["failed_gates"])
        )
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    args = create_parser().parse_args(argv)
    try:
        if args.command == "generate":
            code = run_generate(args.job, args.input, args.output, args.rules)
        else:  # pragma: no cover - argparse enforces known subcommands
            code = 2
    except (
        JobConfigError,
        RulesConfigError,
        QualityGateError,
        FileNotFoundError,
        NotADirectoryError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
