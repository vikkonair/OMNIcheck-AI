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


def _rows_check(
    context: ParserContext,
    *,
    parser_id: str,
    check_id: str,
    section_id: str,
    product: str,
    headers: list[str],
    rows: list[list[str]],
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        section_id=section_id,
        node=context.scope_item["node"],
        node_role=context.scope_item["node_role"],
        product=product,
        evidence=TableEvidence(headers=headers, rows=rows),
        trace=Trace(
            parser_id=parser_id,
            evidence_sha256=context.inventory_item["sha256"],
        ),
    )


def _redact_secret_text(value: str) -> str:
    patterns = (
        re.compile(
            r"(?i)((?:db\.)?password(?:\.[a-z0-9_]+)*\s*=\s*)"
            r"(?:'[^']*'|[^\s']+)"
        ),
        re.compile(
            r"(?i)([a-z0-9_.-]*(?:password|passwd|pwd|secret|token|"
            r"api[_-]?key|access[_-]?key|private[_-]?key|wrapper\.key)"
            r"\s*(?:=|:)\s*)(?:'[^']*'|[^\s',;]+)"
        ),
    )
    redacted = value
    for pattern in patterns:
        redacted = pattern.sub(r"\1***MASKED***", redacted)
    return redacted


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

    @classmethod
    def _first_section(cls, text: str, *titles: str) -> str | None:
        return next((body for title in titles if (body := cls._section(text, title))), None)

    @staticmethod
    def _size_to_kb(value: str, unit: str) -> str:
        factors = {"ki": 1, "kib": 1, "kb": 1, "mi": 1024, "mib": 1024, "mb": 1024, "gi": 1048576, "gib": 1048576, "gb": 1048576, "ti": 1073741824, "tib": 1073741824, "tb": 1073741824}
        return str(round(float(value) * factors[unit.casefold()]))

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

        os_section = self._first_section(text, "OS 版本", "OS版本")
        if os_section:
            value = next((line.strip() for line in os_section.splitlines() if line.strip()), None)
            if value:
                extracted.append(("os_version", "3.1", "OS Version", value))

        cpu_section = self._first_section(text, "CPU Core 數", "CPU資訊2")
        if cpu_section:
            match = re.search(r"(?m)^\s*(?:CPU\(s\):\s*)?(\d+)\s*$", cpu_section)
            if match:
                extracted.append(("cpu_count", "3.2", "CPU Count", match.group(1)))
            model = re.search(r"(?m)^Model name:\s*(.+?)\s*$", cpu_section)
            if model:
                extracted.append(("cpu_model", "3.2", "CPU Model", model.group(1)))

        memory_section = self._first_section(text, "記憶體使用量")
        if memory_section:
            for label, check_id, metric in (
                ("Mem", "memory_total_kb", "Memory Total (kB)"),
                ("Swap", "swap_total_kb", "Swap Total (kB)"),
            ):
                match = re.search(rf"(?m)^{label}:\s+([0-9.]+)([KMGT]i?B?)\b", memory_section, re.IGNORECASE)
                if match:
                    extracted.append((check_id, "3.3", metric, self._size_to_kb(*match.groups())))

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


