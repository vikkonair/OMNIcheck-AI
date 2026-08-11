from pathlib import Path


ROOT = Path(__file__).parents[1]
SYSTEMD = ROOT / "deploy" / "systemd"


def test_web_and_worker_use_release_local_virtual_environment() -> None:
    for name in ("omnicheck-web.service", "omnicheck-worker.service"):
        content = (SYSTEMD / name).read_text(encoding="utf-8")
        assert "WorkingDirectory=/data/omnicheck/app/current" in content
        assert "ExecStart=/data/omnicheck/app/current/.venv/bin/" in content
        assert "ExecStart=/data/omnicheck/venv/bin/" not in content


def test_services_keep_runtime_hardening_and_environment_contract() -> None:
    for name in ("omnicheck-web.service", "omnicheck-worker.service"):
        content = (SYSTEMD / name).read_text(encoding="utf-8")
        assert "EnvironmentFile=/etc/omnicheck-ai/omnicheck.env" in content
        assert "User=omnicheck" in content
        assert "Group=omnicheck" in content
        assert "NoNewPrivileges=true" in content
        assert "ProtectSystem=strict" in content
        assert "ReadWritePaths=/data/omnicheck" in content
