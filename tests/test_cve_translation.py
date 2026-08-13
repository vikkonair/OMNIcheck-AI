from types import SimpleNamespace

from omni_healthcheck.cve_translation import translate_cve_report


class _Audit:
    def __init__(self) -> None:
        self.finished = []

    def start(self, **_kwargs) -> str:
        return "request-1"

    def finish(self, request_id: str, **kwargs) -> None:
        self.finished.append((request_id, kwargs))


def test_cve_translation_only_adds_chinese_presentation_text() -> None:
    audit = _Audit()
    gateway = SimpleNamespace(
        settings=SimpleNamespace(
            enabled=True, endpoint="http://ollama.invalid", model="test",
            timeout_seconds=10,
        ),
        audit_store=audit,
        transport=lambda *_args: {"choices": [{"message": {"content": (
            '{"translations":[{"id":"CVE-2026-1",'
            '"summary_zh":"修正資料庫伺服器的安全性問題"}]}'
        )}}]},
    )
    report = {"version_updates": [{"cves": [{
        "id": "CVE-2026-1", "summary": "Fix a security issue in database server.",
        "cvss_score": "7.5", "fixed_version": "16.5",
    }]}]}

    translated = translate_cve_report(
        report, job_id="a" * 32, item_id="b" * 32, gateway=gateway
    )
    cve = translated["version_updates"][0]["cves"][0]
    assert cve["summary"] == "Fix a security issue in database server."
    assert cve["summary_zh"] == "修正資料庫伺服器的安全性問題"
    assert cve["cvss_score"] == "7.5"
    assert audit.finished[0][1]["status"] == "succeeded"
