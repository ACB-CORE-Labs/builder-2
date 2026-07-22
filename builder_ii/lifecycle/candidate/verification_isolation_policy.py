from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.lifecycle.candidate.verification_execution_plan import scan_planned_step

VERIFICATION_ISOLATION_POLICY_KIND = "builder_ii.verification_isolation_policy"
VERIFICATION_ISOLATION_POLICY_SCHEMA_VERSION = 1


def finalize_verification_isolation_policy(
    backend: str,
    image_ref: str | None = None,
    image_digest: str | None = None,
    mounts: list[dict[str, str]] | None = None,
    network_policy: str | None = None,
    resource_limits: dict[str, Any] | None = None,
    uid_gid: str | None = None,
) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "kind": VERIFICATION_ISOLATION_POLICY_KIND,
        "schema_version": VERIFICATION_ISOLATION_POLICY_SCHEMA_VERSION,
        "backend": backend,
    }
    if image_ref is not None:
        policy["image_ref"] = image_ref
    if image_digest is not None:
        policy["image_digest"] = image_digest
    if mounts is not None:
        policy["mounts"] = mounts
    if network_policy is not None:
        policy["network_policy"] = network_policy
    if resource_limits is not None:
        policy["resource_limits"] = resource_limits
    if uid_gid is not None:
        policy["uid_gid"] = uid_gid

    return attach_digest(policy, digest_key="verification_isolation_policy_digest")


def validate_verification_isolation_policy_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["artifact must be an object"]

    if data.get("kind") != VERIFICATION_ISOLATION_POLICY_KIND:
        errors.append(f"kind must be {VERIFICATION_ISOLATION_POLICY_KIND}")

    if data.get("schema_version") != VERIFICATION_ISOLATION_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_ISOLATION_POLICY_SCHEMA_VERSION}")

    backend = data.get("backend")
    if not isinstance(backend, str) or backend not in ("none", "docker"):
        errors.append("backend must be 'none' or 'docker'")

    errors.extend(scan_planned_step(data, ""))

    expected_digest = digest_jsonable(data, digest_key="verification_isolation_policy_digest")
    if data.get("verification_isolation_policy_digest") != expected_digest:
        errors.append("verification_isolation_policy_digest is invalid or missing")

    return errors


def validate_verification_isolation_policy_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
        data = json_lib.loads(content)
        return validate_verification_isolation_policy_artifact(data)
    except (OSError, json_lib.JSONDecodeError) as exc:
        return [f"failed to load verification isolation policy file: {exc}"]
