import hashlib
from pathlib import Path

import pytest

from omni_healthcheck.reporting import ReportModel
from omni_healthcheck.v4_adapter import _prepare_unit, build_v4_report
from omni_healthcheck.v4_quality import V4QualityError, validate_v4_report
from omni_healthcheck.v4_renderer import VENDOR_RENDERER
from omni_healthcheck.docx_renderer import _font_config_for_platform


ROOT = Path(__file__).parents[1]


def test_linux_pdf_conversion_uses_system_fontconfig() -> None:
    assert _font_config_for_platform("linux") is None


def test_macos_pdf_conversion_uses_project_fallback() -> None:
    path = _font_config_for_platform("darwin")
    assert path is not None
    assert path.name == "fonts.macos.conf"


def _model() -> ReportModel:
    return ReportModel(
        customer="測試客戶",
        system_name="db-system",
        period="2026-H1",
        engineer="XXX",
        product="EPAS",
        nodes=[
            {"hostname": "db-primary", "role": "Primary", "services": ["EFM"]},
            {"hostname": "db-standby", "role": "Standby", "services": ["EFM"]},
        ],
        summary={"normal": 1, "attention": 1, "critical": 0, "pending": 0},
        sections=[
            {
                "section_id": "3",
                "title": "作業系統健檢",
                "groups": [
                    {
                        "title": "3.1 主機與組態設定",
                        "units": [
                            {
                                "title": "主機彙整",
                                "headers": ["項目", "db-primary\nPrimary", "db-standby\nStandby"],
                                "rows": [
                                    ["作業系統", "RHEL 8", "RHEL 8"],
                                    ["CPU Core 數", "8", "8"],
                                    ["記憶體", "64 GB", "64 GB"],
                                ],
                                "omitted_rows": 0,
                                "assessment": None,
                            }
                        ],
                    }
                ],
            },
            {
                "section_id": "4",
                "title": "PostgreSQL 資料庫健檢",
                "groups": [
                    {
                        "title": "4.1 組態與安全設定",
                        "units": [
                            {
                                "title": "版本資訊",
                                "headers": ["Metric", "Value"],
                                "rows": [["Database Version", "PostgreSQL 16.14"]],
                                "omitted_rows": 0,
                                "assessment": None,
                            },
                            {
                                "title": "Primary postgresql.auto.conf",
                                "headers": ["Output"],
                                "rows": [["shared_buffers = '8GB'"]],
                                "omitted_rows": 0,
                                "assessment": {
                                    "status": "attention",
                                    "status_label": "注意",
                                    "observation": "跨節點比較有 1 項差異\n結論：本項需注意",
                                    "recommendation": "確認角色必要差異",
                                },
                            }
                        ],
                    }
                ],
            },
        ],
        findings=[],
        coverage={"coverage_percent": 100},
        cve={"status": "pending"},
    )


def test_adapter_preserves_primary_database_and_configuration_observation(
    tmp_path: Path,
) -> None:
    report = build_v4_report(
        _model(),
        {"evidence": []},
        tmp_path,
    )
    assert report["database_source_hostname"] == "db-primary"
    section_items = report["chapters"][1]["sections"][0]["items"]
    item = next(item for item in section_items if "postgresql.auto.conf" in item["title"])
    assert item["node"] == "db-primary"
    assert item["status"] == "注意"
    assert "跨節點比較" in item["observation"]
    assert item["controlled_continuation"] is True
    assert report["nodes"][0]["cpu"] == "8 cores"
    assert report["product"]["name"] == "EDB Postgres Advanced Server"
    assert report["cover_company_name"] == "Omniwaresoft Tech"
    assert report["show_components"] is False
    version = next(item for item in section_items if item["title"] == "版本資訊")
    assert version["evidence"]["rows"] == [
        ["Database Version", "EDB Postgres Advanced Server 16.14"]
    ]


def test_adapter_applies_requested_report_limits_and_database_columns() -> None:
    inventory = _prepare_unit(
        {
            "title": "資料庫清單",
            "headers": [
                "Name", "Owner", "Encoding", "Access privileges", "Size", "Description"
            ],
            "rows": [["app", "owner", "UTF8", "=Tc/owner", "10 GB", "omit me"]],
        }
    )
    assert inventory["headers"] == ["資料庫名稱", "擁有者", "權限", "大小"]
    assert inventory["rows"] == [["app", "owner", "=Tc/owner", "10 GB"]]

    txid = _prepare_unit(
        {
            "title": "Transaction ID 年齡",
            "headers": ["table", "txid_age"],
            "rows": [[f"t{value}", str(value)] for value in range(12)],
        }
    )
    assert len(txid["rows"]) == 10
    assert txid["rows"][0] == ["t11", "11"]

    indexes = _prepare_unit(
        {
            "title": "罕用索引",
            "headers": ["index", "idx_scan"],
            "rows": [["used", "5"], ["zero", "0"]] + [
                [f"i{value}", str(value)] for value in range(1, 12)
            ],
        }
    )
    assert len(indexes["rows"]) == 10
    assert indexes["rows"][0] == ["zero", "0"]

    replication = _prepare_unit(
        {
            "title": "同步狀態",
            "headers": [
                "pid", "usesysid", "usename", "client_hostname", "state", "sync_state"
            ],
            "rows": [["1", "2", "repuser", "standby", "streaming", "async"]],
        }
    )
    assert replication["headers"] == [
        "pid", "usename", "client_hostname", "state", "sync_state"
    ]
    assert replication["rows"] == [
        ["1", "repuser", "standby", "streaming", "async"]
    ]


def test_v4_quality_blocks_pending_scope() -> None:
    report = build_v4_report(_model(), {"evidence": []}, ROOT)
    ledger = {
        "evidence": [
            {"path": "unknown.png", "decision": "pending"}
        ]
    }
    with pytest.raises(V4QualityError, match="pending_evidence"):
        validate_v4_report(report, ledger)


def test_approved_v4_renderer_hash_is_pinned() -> None:
    digest = hashlib.sha256(VENDOR_RENDERER.read_bytes()).hexdigest()
    assert digest == "34c5298c78cbd78b8dc68b1d9af7f0035cf4b99ef0f9ae167f12919203a701b7"