class OSSectionParser:
    parser_id = "os.sections.v1"
    mappings = {
        "CPU 型號": ("cpu_model", "3.2", "OS"),
        "OS 磁碟設備類型": ("disk_devices", "3.4", "OS"),
        "資料磁碟總空間": ("filesystem_usage", "3.4", "OS"),
        "硬碟空間": ("filesystem_usage", "3.4", "OS"),
        "檔案系統的掛載點": ("filesystem_mounts", "3.4", "OS"),
        "掛載點": ("mount_points", "3.4", "OS"),
        "查看ps aux": ("process_state", "3.5", "OS"),
        "檢查網路資訊": ("network_listeners", "3.6", "OS"),
        "Service LAN 網路 IP": ("service_network", "3.6", "OS"),
        "Backup LAN 網路 IP": ("backup_network", "3.6", "OS"),
        "HugePage 設定檢查": ("hugepage_settings", "3.7", "OS"),
        "檢查SELINUX": ("selinux_status", "3.7", "OS"),
        "防火牆設定": ("firewall_status", "3.7", "OS"),
        "防火牆設定狀態檢查": ("firewall_status", "3.7", "OS"),
        "postgresql": (
            "postgresql_conf",
            "4.13",
            "database_configuration",
        ),
        "postgresql.auto.conf": (
            "postgresql_auto_conf",
            "4.14",
            "database_configuration",
        ),
        "pg_hba.conf": (
            "pg_hba_conf",
            "4.12",
            "database_configuration",
        ),
        "EFM": ("efm_status", "3.8", "EFM"),
        "PEM Agent": ("pem_agent_status", "3.8", "PEM"),
        "PEM Server": ("pem_server_status", "3.8", "PEM"),
        "XDB": ("xdb_status", "3.8", "XDB"),
        "PEM / EFM 狀態彙整": ("pem_efm_summary", "3.8", "OS"),
        "pgbackrest": (
            "backup_configuration",
            "3.9",
            "Backup",
        ),
        "Cronjob 設定檢查": ("cron_configuration", "3.9", "OS"),
        "檢查 crontab": ("cron_configuration", "3.9", "OS"),
    }

    @staticmethod
    def _sections(text: str) -> list[tuple[str, str]]:
        matches = list(re.finditer(r"(?m)^=+\s*(.*?)\s*=+\s*$", text))
        sections = []
        for index, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((title, body))
        return sections

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "os":
            return []
        checks = []
        seen = set()
        for title, body in self._sections(context.text):
            mapping = self.mappings.get(title)
            if mapping is None or not body:
                continue
            check_id, section_id, product_kind = mapping
            if product_kind == "database_configuration" and context.scope_item[
                "node_role"
            ] not in {"Primary", "Standby", "DR"}:
                continue
            if check_id == "backup_configuration":
                configured = context.job.backup
                provider = "Barman" if title.casefold() == "barman" else "pgBackRest"
                if configured:
                    if (
                        context.scope_item["node"].casefold()
                        != configured.node.casefold()
                        or provider.casefold() != configured.provider.casefold()
                    ):
                        continue
                elif context.scope_item["node_role"] != "Primary":
                    continue
            if check_id in seen:
                continue
            seen.add(check_id)
            product = (
                context.job.product
                if product_kind == "database_configuration"
                else product_kind
            )
            prefix = []
            if check_id == "backup_configuration":
                prefix = [[f"Provider: {provider}"]]
            rows = [
                [_redact_secret_text(line.rstrip())]
                for line in body.splitlines()
                if line.strip()
            ]
            rows = prefix + rows
            if rows:
                checks.append(
                    _rows_check(
                        context,
                        parser_id=self.parser_id,
                        check_id=check_id,
                        section_id=section_id,
                        product=product,
                        headers=["Output"],
                        rows=rows,
                    )
                )
        return checks


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


class BarmanParser:
    """Parse Barman check/status/list-backup output without database scope."""

    parser_id = "backup.barman.v1"
    markers = (
        "barman check",
        "barman status",
        "barman list-backup",
        "backup maximum age:",
        "retention policy:",
    )

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "os":
            return []
        configured = context.job.backup
        if configured:
            if (
                configured.provider != "barman"
                or context.scope_item["node"].casefold()
                != configured.node.casefold()
            ):
                return []
        elif context.scope_item["node_role"] != "Primary":
            return []
        text = context.text
        barman_section = next(
            (
                body
                for title, body in OSSectionParser._sections(text)
                if title.casefold() == "barman"
            ),
            None,
        )
        candidate = barman_section if barman_section is not None else text
        lowered = candidate.casefold()
        if not any(marker in lowered for marker in self.markers):
            return []
        rows = [["Provider: Barman"]] + [
            [_redact_secret_text(line.rstrip())]
            for line in candidate.splitlines()
            if line.strip()
        ]
        return [
            _rows_check(
                context,
                parser_id=self.parser_id,
                check_id="backup_configuration",
                section_id="3.9",
                product="Backup",
                headers=["Output"],
                rows=rows,
            )
        ]


