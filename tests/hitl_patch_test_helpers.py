import json
from pathlib import Path


def write_core_demo_verification_receipt(path: Path, repo: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.core_demo_verification_receipt",
                "schema_version": 1,
                "label": "before_apply",
                "receipt_status": "EXECUTED",
                "target": {"name": "core", "repo": str(repo.resolve())},
                "checks": [{"status": "PASS", "name": "preflight"}],
                "governance": {
                    "model_execution": "DISABLED",
                    "source_writes": "DISABLED",
                    "artifact_is_authority": False,
                    "core_workbench_coupling": "NONE",
                },
            }
        ),
        encoding="utf-8",
    )