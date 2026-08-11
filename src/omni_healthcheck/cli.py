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
from omni_healthcheck.reporting import build_report_model
from omni_healthcheck.rules import RulesConfigError, evaluate_rules, load_rules
from omni_healthcheck.section_workflow import build_section_workflow
from omni_healthcheck.topology import build_scope_ledger, build_topology
from omni_healthcheck.v4_adapter import build_v4_report
from omni_healthcheck.v4_quality import V4QualityError, validate_v4_report


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
    section_workflow = build_section_workflow(assessment)
    coverage = build_coverage_ledger(job, normalized, assessment)
    qa_result = build_qa_result(
        job, inventory, scope_ledger, normalized, assessment, coverage
    )
    report_model = build_report_model(
        job, topology, normalized, assessment, coverage, configuration_comparison
    )
    v4_report = build_v4_report(report_model, scope_ledger, input_dir)
    v4_qa = validate_v4_report(
        v4_report, scope_ledger, raise_on_failure=False
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "inventory.json": inventory,
        "topology.json": topology,
        "scope-ledger.json": scope_ledger,
        "normalized.json": normalized.model_dump(mode="json"),
        "configuration-comparison.json": configuration_comparison,
        "assessment.json": assessment.model_dump(mode="json"),
        "section-workflow.json": section_workflow.model_dump(mode="json"),
        "coverage-ledger.json": coverage,
        "qa-result.json": qa_result,
        "report-model.json": report_model.model_dump(mode="json"),
        "v4-report.json": v4_report,
        "v4-qa-result.json": v4_qa,
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
    if job.report.output_docx or job.report.output_pdf:
        from omni_healthcheck.docx_renderer import convert_docx_to_pdf
        from omni_healthcheck.v4_renderer import render_v4_docx

        if not v4_qa["delivery_allowed"]:
            raise V4QualityError(
                "V4 report quality gates failed: "
                + "; ".join(v4_qa["failed_gates"])
            )

        docx_path = output_dir / "report.docx"
        render_v4_docx(v4_report, docx_path)
        if job.report.output_pdf:
            convert_docx_to_pdf(docx_path, output_dir / "report.pdf")
        if not job.report.output_docx:
            docx_path.unlink()
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
        RuntimeError,
        V4QualityError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
