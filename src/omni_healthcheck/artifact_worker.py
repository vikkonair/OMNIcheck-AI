"""One-shot M9.6 retention scanner and copy-verify archive worker."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from omni_healthcheck.artifact_lifecycle import ArtifactRegistry


def main() -> None:
    parser = argparse.ArgumentParser(prog="omni-healthcheck-artifacts")
    parser.add_argument(
        "--apply", action="store_true",
        help="copy due artifacts and update registry; default is dry-run",
    )
    args = parser.parse_args()
    database_url = os.environ.get("OMNICHECK_DATABASE_URL")
    if not database_url:
        raise SystemExit("OMNICHECK_DATABASE_URL is required")
    active_root = Path(os.environ.get("OMNICHECK_STORAGE_ROOT", "/data/omnicheck"))
    archive_root = Path(
        os.environ.get("OMNICHECK_ARCHIVE_ROOT", "/data/omnicheck/archive")
    )
    results = ArtifactRegistry(database_url).archive_due(
        active_root=active_root,
        archive_root=archive_root,
        apply=args.apply,
    )
    print(json.dumps({"apply": args.apply, "count": len(results), "items": results}, indent=2))


if __name__ == "__main__":
    main()
