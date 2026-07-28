"""Deterministic parser framework and initial OS/database parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from omni_healthcheck import __version__
from omni_healthcheck.config import JobConfig
from omni_healthcheck.schema import (
    CheckResult,
    NormalizedDocument,
    TableEvidence,
    Trace,
    UnparsedEvidence,
)


@dataclass(frozen=True)
class ParserContext:
    path: Path
    inventory_item: dict
    scope_item: dict
    job: JobConfig

    @property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace")


class EvidenceParser(Protocol):
    parser_id: str

    def parse(self, context: ParserContext) -> list[CheckResult]:
        """Return zero or more canonical checks."""


def _table_check(
    context: ParserContext,
    *,
    parser_id: str,
    check_id: str,
    section_id: str,
    product: str,
    metric: str,
    value: str,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        section_id=section_id,
        node=context.scope_item["node"],
        node_role=context.scope_item["node_role"],
        product=product,
        evidence=TableEvidence(
            headers=["Metric", "Value"],
            rows=[[metric, value]],
        ),
        trace=Trace(
            parser_id=parser_id,
            evidence_sha256=context.inventory_item["sha256"],
        ),
    )


class OSKeyValueParser:
    parser_id = "os.key_value.v1"
    patterns = {
        "hostname": (
            "3.1",
            "Hostname",
            re.compile(r"(?im)^\s*hostname\s*[:=]\s*(\S+)\s*$"),
        ),
        "os_version": (
            "3.1",
            "OS Version",
            re.compile(r'(?im)^\s*(?:os|os_version|pretty_name)\s*[:=]\s*"?([^"\n]+)'),
        ),
        "kernel_version": (
            "3.1",
            "Kernel Version",
            re.compile(r"(?im)^\s*(?:kernel|kernel_version)\s*[:=]\s*(.+?)\s*$"),
        ),
        "cpu_count": (
            "3.2",
            "CPU Count",
            re.compile(r"(?im)^\s*(?:cpu_count|cpu\(s\))\s*[:=]\s*(\d+)\s*$"),
        ),
        "memory_total_kb": (
            "3.3",
            "Memory Total (kB)",
            re.compile(r"(?im)^\s*memtotal\s*[:=]\s*(\d+)\s*(?:kb)?\s*$"),
        ),
        "swap_total_kb": (
            "3.3",
            "Swap Total (kB)",
            re.compile(r"(?im)^\s*swaptotal\s*[:=]\s*(\d+)\s*(?:kb)?\s*$"),
        ),
    }

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "os":
            return []
        text = context.text
        checks = []
        for check_id, (section_id, metric, pattern) in self.patterns.items():
            match = pattern.search(text)
            if match:
                checks.append(
                    _table_check(
                        context,
                        parser_id=self.parser_id,
                        check_id=check_id,
                        section_id=section_id,
                        product="OS",
                        metric=metric,
                        value=match.group(1).strip(),
                    )
                )
        return checks


class HealthCheckOSLogParser:
    parser_id = "os.healthcheck_log.v1"

    @staticmethod
    def _section(text: str, title: str) -> str | None:
        pattern = re.compile(
            rf"(?ms)^=+\s*{re.escape(title)}\s*=+\s*$\n(.*?)(?=^=+|\Z)"
        )
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "os":
            return []
        text = context.text
        extracted = []

        hostname_section = self._section(text, "主機名稱")
        if hostname_section:
            configured_hostname = context.scope_item["node"]
            lines = [line.strip() for line in hostname_section.splitlines() if line.strip()]
            value = next(
                (
                    line
                    for line in lines
                    if line.casefold() == configured_hostname.casefold()
                ),
                lines[-1] if lines else None,
            )
            if value:
                extracted.append(("hostname", "3.1", "Hostname", value))

        os_section = self._section(text, "OS 版本")
        if os_section:
            value = next((line.strip() for line in os_section.splitlines() if line.strip()), None)
            if value:
                extracted.append(("os_version", "3.1", "OS Version", value))

        cpu_section = self._section(text, "CPU Core 數")
        if cpu_section:
            match = re.search(r"(?m)^\s*(\d+)\s*$", cpu_section)
            if match:
                extracted.append(("cpu_count", "3.2", "CPU Count", match.group(1)))

        return [
            _table_check(
                context,
                parser_id=self.parser_id,
                check_id=check_id,
                section_id=section_id,
                product="OS",
                metric=metric,
                value=value,
            )
            for check_id, section_id, metric, value in extracted
        ]


class DatabaseVersionParser:
    parser_id = "postgresql.version.v1"
    pattern = re.compile(
        r"(?im)\b(PostgreSQL|EnterpriseDB|EDB Postgres Advanced Server|EPAS)"
        r"\s+(\d+(?:\.\d+)+)"
    )

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "database":
            return []
        match = self.pattern.search(context.text)
        if not match:
            return []
        detected_product = match.group(1).casefold()
        product = (
            "EPAS"
            if context.job.product == "EPAS"
            or "enterprisedb" in context.text.casefold()
            or detected_product != "postgresql"
            else "PostgreSQL"
        )
        return [
            _table_check(
                context,
                parser_id=self.parser_id,
                check_id="database_version",
                section_id="4.1",
                product=product,
                metric="Database Version",
                value=f"{match.group(1)} {match.group(2)}",
            )
        ]


DEFAULT_PARSERS: tuple[EvidenceParser, ...] = (
    OSKeyValueParser(),
    HealthCheckOSLogParser(),
    DatabaseVersionParser(),
)


def normalize_allowed_evidence(
    input_dir: Path,
    inventory: dict,
    scope_ledger: dict,
    job: JobConfig,
    parsers: tuple[EvidenceParser, ...] = DEFAULT_PARSERS,
) -> NormalizedDocument:
    inventory_by_path = {item["path"]: item for item in inventory["files"]}
    checks = []
    unparsed = []

    for scope_item in scope_ledger["evidence"]:
        if scope_item["decision"] != "allowed":
            continue
        inventory_item = inventory_by_path[scope_item["path"]]
        if inventory_item["preliminary_category"] not in {"text", "sql", "table"}:
            unparsed.append(
                UnparsedEvidence(
                    sha256=inventory_item["sha256"],
                    reason="no deterministic text parser for evidence category",
                )
            )
            continue

        context = ParserContext(
            path=input_dir / scope_item["path"],
            inventory_item=inventory_item,
            scope_item=scope_item,
            job=job,
        )
        parsed_checks = [
            check for parser in parsers for check in parser.parse(context)
        ]
        if parsed_checks:
            checks.extend(parsed_checks)
        else:
            unparsed.append(
                UnparsedEvidence(
                    sha256=inventory_item["sha256"],
                    reason="no parser matched allowed evidence",
                )
            )

    return NormalizedDocument(
        pipeline_version=__version__,
        checks=checks,
        unparsed_allowed_evidence=unparsed,
    )