class PsqlReportParser:
    parser_id = "postgresql.psql_report.v1"
    mappings = {
        "資料庫訊息查看": ("database_information", "4.1"),
        "資料庫重要參數": ("postgresql_auto_conf", "4.14"),
        "List of databases": ("database_inventory", "4.2"),
        "List of installed extensions": ("extensions", "4.3"),
        "資料庫帳號權限": ("roles_privileges", "4.4"),
        "Schema 權限列表": ("schema_privileges", "4.5"),
        "個別 Schema 施加的 Default Privilege 清單": (
            "schema_default_privileges",
            "4.5",
        ),
        "資料庫PROFILE": ("database_profiles", "4.4"),
        "pg_stat_activity 查看": ("connections", "4.6"),
        "TxID Age 與 MxID Age": ("transaction_id_age", "4.7"),
        "空間用量前十大的表格": ("largest_tables", "4.8"),
        "Checkpoint 活動狀況": ("checkpoint_activity", "4.9"),
        "SLRU 狀態": ("slru_status", "4.9"),
        "資料庫 Lock 狀況": ("database_locks", "4.10"),
        "Replication Slot 狀況": ("replication_slots", "4.11"),
        "資料庫同步狀況": ("replication_state", "4.11"),
        "資料庫 SSL 設置狀態": ("ssl_status", "4.12"),
        "曾經 Drop Column 的表格": ("dropped_columns", "4.15"),
        "Dead Tuple 數量前十名表格/最後 AutoVacuum 執行時間": (
            "dead_tuples",
            "4.15",
        ),
        "表格膨脹比例前十名": ("table_bloat", "4.15"),
        "索引膨脹程度前十名": ("index_bloat", "4.15"),
        "罕用索引可能清單": ("rarely_used_indexes", "4.16"),
        "Partitioned Table 清單": ("partitioned_tables", "4.17"),
    }
    omitted_titles = {
        "最後 AutoVacuum 執行時間清單",
        "最後 AutoAnalyze 執行時間清單",
    }

    @classmethod
    def _title_positions(cls, lines: list[str]) -> list[tuple[int, str]]:
        known = set(cls.mappings) | cls.omitted_titles
        return [
            (index, line.strip())
            for index, line in enumerate(lines)
            if line.strip() in known
        ]

    @staticmethod
    def _parse_block(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
        pipe_lines = [
            line
            for line in lines
            if "|" in line
            and not re.fullmatch(r"[\s+|-]+", line)
        ]
        if pipe_lines:
            cells = [
                [_redact_secret_text(cell.strip()) for cell in line.split("|")]
                for line in pipe_lines
            ]
            cells = [
                row[1:-1] if row and row[0] == "" and row[-1] == "" else row
                for row in cells
            ]
            if any(line.lstrip().startswith("-[ RECORD") for line in lines):
                rows = [row[:2] for row in cells if len(row) >= 2 and row[0]]
                return (["Metric", "Value"], rows) if rows else None
            headers = cells[0]
            rows = [row for row in cells[1:] if len(row) == len(headers)]
            return (headers, rows) if headers and rows else None

        output_rows = [
            [_redact_secret_text(line.strip())]
            for line in lines
            if line.strip() and not re.fullmatch(r"\(\d+ rows?\)", line.strip())
        ]
        return (["Output"], output_rows) if output_rows else None

    @staticmethod
    def _apply_policy(
        check_id: str, headers: list[str], rows: list[list[str]]
    ) -> list[list[str]]:
        if check_id in {"schema_privileges", "schema_default_privileges"}:
            return rows[:20]
        if check_id == "rarely_used_indexes":
            index = next(
                (
                    idx
                    for idx, header in enumerate(headers)
                    if header.casefold() == "idx_scan"
                ),
                None,
            )
            if index is not None:
                rows = sorted(
                    rows,
                    key=lambda row: (
                        0 if row[index].strip() == "0" else 1,
                        int(row[index]) if row[index].strip().isdigit() else 10**30,
                    ),
                )
            return rows[:20]
        return rows

    def parse(self, context: ParserContext) -> list[CheckResult]:
        if context.scope_item["evidence_domain"] != "database":
            return []
        lines = context.text.splitlines()
        positions = self._title_positions(lines)
        grouped: dict[str, tuple[str, list[str], list[list[str]]]] = {}

        for position_index, (start, title) in enumerate(positions):
            if title in self.omitted_titles:
                continue
            end = (
                positions[position_index + 1][0]
                if position_index + 1 < len(positions)
                else len(lines)
            )
            block = lines[start + 1 : end]
            parsed = self._parse_block(block)
            if parsed is None and any(
                re.fullmatch(r"\(0 rows?\)", line.strip()) for line in block
            ):
                parsed = (["結果"], [["0 rows（未發現項目）"]])
            if parsed is None:
                continue
            headers, rows = parsed
            check_id, section_id = self.mappings[title]
            rows = self._apply_policy(check_id, headers, rows)
            if not rows:
                continue
            if check_id in grouped and grouped[check_id][1] == headers:
                grouped[check_id][2].extend(
                    row for row in rows if row not in grouped[check_id][2]
                )
            else:
                grouped[check_id] = (section_id, headers, rows)

        return [
            _rows_check(
                context,
                parser_id=self.parser_id,
                check_id=check_id,
                section_id=section_id,
                product=context.job.product,
                headers=headers,
                rows=self._apply_policy(check_id, headers, rows),
            )
            for check_id, (section_id, headers, rows) in grouped.items()
        ]


DEFAULT_PARSERS: tuple[EvidenceParser, ...] = (
    OSKeyValueParser(),
    HealthCheckOSLogParser(),
    OSSectionParser(),
    BarmanParser(),
    DatabaseVersionParser(),
    PsqlReportParser(),
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
