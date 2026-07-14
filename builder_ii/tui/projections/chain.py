"""Artifact chain projection for the STRATUM spine and inspect panel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

StageStatus = Literal["verified", "gate", "pending", "failed", "disabled"]

PIPELINE_STAGES: list[dict[str, str]] = [
    {"id": "repo-map", "label": "repo-map", "kind": "builder_ii.repo_map"},
    {"id": "ctx-pack", "label": "ctx-pack", "kind": "builder_ii.context_pack"},
    {"id": "session", "label": "session", "kind": "builder_ii.session_configuration"},
    {"id": "projection", "label": "projection", "kind": "builder_ii.goose_projection"},
    {"id": "wrap-plan", "label": "wrap-plan", "kind": "builder_ii.goose_wrapper_plan"},
    {"id": "ver-plan", "label": "ver-plan", "kind": "builder_ii.verification_execution_plan"},
    {"id": "exec-req", "label": "exec-req", "kind": "builder_ii.execution_candidate_manifest"},
    {"id": "postflight", "label": "postflight", "kind": "builder_ii.execution_postflight_record"},
    {"id": "promote", "label": "promote", "kind": "builder_ii.promotion_readiness_record"},
]


@dataclass(frozen=True)
class StageView:
    stage_id: str
    label: str
    kind: str
    status: StageStatus
    path: str | None = None
    artifact: dict[str, Any] | None = None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChainView:
    stages: tuple[StageView, ...]
    chain_valid: bool | None  # None = not evaluated / no files
    file_count: int
    found_kinds: tuple[str, ...] = ()


def _load_artifacts(artifacts_dir: Path | None) -> dict[str, tuple[Path, dict[str, Any]]]:
    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    if artifacts_dir is None or not artifacts_dir.exists():
        return found
    for path in sorted(artifacts_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        kind = str(data.get("kind", ""))
        if kind:
            found[kind] = (path, data)
    return found


def _stage_status(artifact: dict[str, Any] | None, *, upstream_ok: bool) -> StageStatus:
    if artifact is None:
        return "pending"
    errors = artifact.get("errors") or []
    if errors:
        return "failed"
    governance = artifact.get("governance") or {}
    if isinstance(governance, dict) and governance.get("hitl_required"):
        return "gate"
    # Presence without local errors — not cryptographic chain proof.
    # upstream_ok reserved for future blocked-downstream display.
    _ = upstream_ok
    return "verified"


def project_chain(artifacts_dir: Path | None) -> ChainView:
    """Project pipeline stages from on-disk artifacts + optional chain report."""
    found = _load_artifacts(artifacts_dir)
    stages: list[StageView] = []
    upstream_ok = True

    for stage in PIPELINE_STAGES:
        kind = stage["kind"]
        hit = found.get(kind)
        artifact = hit[1] if hit else None
        path = str(hit[0]) if hit else None
        status = _stage_status(artifact, upstream_ok=upstream_ok)
        errors: tuple[str, ...] = ()
        if artifact is not None:
            raw_errors = artifact.get("errors") or []
            if isinstance(raw_errors, list):
                errors = tuple(str(e) for e in raw_errors)
            if status in ("failed", "pending") and artifact is None:
                upstream_ok = False
            elif status == "failed":
                upstream_ok = False
            elif status == "pending":
                upstream_ok = False
        else:
            upstream_ok = False

        stages.append(
            StageView(
                stage_id=stage["id"],
                label=stage["label"],
                kind=kind,
                status=status,
                path=path,
                artifact=artifact,
                errors=errors,
            )
        )

    chain_valid: bool | None = None
    file_count = 0
    if artifacts_dir is not None and artifacts_dir.exists():
        paths = [p for p in artifacts_dir.glob("*.json") if p.is_file()]
        file_count = len(paths)
        if paths:
            try:
                from builder_ii.artifact_chain_verification import verify_artifact_chain

                report = verify_artifact_chain(paths)
                chain_valid = bool(report.get("valid", False))
                file_count = int((report.get("counts") or {}).get("files", file_count))
            except Exception:
                chain_valid = None

    return ChainView(
        stages=tuple(stages),
        chain_valid=chain_valid,
        file_count=file_count,
        found_kinds=tuple(sorted(found.keys())),
    )


def find_artifact_for_kind(artifacts_dir: Path | None, kind: str) -> dict[str, Any] | None:
    found = _load_artifacts(artifacts_dir)
    hit = found.get(kind)
    return hit[1] if hit else None


def find_artifact_path_for_kind(artifacts_dir: Path | None, kind: str) -> Path | None:
    found = _load_artifacts(artifacts_dir)
    hit = found.get(kind)
    return hit[0] if hit else None


def epistemic_from_chain(chain: ChainView) -> dict[str, str]:
    """Map chain presence to conservative epistemic states.

    Digests are always absent markers here — STRATUM does not invent them.
    Prefer pending over completed when evidence is only partial.
    """
    kinds = set(chain.found_kinds)
    planned = any(k for k in kinds if "plan" in k or "repo_map" in k or "context_pack" in k or "session" in k)
    executed = any(k for k in kinds if "receipt" in k or "postflight" in k or "execution" in k)
    verified = chain.chain_valid is True
    promoted = any("promotion" in k and "decision" in k for k in kinds) or any(
        "promotion_decision" in k for k in kinds
    )

    def state(done: bool, active_when: bool) -> str:
        if done:
            return "completed"
        if active_when:
            return "active"
        return "pending"

    # Verified only lights completed when chain report is explicitly valid.
    # Promoted never greens without a promotion decision kind on disk.
    return {
        "state_planned": state(planned, not planned and chain.file_count == 0),
        "state_executed": state(executed, planned and not executed),
        "state_verified": state(verified, executed and not verified),
        "state_promoted": state(promoted, verified and not promoted),
        "digest_planned": "—",
        "digest_executed": "—",
        "digest_verified": "—",
        "digest_promoted": "—",
    }
