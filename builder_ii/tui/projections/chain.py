"""Artifact chain projection for the STRATUM spine and inspect panel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Presence on disk is not cryptographic chain proof. Prefer "present" over "verified".
StageStatus = Literal["present", "gate", "pending", "failed", "disabled"]

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

# Sibling dirs under ``.builder/`` that prepare / session / hitl may write into.
# First-session prepare historically lands under ``.builder/session`` while the spine
# only watched top-level ``.builder/artifacts/*.json`` — a structural empty-spine bug.
_SIBLING_SCAN_NAMES = ("artifacts", "session", "hitl", "receipts")


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


def artifact_search_roots(artifacts_dir: Path | None) -> list[Path]:
    """Roots whose top-level ``*.json`` participate in chain projection.

    Includes the configured artifacts dir and sibling dirs under ``.builder/``
    (notably ``session``, where prepare-package writes).
    """
    if artifacts_dir is None:
        return []
    roots: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            return
        seen.add(resolved)
        if path.is_dir():
            roots.append(path)

    _add(artifacts_dir)
    parent = artifacts_dir.parent
    if parent.name == ".builder" or (parent / "artifacts").exists() or (parent / "session").exists():
        for name in _SIBLING_SCAN_NAMES:
            _add(parent / name)
    # Also accept being pointed at ``.builder`` itself.
    if artifacts_dir.name == ".builder":
        for name in _SIBLING_SCAN_NAMES:
            _add(artifacts_dir / name)
    return roots


def _load_artifacts(artifacts_dir: Path | None) -> dict[str, tuple[Path, dict[str, Any]]]:
    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in artifact_search_roots(artifacts_dir):
        for path in sorted(root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            kind = str(data.get("kind", ""))
            if kind:
                # Prefer newer mtime when the same kind appears in multiple roots.
                prev = found.get(kind)
                if prev is not None:
                    try:
                        if path.stat().st_mtime < prev[0].stat().st_mtime:
                            continue
                    except OSError:
                        pass
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
    # An execution_postflight_record can be validly on disk with postflight_state
    # NOT_RUN -- the run it describes has not happened yet. Presence alone must not
    # green EXECUTE/VERIFY for it; that is exactly the planned != executed conflation
    # this projection exists to prevent.
    postflight_state = artifact.get("postflight_state")
    if postflight_state is not None and postflight_state != "RUN_COMPLETE":
        return "pending"
    # Presence without local errors — not cryptographic chain proof.
    # upstream_ok reserved for future blocked-downstream display.
    _ = upstream_ok
    return "present"


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
    all_paths: list[Path] = []
    for root in artifact_search_roots(artifacts_dir):
        all_paths.extend(p for p in root.glob("*.json") if p.is_file())
    file_count = len(all_paths)
    if all_paths:
        try:
            from builder_ii.core.artifact_chain_verification import verify_artifact_chain

            report = verify_artifact_chain(all_paths)
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
    # "execution" in a kind name must mean an execution *happened*, not merely that a planned artifact
    # carries the word. verification_execution_plan / _approval and execution_candidate_manifest (the
    # exec-req stage) all contain "execution" yet are planned-only -- greening executed from them is
    # exactly the planned != executed conflation the epistemic matrix exists to prevent. Require real
    # post-execution evidence: a receipt, a postflight record, or an execution record that is not a
    # plan/candidate/approval.
    executed = any(
        "receipt" in k
        or "postflight" in k
        or ("execution" in k and not any(w in k for w in ("plan", "candidate", "approval")))
        for k in kinds
    )
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
