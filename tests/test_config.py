from pathlib import Path

import pytest

from omni_healthcheck.config import JobConfigError, load_job


ROOT = Path(__file__).parents[1]


def test_example_job_is_valid() -> None:
    job = load_job(ROOT / "config/job.example.yaml")
    assert job.customer == "環球晶圓"
    assert job.product == "EPAS"
    assert [node.hostname for node in job.nodes if node.role == "Primary"] == [
        "gwcymsedb"
    ]


def test_job_rejects_multiple_primaries(tmp_path: Path) -> None:
    job_path = tmp_path / "job.yaml"
    job_path.write_text(
        """
customer: Example
period: 2026-H1
product: PostgreSQL
first_healthcheck: true
nodes:
  - {hostname: db1, role: Primary}
  - {hostname: db2, role: Primary}
scope:
  include_os_from_all_nodes: true
  database_primary_only: true
report:
  template: omni-v4
  output_docx: true
  output_pdf: true
ai:
  enabled: false
  provider: disabled
""",
        encoding="utf-8",
    )
    with pytest.raises(JobConfigError, match="exactly one"):
        load_job(job_path)


def test_pem_service_is_only_allowed_on_witness(tmp_path: Path) -> None:
    source = (ROOT / "config/job.example.yaml").read_text(encoding="utf-8")
    job_path = tmp_path / "job.yaml"
    job_path.write_text(
        source.replace("role: Witness", "role: Standby"),
        encoding="utf-8",
    )

    with pytest.raises(JobConfigError, match="PEM service must run on a Witness"):
        load_job(job_path)
