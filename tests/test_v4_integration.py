import hashlib
from pathlib import Path

import pytest

from omni_healthcheck.reporting import ReportModel
from omni_healthcheck.v4_adapter import build_v4_report
from omni_healthcheck.v4_quality import V4QualityError, validate_v4_report
from omni_healthcheck.v4_renderer import VENDOR_RENDERER


ROOT = Path(__file__).parents[1]


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
    item = report["chapters"][1]["sections"][0]["items"][0]
    assert item["node"] == "db-primary"
    assert item["status"] == "注意"
    assert "跨節點比較" in item["observation"]
    assert item["controlled_continuation"] is True
    assert report["nodes"][0]["cpu"] == "8 cores"


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
    assert digest == "f4f3728c4c11d4b1fcaa563d800a5d91fa5878b1663275b085bda568e70c9895"
