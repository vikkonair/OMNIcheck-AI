from __future__ import annotations

from pathlib import Path

from omni_healthcheck.ai_gateway import (
    AIGatewaySettings,
    OllamaGateway,
    build_sanitized_prompt,
)
from omni_healthcheck.ai_persistence import AIGatewayAuditStore
from omni_healthcheck.database import DatabaseMetadataStore
from omni_healthcheck.section_persistence import SectionWorkflowStore
from omni_healthcheck.section_workflow import (
    Narrative,
    WorkflowMedia,
    build_section_workflow,
)
from test_section_workflow import assessment_document


def setup_stores(tmp_path: Path):
    metadata = DatabaseMetadataStore(f"sqlite:///{tmp_path / 'ai.db'}")
    metadata.create_schema_for_test()
    job_id = "b" * 32
    metadata.create({
        "job_id": job_id, "customer": "客戶", "system_name": "系統",
        "period": "2026-H2", "product": "EPAS", "status": "succeeded",
        "error": None, "input_files": 1,
    })
    sections = SectionWorkflowStore(engine=metadata.engine)
    document = build_section_workflow(assessment_document())
    original = document.items[0]
    sensitive = original.model_copy(update={
        "deterministic": Narrative(
            source="deterministic_template",
            observation=(
                "db-primary 192.168.1.50 password=secret 使用率正常。\n"
                "結論：目前無容量風險。"
            ),
            recommendation="請通知 dba@example.com 並持續監控。",
        ),
        "evidence_snapshot": {
            "type": "table",
            "headers": ["host", "value"],
            "rows": [["db-primary", "192.168.1.50 password=secret"]],
            "path": "/customer/private/output.txt",
        },
    })
    sections.persist_baseline(
        job_id, document.model_copy(update={"items": [sensitive]})
    )
    item = sections.list_items(job_id)[0]
    audit = AIGatewayAuditStore(engine=metadata.engine)
    return metadata, sections, audit, job_id, item


def settings() -> AIGatewaySettings:
    return AIGatewaySettings(
        enabled=True,
        endpoint="http://ollama.internal:11434/v1/chat/completions",
        model="gpt-oss:20b",
        timeout_seconds=10,
        max_attempts=1,
    )


