"""Versioned deterministic assessment rules with visible evidence references."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from omni_healthcheck.schema import CheckResult, NormalizedDocument


Status = Literal["normal", "attention", "critical", "pending"]


class RuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceReference(RuleModel):
    check_id: str
    node: str
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RuleTrace(RuleModel):
    rule_id: str
    rule_version: str


class Assessment(RuleModel):
    schema_version: Literal["1.0"] = "1.0"
    check_id: str
    section_id: str
    node: str
    status: Status
    observation: str
    recommendation: str
    evidence_refs: list[EvidenceReference] = Field(min_length=1)
    trace: RuleTrace


class AssessmentDocument(RuleModel):
    schema_version: Literal["1.0"] = "1.0"
    ruleset_version: str
    summary: dict[str, int]
    assessments: list[Assessment]


class RulesConfigError(ValueError):
    pass


def load_rules(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RulesConfigError(f"cannot load rules configuration: {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != "1.0":
        raise RulesConfigError("rules configuration must use schema_version 1.0")
    return raw


def _ref(check: CheckResult) -> EvidenceReference:
    return EvidenceReference(
        check_id=check.check_id,
        node=check.node,
        evidence_sha256=check.trace.evidence_sha256,
    )


def _assessment(
    check: CheckResult,
    *,
    status: Status,
    rule_id: str,
    ruleset_version: str,
    explanation: str,
    conclusion: str,
    recommendation: str,
) -> Assessment:
    return Assessment(
        check_id=check.check_id,
        section_id=check.section_id,
        node=check.node,
        status=status,
        observation=f"{explanation}\n結論：{conclusion}",
        recommendation=recommendation,
        evidence_refs=[_ref(check)],
        trace=RuleTrace(rule_id=rule_id, rule_version=ruleset_version),
    )


def _output_text(check: CheckResult) -> str:
    return "\n".join(" | ".join(row) for row in check.evidence.rows)


def _filesystem_assessment(
    check: CheckResult, config: dict, version: str
) -> Assessment | None:
    percentages = [
        int(value)
        for value in re.findall(r"(?<!\d)(\d{1,3})%", _output_text(check))
        if 0 <= int(value) <= 100
    ]
    if not percentages:
        return None
    usage = max(percentages)
    observe = int(config["observe_percent"])
    attention = int(config["attention_percent"])
    if usage >= attention:
        status: Status = "attention"
        conclusion = f"檔案系統使用率已達注意門檻 {attention}% 以上。"
        recommendation = "請確認成長趨勢並規劃清理或擴充。"
    elif usage >= observe:
        status = "normal"
        conclusion = "目前容量尚未達注意門檻，但需持續觀察量體成長。"
        recommendation = "請隨時觀察量體成長速度，並維持容量監控與告警。"
    else:
        status = "normal"
        conclusion = "目前容量仍在設定門檻內。"
        recommendation = "維持容量監控與告警。"
    return _assessment(
        check,
        status=status,
        rule_id="os.filesystem_usage.v1",
        ruleset_version=version,
        explanation=f"{check.node} 目前可見最高檔案系統使用率為 {usage}%。",
        conclusion=conclusion,
        recommendation=recommendation,
    )


def _txid_assessment(
    check: CheckResult, config: dict, version: str
) -> Assessment | None:
    try:
        index = [header.casefold() for header in check.evidence.headers].index("txid_age")
    except ValueError:
        return None
    ages = [
        int(row[index])
        for row in check.evidence.rows
        if len(row) > index and row[index].isdigit()
    ]
    if not ages:
        return None
    age = max(ages)
    warning = int(config["warning"])
    critical = int(config["critical"])
    if age >= critical:
        status: Status = "critical"
        conclusion = "交易 ID 年齡已達重大門檻。"
        recommendation = "請立即確認 autovacuum freeze 狀態並安排 VACUUM FREEZE。"
    elif age >= warning:
        status = "attention"
        conclusion = "交易 ID 年齡已達注意門檻。"
        recommendation = "請追蹤成長速度並規劃 VACUUM FREEZE。"
    else:
        status = "normal"
        conclusion = "交易 ID 年齡目前仍在設定門檻內。"
        recommendation = "持續追蹤 TxID 年齡與凍結維護狀態。"
    return _assessment(
        check,
        status=status,
        rule_id="database.txid_age.v1",
        ruleset_version=version,
        explanation=f"Primary 可見最高 TxID age 為 {age:,}。",
        conclusion=conclusion,
        recommendation=recommendation,
    )


def _replication_assessment(check: CheckResult, version: str) -> Assessment | None:
    headers = [header.casefold() for header in check.evidence.headers]
    if "state" not in headers:
        return None
    index = headers.index("state")
    states = [
        row[index].casefold()
        for row in check.evidence.rows
        if len(row) > index and row[index]
    ]
    normal = bool(states) and all(state == "streaming" for state in states)
    return _assessment(
        check,
        status="normal" if normal else "attention",
        rule_id="database.replication_state.v1",
        ruleset_version=version,
        explanation=f"Primary 可見 replication state：{', '.join(states) or '無資料'}。",
        conclusion="複寫連線目前為 streaming。" if normal else "複寫狀態需進一步確認。",
        recommendation="持續監控 replication lag。"
        if normal
        else "請確認 Standby／DR 連線與 replication lag。",
    )


def _database_locks_assessment(check: CheckResult, version: str) -> Assessment | None:
    zero_rows = check.evidence.rows == [["0 rows（未發現項目）"]]
    if not zero_rows:
        return None
    return _assessment(
        check,
        status="normal",
        rule_id="database.locks.v1",
        ruleset_version=version,
        explanation="健檢當下 Lock 查詢結果為 0 rows。",
        conclusion="未發現資料庫 Lock 阻塞項目。",
        recommendation="持續監控長交易、blocking session 與 lock wait。",
    )


def _idle_transaction_assessment(
    check: CheckResult, version: str
) -> Assessment | None:
    if check.evidence.headers != ["Output"]:
        return None
    values = [
        int(row[0])
        for row in check.evidence.rows
        if row and row[0].strip().isdigit()
    ]
    if not values:
        return None
    count = values[-1]
    return _assessment(
        check,
        status="normal" if count == 0 else "attention",
        rule_id="database.idle_in_transaction.v1",
        ruleset_version=version,
        explanation=f"健檢當下 idle in transaction 數量為 {count}。",
        conclusion="未見 idle in transaction。" if count == 0 else "存在閒置交易需處理。",
        recommendation="維持監控。"
        if count == 0
        else "請檢查應用交易邏輯並設定適當的 idle timeout。",
    )


def _candidate_assessment(
    check: CheckResult, status: Status, version: str
) -> Assessment:
    labels = {
        "table_bloat": ("表格膨脹", "維護時段評估 VACUUM FULL 或重整。"),
        "index_bloat": ("索引膨脹", "依空間與查詢影響排序評估 REINDEX。"),
        "dead_tuples": ("Dead Tuple", "檢查高 dead tuple 表的更新模式與 autovacuum 門檻。"),
        "rarely_used_indexes": ("罕用索引", "確認實際工作負載後再決定是否移除。"),
    }
    label, recommendation = labels[check.check_id]
    if check.check_id in {"table_bloat", "index_bloat"}:
        headers = [header.casefold().strip() for header in check.evidence.headers]
        bloat_index = next(
            (index for index, header in enumerate(headers) if "bloat" in header or "膨脹" in header),
            None,
        )
        name_indexes = [
            index
            for index, header in enumerate(headers)
            if header in {
                "current_database", "database", "schemaname", "schema_name",
                "tablename", "table_name", "iname", "indexname", "index_name",
            }
        ]
        candidates: list[tuple[str, str]] = []
        if bloat_index is not None:
            for row in check.evidence.rows:
                if bloat_index >= len(row):
                    continue
                match = re.search(r"-?\d+(?:\.\d+)?", row[bloat_index].replace(",", ""))
                if match and float(match.group()) > 2:
                    object_name = ".".join(
                        row[index].strip()
                        for index in name_indexes
                        if index < len(row) and row[index].strip()
                    )
                    candidates.append((object_name or "未命名物件", match.group()))
        action = "VACUUM FULL" if check.check_id == "table_bloat" else "REINDEX"
        if candidates:
            listed = "、".join(f"{name}（{value}）" for name, value in candidates)
            actions = "；".join(f"{name}：{action}" for name, _ in candidates)
            explanation = (
                f"Primary 膨脹前十名輸出中，膨脹指數高於 2 的{label}物件為：{listed}。"
            )
            conclusion = f"上述 {len(candidates)} 個物件需安排維護處理。"
            recommendation = f"建議處置：{actions}。執行前請安排維護時段並確認可接受的鎖定影響。"
            assessment_status: Status = status
        else:
            explanation = f"Primary 膨脹前十名輸出中，未發現膨脹指數高於 2 的{label}物件。"
            conclusion = f"目前前十名清單未見需處理的{label}候選。"
            recommendation = "持續定期檢查膨脹指數。"
            assessment_status = "normal"
        return _assessment(
            check,
            status=assessment_status,
            rule_id=f"database.{check.check_id}.candidate.v1",
            ruleset_version=version,
            explanation=explanation,
            conclusion=conclusion,
            recommendation=recommendation,
        )
    return _assessment(
        check,
        status=status,
        rule_id=f"database.{check.check_id}.candidate.v1",
        ruleset_version=version,
        explanation=f"Primary 輸出列出 {len(check.evidence.rows)} 筆{label}候選項目。",
        conclusion=f"{label}清單需依工作負載與維護時窗複核。",
        recommendation=recommendation,
    )


def _backup_assessment(check: CheckResult, version: str) -> Assessment:
    output = _output_text(check)
    lowered = output.casefold()
    provider = next(
        (
            row[0].partition(":")[2].strip()
            for row in check.evidence.rows
            if row and row[0].casefold().startswith("provider:")
        ),
        "Backup",
    )
    has_error = any(
        marker in lowered
        for marker in (
            "no such file",
            "error",
            "failed",
            "fatal",
            "check failed",
        )
    )
    if provider.casefold() == "pgbackrest":
        stanza_headers = list(
            re.finditer(r"(?im)^\s*stanza:\s*([^\s|]+)", output)
        )
        stanza_statuses = []
        for index, header in enumerate(stanza_headers):
            block_end = (
                stanza_headers[index + 1].start()
                if index + 1 < len(stanza_headers)
                else len(output)
            )
            status_match = re.search(
                r"(?im)^\s*status:\s*([^\r\n|]+)",
                output[header.end() : block_end],
            )
            if status_match:
                stanza_statuses.append(
                    (header.group(1).strip(), status_match.group(1).strip())
                )
        primary_candidates = [
            item
            for item in stanza_statuses
            if not re.search(r"(?:^|[-_])(dr|standby|replica)(?:$|[-_])", item[0], re.I)
            and not item[0].casefold().endswith("dr")
        ]
        if len(primary_candidates) == 1:
            stanza, stanza_status = primary_candidates[0]
            is_ok = stanza_status.casefold() == "ok"
            other_statuses = [
                f"{name}={status}"
                for name, status in stanza_statuses
                if name.casefold() != stanza.casefold()
            ]
            other_note = (
                f"；另偵測到其他 stanza：{'、'.join(other_statuses)}，應獨立確認其用途與狀態"
                if other_statuses
                else ""
            )
            return _assessment(
                check,
                status="normal" if is_ok else "attention",
                rule_id="os.backup_configuration.pgbackrest_stanza.v2",
                ruleset_version=version,
                explanation=(
                    f"{check.node} 的 pgBackRest 主要備份 stanza `{stanza}` 回報 "
                    f"`status: {stanza_status}`{other_note}。"
                ),
                conclusion=(
                    f"主要備份 stanza `{stanza}` 狀態正常。"
                    if is_ok
                    else f"主要備份 stanza `{stanza}` 狀態異常，需進一步確認。"
                ),
                recommendation=(
                    f"建議持續監控 stanza `{stanza}` 的備份結果與 WAL 歸檔，並定期執行還原驗證。"
                    if is_ok
                    else f"請檢查 stanza `{stanza}` 的 pgBackRest 日誌、儲存庫與最近成功備份，排除異常後執行還原驗證。"
                ),
            )
        if stanza_statuses:
            listed = "、".join(f"{name}={status}" for name, status in stanza_statuses)
            return _assessment(
                check,
                status="pending",
                rule_id="os.backup_configuration.pgbackrest_stanza.v2",
                ruleset_version=version,
                explanation=f"{check.node} 偵測到多個無法唯一對應主要備份的 pgBackRest stanza：{listed}。",
                conclusion="目前無法安全判定哪一個 stanza 代表主要資料庫備份。",
                recommendation="請確認主要資料庫對應的 pgBackRest stanza，再依該 stanza 的 status 與最近成功備份進行判斷。",
            )
    return _assessment(
        check,
        status="attention" if has_error else "normal",
        rule_id="os.backup_configuration.v1",
        ruleset_version=version,
        explanation=f"{check.node} 已收集 {provider} 備份設定與狀態輸出。",
        conclusion="輸出中出現需確認的錯誤訊息。" if has_error else "未見明確備份設定錯誤。",
        recommendation="請確認備份路徑、排程與最近成功紀錄。"
        if has_error
        else "維持備份成功率與還原演練追蹤。",
    )


def _schema_privilege_assessment(
    check: CheckResult, version: str
) -> Assessment:
    text = _output_text(check).casefold()
    public_create = "public" in text and "create" in text
    return _assessment(
        check,
        status="attention" if public_create else "normal",
        rule_id="database.schema_privileges.v1",
        ruleset_version=version,
        explanation=f"Primary 已檢查 {len(check.evidence.rows)} 筆 schema 權限。",
        conclusion="發現 PUBLIC CREATE 權限需複核。"
        if public_create
        else "抽樣範圍未見明確 PUBLIC CREATE 風險。",
        recommendation="請確認 PUBLIC CREATE 是否符合權限基準。"
        if public_create
        else "下次健檢持續比對權限增減。",
    )


def _roles_privilege_assessment(
    check: CheckResult,
    config: dict,
    version: str,
) -> Assessment | None:
    headers = [header.casefold() for header in check.evidence.headers]
    required = {"role_name", "is_superuser", "can_create_role", "can_create_db"}
    if not required <= set(headers):
        return None
    indexes = {header: headers.index(header) for header in required}
    allowed = {
        role.casefold() for role in config["allowed_elevated_roles"]
    }
    elevated = []
    for row in check.evidence.rows:
        if len(row) < len(headers):
            continue
        role = row[indexes["role_name"]]
        has_capability = any(
            row[indexes[field]].casefold() == "t"
            for field in ("is_superuser", "can_create_role", "can_create_db")
        )
        if has_capability and role.casefold() not in allowed:
            elevated.append(role)
    return _assessment(
        check,
        status="pending" if elevated else "normal",
        rule_id="database.roles_privileges.v1",
        ruleset_version=version,
        explanation=f"Primary 已檢查 {len(check.evidence.rows)} 個資料庫角色。",
        conclusion=(
            f"發現 {len(elevated)} 個非基準角色具有 elevated capability，需確認。"
            if elevated
            else "未見基準外角色具有 Superuser、Create role 或 Create DB。"
        ),
        recommendation="請複核 elevated role 是否為核准需求並落實最小權限。"
        if elevated
        else "持續定期比對角色權限增減。",
    )


def _configuration_assessments(
    normalized: NormalizedDocument,
    comparison: dict,
    config: dict,
    version: str,
) -> list[Assessment]:
    checks = [
        check
        for check in normalized.checks
        if check.check_id in {"postgresql_conf", "postgresql_auto_conf"}
        and check.node_role in {"Primary", "Standby", "DR"}
    ]
    refs_by_configuration = {
        check_id: [_ref(check) for check in checks if check.check_id == check_id]
        for check_id in {"postgresql_conf", "postgresql_auto_conf"}
    }
    ignored = set(config["ignored_role_specific_parameters"])
    important = set(config["important_parameters"])
    assessments = []
    for item in comparison["parameter_comparisons"]:
        if item["status"] == "matching" or item["parameter"] in ignored:
            continue
        refs = refs_by_configuration.get(item["configuration"], [])
        if not refs:
            continue
        status: Status = (
            "attention" if item["parameter"] in important else "pending"
        )
        conclusion = (
            "重要效能參數在節點間不一致。"
            if status == "attention"
            else "此參數差異需確認是否為預期角色設定。"
        )
        assessments.append(
            Assessment(
                check_id="configuration_consistency",
                section_id="4.14",
                node="cluster",
                status=status,
                observation=(
                    f"{item['parameter']} 的跨節點狀態為 {item['status']}。\n"
                    f"結論：{conclusion}"
                ),
                recommendation="請確認差異是否為核准基準；非預期時同步設定並 reload。",
                evidence_refs=refs,
                trace=RuleTrace(
                    rule_id="database.configuration_consistency.v1",
                    rule_version=version,
                ),
            )
        )
    return assessments


def _hba_assessments(
    normalized: NormalizedDocument,
    comparison: dict,
    version: str,
) -> list[Assessment]:
    checks = {
        check.node: check
        for check in normalized.checks
        if check.check_id == "pg_hba_conf"
        and check.node_role in {"Primary", "Standby", "DR"}
    }
    assessments = []
    for node, rules in comparison["pg_hba"]["rules_by_node"].items():
        check = checks.get(node)
        if check is None:
            continue
        unsafe = [
            rule
            for rule in rules
            if rule.casefold().endswith(" trust")
            and "127.0.0.1" not in rule
            and "::1" not in rule
        ]
        assessments.append(
            _assessment(
                check,
                status="attention" if unsafe else "normal",
                rule_id="database.hba_trust.v1",
                ruleset_version=version,
                explanation=f"{node} 共解析 {len(rules)} 條 pg_hba.conf 規則。",
                conclusion="發現非本機 trust 規則需複核。"
                if unsafe
                else "未見明確非本機 trust 規則。",
                recommendation="請確認 trust 是否必要，並優先改用 scram-sha-256。"
                if unsafe
                else "下次健檢持續比對規則變更。",
            )
        )
    return assessments


def evaluate_rules(
    normalized: NormalizedDocument,
    configuration_comparison: dict,
    rules_config: dict,
) -> AssessmentDocument:
    version = str(rules_config["ruleset_version"])
    assessments: list[Assessment] = []
    candidate_config = rules_config["candidate_lists"]

    for check in normalized.checks:
        assessment = None
        if check.check_id == "filesystem_usage":
            assessment = _filesystem_assessment(
                check, rules_config["filesystem_usage"], version
            )
        elif check.check_id == "transaction_id_age":
            assessment = _txid_assessment(
                check, rules_config["transaction_id_age"], version
            )
        elif check.check_id == "replication_state":
            assessment = _replication_assessment(check, version)
        elif check.check_id == "database_locks":
            assessment = _database_locks_assessment(check, version)
        elif check.check_id == "connections":
            assessment = _idle_transaction_assessment(check, version)
        elif check.check_id in candidate_config:
            assessment = _candidate_assessment(
                check, candidate_config[check.check_id], version
            )
        elif check.check_id == "backup_configuration":
            assessment = _backup_assessment(check, version)
        elif check.check_id == "schema_privileges":
            assessment = _schema_privilege_assessment(check, version)
        elif check.check_id == "roles_privileges":
            assessment = _roles_privilege_assessment(
                check, rules_config["roles_privileges"], version
            )
        if assessment is not None:
            assessments.append(assessment)

    assessments.extend(
        _configuration_assessments(
            normalized,
            configuration_comparison,
            rules_config["configuration_consistency"],
            version,
        )
    )
    if rules_config["hba"]["flag_nonlocal_trust"]:
        assessments.extend(
            _hba_assessments(normalized, configuration_comparison, version)
        )

    summary_counter = Counter(assessment.status for assessment in assessments)
    summary = {
        status: summary_counter.get(status, 0)
        for status in ("normal", "attention", "critical", "pending")
    }
    return AssessmentDocument(
        ruleset_version=version,
        summary=summary,
        assessments=assessments,
    )
