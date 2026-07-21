from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_readonly_session import GOOSE_READONLY_SESSION_PLAN_KIND
from builder_ii.core.context_pack import CONTEXT_PACK_RECORD_KIND
from builder_ii.core.git_state import GIT_STATE_RECORD_KIND
from builder_ii.core.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND
from builder_ii.lifecycle.candidate.verification_profiles import VERIFICATION_ARTIFACT_KIND
from builder_ii.lifecycle.setup.target_profiles import TARGET_PROFILE_ARTIFACT_KIND
from builder_ii.routing.agent_profiles import AGENT_PROFILE_RECORD_KIND

PROMOTION_SUPPORT_ARTIFACT_REQUIRED_KINDS: tuple[str, ...] = (
    TARGET_PROFILE_ARTIFACT_KIND,
    VERIFICATION_ARTIFACT_KIND,
    CONTEXT_PACK_RECORD_KIND,
    AGENT_PROFILE_RECORD_KIND,
    GIT_STATE_RECORD_KIND,
)

PROMOTION_SUPPORT_ARTIFACT_ALLOWED_KINDS: tuple[str, ...] = PROMOTION_SUPPORT_ARTIFACT_REQUIRED_KINDS + (
    READONLY_INSPECTION_REPORT_KIND,
    GOOSE_READONLY_SESSION_PLAN_KIND,
)

_TARGETS = {"generic", "builder", "core"}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _extract_target(record: dict[str, Any]) -> str:
    if record.get("kind") == TARGET_PROFILE_ARTIFACT_KIND:
        return _clean(record.get("name"))
    return _clean(record.get("target"))


def create_support_artifact_ref(record: dict[str, Any], *, path: str | Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "kind": _clean(record.get("kind")),
        "sha256": _digest(record),
        "target": _extract_target(record),
        "name": _clean(record.get("name")),
    }


def parse_support_artifact_ref(spec: str) -> dict[str, Any]:
    parts = [part.strip() for part in spec.split(",")]
    if len(parts) not in (4, 5):
        return {"_parse_error": "support artifact must use kind,path,sha256,target[,name]"}
    kind, path, sha256, target, *rest = parts
    return {"kind": kind, "path": path, "sha256": sha256, "target": target, "name": rest[0] if rest else ""}


def _validate_ref(ref: Any, index: int, *, expected_target: str) -> list[str]:
    prefix = f"support_artifacts[{index}]"
    errors: list[str] = []
    if not isinstance(ref, dict):
        return [f"{prefix} must be an object"]
    if ref.get("_parse_error"):
        return [f"{prefix}: {ref['_parse_error']}"]
    if ref.get("kind") not in PROMOTION_SUPPORT_ARTIFACT_ALLOWED_KINDS:
        errors.append(f"{prefix}.kind must be a known promotion support artifact kind")
    for field in ("path", "sha256"):
        if not isinstance(ref.get(field), str) or not ref[field]:
            errors.append(f"{prefix}.{field} must be a non-empty string")
    target = ref.get("target")
    if target not in _TARGETS:
        errors.append(f"{prefix}.target must be one of: generic, builder, core")
    elif expected_target and target != expected_target:
        errors.append(f"{prefix}.target must match readiness target {expected_target}")
    if "name" in ref and not isinstance(ref.get("name"), str):
        errors.append(f"{prefix}.name must be a string when present")
    return errors


def validate_support_artifacts(value: Any, *, expected_target: str = "") -> list[str]:
    if not isinstance(value, list):
        return ["support_artifacts must be a list"]
    if not value:
        return []
    errors: list[str] = []
    if expected_target not in _TARGETS:
        errors.append("target is required when support_artifacts are present")
    seen: set[str] = set()
    for index, ref in enumerate(value):
        if isinstance(ref, dict) and isinstance(ref.get("kind"), str):
            kind = ref["kind"]
            if kind in seen:
                errors.append(f"duplicate support artifact kind: {kind}")
            seen.add(kind)
        errors.extend(_validate_ref(ref, index, expected_target=expected_target if expected_target in _TARGETS else ""))
    for kind in PROMOTION_SUPPORT_ARTIFACT_REQUIRED_KINDS:
        if kind not in seen:
            errors.append(f"missing support artifact kind: {kind}")
    return errors


def support_artifact_kinds(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [ref["kind"] for ref in value if isinstance(ref, dict) and isinstance(ref.get("kind"), str) and ref["kind"]]