def test_prompt_minimizes_and_redacts_infrastructure_data(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    captured = {}

    def transport(endpoint, payload, headers, timeout):
        captured.update({
            "endpoint": endpoint, "payload": payload,
            "headers": headers, "timeout": timeout,
        })
        return {
            "model": "gpt-oss:20b",
            "choices": [{
                "message": {"content": (
                    '{"observation":"證據顯示使用率正常。\\n結論：目前無容量風險。",'
                    '"recommendation":"維持定期容量監控。"}'
                ), "reasoning": "must never persist"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

    gateway = OllamaGateway(settings(), audit, transport=transport)
    item = sections.get_item(job_id, row["item_id"])
    prompt = build_sanitized_prompt(item)
    encoded = str(prompt)
    assert "db-primary" not in encoded
    assert "192.168.1.50" not in encoded
    assert "password=secret" not in encoded
    assert "dba@example.com" not in encoded
    assert "/customer/private/output.txt" not in encoded
    assert "visible_output" in encoded
    assert "[NODE]" in encoded
    assert "[IP]" in encoded
    assert "password=[REDACTED]" in encoded

    result = gateway.generate(
        job_id=job_id, item_id=row["item_id"], item=item,
        requested_by="engineer-a",
    )
    assert result.status == "succeeded"
    assert result.draft is not None
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    record = audit.list_for_job(job_id)[0]
    assert record["status"] == "succeeded"
    assert record["requested_by"] == "engineer-a"
    assert "reasoning" not in str(record["sanitized_response"])
    assert record["usage"]["completion_tokens"] == 20


def test_bloat_ai_draft_must_preserve_every_object_and_action(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    item = sections.get_item(job_id, row["item_id"]).model_copy(
        update={
            "check_id": "table_bloat",
            "deterministic": Narrative(
                source="deterministic_template",
                observation=(
                    "膨脹指數高於 2 的物件為：public.orders（8.5）、audit.events（3.1）。\n"
                    "結論：上述物件需安排維護處理。"
                ),
                recommendation=(
                    "建議處置：public.orders：VACUUM FULL；"
                    "audit.events：VACUUM FULL。"
                ),
            ),
        },
        deep=True,
    )

    def incomplete_transport(*_args):
        return {
            "choices": [{"message": {"content": (
                '{"observation":"僅列 public.orders。\\n結論：需處理。",'
                '"recommendation":"public.orders：VACUUM FULL。"}'
            )}}]
        }

    gateway = OllamaGateway(settings(), audit, transport=incomplete_transport)
    result = gateway.generate(
        job_id=job_id,
        item_id=row["item_id"],
        item=item,
        requested_by="engineer-a",
    )

    assert result.status == "fallback"
    assert result.draft is None


def test_backup_ai_draft_must_preserve_stanza_and_status(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    item = sections.get_item(job_id, row["item_id"]).model_copy(
        update={
            "check_id": "backup_status",
            "deterministic": Narrative(
                source="deterministic_template",
                observation=(
                    "主要備份 stanza `edb` 回報 `status: ok`。\n"
                    "結論：主要備份狀態正常。"
                ),
                recommendation="持續監控 stanza `edb` 並定期執行還原驗證。",
            ),
        },
        deep=True,
    )

    def incomplete_transport(*_args):
        return {
            "choices": [{"message": {"content": (
                '{"observation":"備份看起來正常。\\n結論：未見異常。",'
                '"recommendation":"持續監控。"}'
            )}}]
        }

    gateway = OllamaGateway(settings(), audit, transport=incomplete_transport)
    result = gateway.generate(
        job_id=job_id,
        item_id=row["item_id"],
        item=item,
        requested_by="engineer-a",
    )

    assert result.status == "fallback"
    assert result.draft is None


def test_largest_tables_ai_draft_must_preserve_evidence_objects(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    item = sections.get_item(job_id, row["item_id"]).model_copy(
        update={
            "check_id": "largest_tables",
            "deterministic": Narrative(
                source="deterministic_template",
                observation=(
                    "前三項為：public.orders（含索引 120 GB）、audit.events（含索引 60 GB）。\n"
                    "結論：本項為容量熱點清冊。"
                ),
                recommendation="追蹤容量成長速度。",
            ),
        },
        deep=True,
    )

    def incomplete_transport(*_args):
        return {
            "choices": [{"message": {"content": (
                '{"observation":"大型資料表需關注。\\n結論：應持續追蹤。",'
                '"recommendation":"建立容量基準。"}'
            )}}]
        }

    gateway = OllamaGateway(settings(), audit, transport=incomplete_transport)
    result = gateway.generate(
        job_id=job_id,
        item_id=row["item_id"],
        item=item,
        requested_by="engineer-a",
    )

    assert result.status == "fallback"
    assert result.draft is None


def test_invalid_ai_response_falls_back_without_section_mutation(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)

    def invalid_transport(*_args):
        return {"choices": [{"message": {"content": "not-json"}}]}

    gateway = OllamaGateway(settings(), audit, transport=invalid_transport)
    before = sections.get_item(job_id, row["item_id"])
    result = gateway.generate(
        job_id=job_id, item_id=row["item_id"], item=before,
        requested_by="engineer-a",
    )
    after = sections.get_item(job_id, row["item_id"])
    assert result.status == "fallback"
    assert result.draft is None
    assert before == after
    assert audit.list_for_job(job_id)[0]["status"] == "failed"


def test_ai_observation_normalizes_observed_conclusion_label(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)

    def variant_transport(*_args):
        return {
            "choices": [{"message": {"content": (
                '{"observation":"證據顯示容量需追蹤。\\n- 觀測結論：目前未見異常。",'
                '"recommendation":"建立容量基準。"}'
            )}}]
        }

    gateway = OllamaGateway(settings(), audit, transport=variant_transport)
    item = sections.get_item(job_id, row["item_id"])
    result = gateway.generate(
        job_id=job_id,
        item_id=row["item_id"],
        item=item,
        requested_by="engineer-a",
    )

    assert result.status == "succeeded"
    assert result.draft is not None
    assert "\n結論：目前未見異常。" in result.draft.observation


def test_ai_observation_moves_inline_conclusion_to_new_line(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)

    def inline_transport(*_args):
        return {
            "choices": [{"message": {"content": (
                '{"observation":"證據顯示容量需追蹤。結論：目前未見異常。",'
                '"recommendation":"建立容量基準。"}'
            )}}]
        }

    gateway = OllamaGateway(settings(), audit, transport=inline_transport)
    item = sections.get_item(job_id, row["item_id"])
    result = gateway.generate(
        job_id=job_id,
        item_id=row["item_id"],
        item=item,
        requested_by="engineer-a",
    )

    assert result.status == "succeeded"
    assert result.draft is not None
    assert result.draft.observation == "證據顯示容量需追蹤。\n結論：目前未見異常。"


def test_disabled_gateway_does_not_require_a_valid_endpoint(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    gateway = OllamaGateway(
        AIGatewaySettings(enabled=False, endpoint="not-a-url"), audit
    )
    result = gateway.generate(
        job_id=job_id, item_id=row["item_id"],
        item=sections.get_item(job_id, row["item_id"]),
        requested_by="engineer-a",
    )
    assert result.status == "disabled"
    assert audit.list_for_job(job_id) == []


def test_image_uses_vision_model_but_audit_does_not_store_image(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    image = tmp_path / "monitor.png"
    image.write_bytes(b"image-bytes")
    item = sections.get_item(job_id, row["item_id"]).model_copy(update={
        "media": WorkflowMedia(type="image", path=str(image), media_type="image/png")
    })
    captured = {}

    def transport(_endpoint, payload, _headers, _timeout):
        captured.update(payload)
        return {"choices": [{"message": {"content": (
            '{"observation":"圖表顯示趨勢平穩。\\n結論：未見明顯異常。",'
            '"recommendation":"持續監控並保留歷史基準。"}'
        )}}]}

    configured = settings().__class__(
        **{**settings().__dict__, "vision_model": "qwen2.5vl:7b"}
    )
    result = OllamaGateway(configured, audit, transport=transport).generate(
        job_id=job_id, item_id=row["item_id"], item=item, requested_by="engineer-a"
    )
    assert result.status == "succeeded"
    assert captured["model"] == "qwen2.5vl:7b"
    content = captured["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    record = audit.list_for_job(job_id)[0]
    assert "base64" not in str(record["sanitized_prompt"])


def test_image_is_downscaled_before_vision_request(tmp_path: Path) -> None:
    from PIL import Image
    import base64

    _, sections, audit, job_id, row = setup_stores(tmp_path)
    image = tmp_path / "large-monitor.png"
    Image.new("RGB", (2400, 1600), "#4080c0").save(image)
    item = sections.get_item(job_id, row["item_id"]).model_copy(update={
        "media": WorkflowMedia(type="image", path=str(image), media_type="image/png")
    })
    captured = {}

    def transport(_endpoint, payload, _headers, timeout):
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": (
            '{"observation":"圖表顯示趨勢平穩。\\n結論：未見明顯異常。",'
            '"recommendation":"持續監控。"}'
        )}}]}

    configured = settings().__class__(**{
        **settings().__dict__, "vision_model": "gemma4:26b",
        "vision_timeout_seconds": 35, "vision_max_dimension": 800,
    })
    result = OllamaGateway(configured, audit, transport=transport).generate(
        job_id=job_id, item_id=row["item_id"], item=item, requested_by="engineer-a"
    )
    assert result.status == "succeeded"
    data_url = captured["payload"]["messages"][1]["content"][1]["image_url"]["url"]
    assert data_url.startswith("data:image/jpeg;base64,")
    encoded = data_url.split(",", 1)[1]
    optimized = tmp_path / "optimized.jpg"
    optimized.write_bytes(base64.b64decode(encoded))
    with Image.open(optimized) as decoded:
        assert max(decoded.size) <= 800
    assert captured["timeout"] == 35


def test_image_without_vision_model_retains_deterministic_fallback(tmp_path: Path) -> None:
    _, sections, audit, job_id, row = setup_stores(tmp_path)
    item = sections.get_item(job_id, row["item_id"]).model_copy(update={
        "media": WorkflowMedia(
            type="image", path=str(tmp_path / "missing.png"), media_type="image/png"
        )
    })
    result = OllamaGateway(settings(), audit).generate(
        job_id=job_id, item_id=row["item_id"], item=item, requested_by="engineer-a"
    )
    assert result.status == "fallback"
    assert result.request_id is None
    assert audit.list_for_job(job_id) == []
