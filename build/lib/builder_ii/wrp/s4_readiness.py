"""W.6 — S4 backend promotion readiness *drafts* (validation_only).

Produces per-backend readiness + decision JSON pairs and a gate-audit skeleton.
Does **not** flip S4 promotion, start engines, grant authority, or approve HUMAN
decisions. Each backend requires its own HUMAN eight-gate decision later
(exactly as S3 did).

Backends in scope (opt-in / research only — never M1 defaults):
  modernbert_embed, opa, langgraph, vllm_research
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest
from builder_ii.promotion_decision_records import create_promotion_decision_record
from builder_ii.promotion_readiness_records import (
    create_promotion_readiness_record,
    validate_promotion_readiness_record,
)
from builder_ii.wrp.backend_registry import list_backends

# Opt-in / research backends that may later receive S4 HUMAN decisions.
# Defaults (hash embed, pure MSDA) are intentionally excluded.
S4_DRAFT_BACKEND_IDS: tuple[str, ...] = (
    "modernbert_embed",
    "opa",
    "langgraph",
    "vllm_research",
)

S4_READINESS_DRAFT_PACKAGE_KIND = "builder_ii.wrp.s4_readiness_draft_package"
S4_GATE_AUDIT_KIND = "builder_ii.wrp.s4_promotion_gate_audit"

_EVIDENCE_DIR = Path("planning/evidence")


def _backend_inventory() -> dict[str, dict[str, Any]]:
    return {str(b["id"]): b for b in list_backends()}


def s4_draft_backend_ids() -> tuple[str, ...]:
    return S4_DRAFT_BACKEND_IDS


def validate_s4_backend_id(backend_id: str) -> str:
    bid = backend_id.strip()
    if bid not in S4_DRAFT_BACKEND_IDS:
        raise ValueError(
            f"unknown S4 draft backend {bid!r}; choose one of {list(S4_DRAFT_BACKEND_IDS)}"
        )
    return bid


def readiness_path_for(backend_id: str) -> Path:
    return _EVIDENCE_DIR / f"wrp_s4_{backend_id}_readiness.json"


def decision_path_for(backend_id: str) -> Path:
    return _EVIDENCE_DIR / f"wrp_s4_{backend_id}_decision.json"


def gate_audit_path() -> Path:
    return _EVIDENCE_DIR / "wrp_s4_promotion_gate_audit.json"


def _backend_meta(backend_id: str) -> dict[str, Any]:
    inv = _backend_inventory()
    row = inv.get(backend_id)
    if row is None:
        # Still draftable if registry drifts; mark missing inventory honestly.
        return {
            "id": backend_id,
            "family": "unknown",
            "module": "unknown",
            "tier": "unknown",
            "inventory_present": False,
            "cli_commands": [],
            "notes": "backend not currently in list_backends() inventory",
        }
    return {
        "id": row["id"],
        "family": row.get("family"),
        "module": row.get("module"),
        "tier": row.get("tier"),
        "inventory_present": True,
        "cli_commands": list(row.get("cli_commands") or []),
        "opt_in_env": row.get("opt_in_env"),
        "notes": row.get("notes"),
        "health_state": (row.get("health") or {}).get("state"),
    }


def build_s4_readiness_record(backend_id: str) -> dict[str, Any]:
    """Eight-gate readiness package for one backend (reviewable; not a promo grant)."""
    bid = validate_s4_backend_id(backend_id)
    meta = _backend_meta(bid)
    cli_cmds = meta.get("cli_commands") or ["builder-wrp doctor-backends"]
    record = create_promotion_readiness_record(
        capability_name=f"WRP S4 backend promotion: {bid}",
        target_state="promoted_opt_in",
        target="builder",
        docs_refs=(
            "docs/WRP_CONTROL_PLANE.md",
            "docs/WRP_MASTERY_GAP_MATRIX.md",
            "docs/WRP_MASTERY_PROGRESS.md",
            "docs/WRP_ACCEPTANCE.md",
            "docs/CAPABILITY_PROMOTION.md",
            "docs/adrs/ADR-0007-orchestration-router-control-plane.md",
            "docs/plan/WRP_VLLM_RESEARCH_PROFILE.md" if bid == "vllm_research" else "docs/WRP_CONTROL_PLANE.md",
        ),
        tests_refs=(
            "tests/test_wrp_backend_registry.py",
            "tests/test_wrp_s4_readiness_drafts.py",
            f"backend inventory id={bid}",
        ),
        cli_refs=(
            "builder-wrp backends",
            "builder-wrp doctor-backends",
            "builder-wrp s4-readiness draft",
            *cli_cmds,
        ),
        failure_mode_refs=(
            "s4_promoted must remain false until HUMAN decision approved",
            "doctor_backends never starts engines",
            "opt-in backends fail closed when env/provider missing",
            f"backend={bid} remains non-default M1-safe",
        ),
        approval_boundary_refs=(
            "docs/CAPABILITY_PROMOTION.md eight-gate HUMAN decision",
            "docs/WRP_ACCEPTANCE.md Promotion acceptance",
            "HUMAN decides each backend independently (no bulk S4 flip)",
            "PENDING_HUMAN — this draft is not an approval",
        ),
        output_artifact_refs=(
            f"builder_ii.promotion_readiness_record {readiness_path_for(bid)}",
            f"builder_ii.promotion_decision_record {decision_path_for(bid)}",
            f"builder_ii.wrp.s4_promotion_gate_audit {gate_audit_path()}",
        ),
        rollback_refs=(
            "keep s4_promoted=false on doctor/inventory reports",
            f"delete or supersede {readiness_path_for(bid)} + {decision_path_for(bid)}",
            "do not merge enablement code without HUMAN approved decision",
        ),
        verification_refs=(
            "uv run pytest tests/test_wrp_s4_readiness_drafts.py tests/test_wrp_backend_registry.py -q",
            "uv run builder-wrp doctor-backends",
            f"uv run builder-wrp s4-readiness draft --backend {bid}",
            "uv run builder-promotion validate <readiness path>",
            "uv run builder-platform audit-docs",
        ),
        notes=(
            f"W.6 S4 readiness DRAFT for backend={bid} (family={meta.get('family')}, "
            f"tier={meta.get('tier')}). ready=true means eight-gate *evidence refs* are present "
            "for HUMAN review — not that S4 should be approved. Does NOT promote the backend, "
            "start engines, flip defaults, enable S3 multi-agent, or invoke cloud. "
            f"Inventory present={meta.get('inventory_present')}; health_state={meta.get('health_state')}. "
            f"Module={meta.get('module')}. HUMAN must issue a separate per-backend decision."
        ),
    )
    # Extra honesty fields (not part of promotion schema core; validators ignore unknown).
    record["s4_backend_id"] = bid
    record["s4_promoted"] = False
    record["s3_enabled"] = False
    record["draft_only"] = True
    record["backend_meta"] = meta
    return record


def build_s4_decision_record(backend_id: str, readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decision template: always blocked / PENDING_HUMAN until a real HUMAN decision."""
    bid = validate_s4_backend_id(backend_id)
    readiness = readiness or build_s4_readiness_record(bid)
    path = readiness_path_for(bid)
    record = create_promotion_decision_record(
        readiness,
        readiness_path=path,
        decision="blocked",
        decided_by="PENDING_HUMAN",
        reason=(
            f"W.6 DRAFT only for backend={bid}. No HUMAN eight-gate ceremony completed. "
            "Decision remains blocked. Do not treat ready readiness as approval. "
            "S4 promo flip OPEN; engine start forbidden; cloud invoke OPEN; S3 still blocked."
        ),
    )
    record["s4_backend_id"] = bid
    record["s4_promoted"] = False
    record["s3_enabled"] = False
    record["draft_only"] = True
    record["human_decision_required"] = True
    return record


def build_s4_gate_audit(*, backends: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Wave-level gate audit *skeleton* — status DRAFT, not PASS, not promo."""
    ids = backends or S4_DRAFT_BACKEND_IDS
    for bid in ids:
        validate_s4_backend_id(bid)
    return {
        "kind": S4_GATE_AUDIT_KIND,
        "schema_version": 1,
        "wave": "S4 readiness drafts (planning/evidence only)",
        "status": "DRAFT",
        "role": "MAKER_DRAFT",
        "s4_promoted": False,
        "s3_enabled": False,
        "grants_authority": False,
        "human_decision_required": True,
        "honesty_locks": {
            "readiness.ready": "per-backend evidence refs present for review",
            "decision.approved": False,
            "decision.decided_by": "PENDING_HUMAN",
            "enablement": "none",
            "engine_start": "none",
            "cloud_invoke": "none",
            "s4_promo_flip": "OPEN",
        },
        "backends": list(ids),
        "artifacts": {
            bid: {
                "readiness": str(readiness_path_for(bid)),
                "decision": str(decision_path_for(bid)),
            }
            for bid in ids
        },
        "gate_audit_path": str(gate_audit_path()),
        "eight_gates": {
            "1_docs": "DRAFT: docs list S4 OPEN; no inflated promoted claims",
            "2_tests": "DRAFT: registry + s4 draft tests required before HUMAN review",
            "3_surface": "DRAFT: builder-wrp s4-readiness draft (validation_only)",
            "4_failure": "DRAFT: decision defaults blocked; s4_promoted=false",
            "5_human": "DRAFT: HUMAN eight-gate per backend — not bulk approve",
            "6_digest": "DRAFT: readiness/decision JSON pairs under planning/evidence",
            "7_rollback": "DRAFT: delete planning/evidence wrp_s4_* files",
            "8_verification": "DRAFT: builder-promotion validate + doctor-backends + audit-docs",
        },
        "notes": (
            "W.6 skeleton only. Not G-LEAD PASS. Not HUMAN approval. "
            "Each backend needs its own later decision ceremony."
        ),
    }


def draft_s4_package(backend_id: str) -> dict[str, Any]:
    """Full draft package for one backend (readiness + decision + honesty pins)."""
    bid = validate_s4_backend_id(backend_id)
    readiness = build_s4_readiness_record(bid)
    decision = build_s4_decision_record(bid, readiness)
    readiness_errors = validate_promotion_readiness_record(readiness)
    ok = (
        readiness.get("ready") is True
        and decision.get("approved") is False
        and decision.get("decision") == "blocked"
        and decision.get("s4_promoted") is False
        and readiness.get("s4_promoted") is False
        and not readiness_errors
    )
    return attach_digest(
        {
            "kind": S4_READINESS_DRAFT_PACKAGE_KIND,
            "schema_version": 1,
            "artifact_state": "VALIDATION_ONLY",
            "backend_id": bid,
            "ok": ok,
            "readiness": readiness,
            "decision": decision,
            "paths": {
                "readiness": str(readiness_path_for(bid)),
                "decision": str(decision_path_for(bid)),
                "gate_audit": str(gate_audit_path()),
            },
            "s4_promoted": False,
            "s3_enabled": False,
            "grants_authority": False,
            "engine_started": False,
            "cloud_invoke": False,
            "human_decision_required": True,
            "notes": (
                "W.6 S4 readiness draft package. Validation_only substrate for HUMAN review. "
                "Does not promote backends or start engines."
            ),
        }
    )


def draft_all_s4_packages() -> dict[str, Any]:
    packages = [draft_s4_package(bid) for bid in S4_DRAFT_BACKEND_IDS]
    audit = build_s4_gate_audit()
    all_ok = all(p.get("ok") for p in packages)
    return attach_digest(
        {
            "kind": S4_READINESS_DRAFT_PACKAGE_KIND,
            "schema_version": 1,
            "artifact_state": "VALIDATION_ONLY",
            "scope": "all_s4_draft_backends",
            "ok": all_ok,
            "backend_ids": list(S4_DRAFT_BACKEND_IDS),
            "packages": packages,
            "gate_audit": audit,
            "s4_promoted": False,
            "s3_enabled": False,
            "grants_authority": False,
            "engine_started": False,
            "cloud_invoke": False,
            "human_decision_required": True,
            "notes": (
                "W.6 aggregate S4 readiness drafts for all opt-in/research backends. "
                "HUMAN decides each backend separately. No promo flip."
            ),
        }
    )


def write_s4_evidence(
    *,
    backend_id: str | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, Path]:
    """Write readiness/decision files (+ gate audit) under planning/evidence (or override)."""
    root = evidence_dir or _EVIDENCE_DIR
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    ids = (validate_s4_backend_id(backend_id),) if backend_id else S4_DRAFT_BACKEND_IDS
    for bid in ids:
        readiness = build_s4_readiness_record(bid)
        decision = build_s4_decision_record(bid, readiness)
        r_path = root / f"wrp_s4_{bid}_readiness.json"
        d_path = root / f"wrp_s4_{bid}_decision.json"
        import json as json_lib

        r_path.write_text(json_lib.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        d_path.write_text(json_lib.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[f"{bid}_readiness"] = r_path
        written[f"{bid}_decision"] = d_path
    audit = build_s4_gate_audit(backends=ids if backend_id else None)
    # When writing a single backend, still refresh gate audit for all known draft backends
    # so the committed skeleton stays complete.
    if backend_id is None or evidence_dir is None:
        audit = build_s4_gate_audit()
    a_path = root / "wrp_s4_promotion_gate_audit.json"
    import json as json_lib

    a_path.write_text(json_lib.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written["gate_audit"] = a_path
    return written


def validate_s4_draft_package(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["s4 draft package must be a JSON object"]
    if record.get("kind") != S4_READINESS_DRAFT_PACKAGE_KIND:
        errors.append(f"kind must be {S4_READINESS_DRAFT_PACKAGE_KIND}")
    if record.get("s4_promoted") is not False:
        errors.append("s4_promoted must be false")
    if record.get("s3_enabled") is not False:
        errors.append("s3_enabled must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("engine_started") is not False:
        errors.append("engine_started must be false")
    if record.get("cloud_invoke") is not False:
        errors.append("cloud_invoke must be false")
    if record.get("human_decision_required") is not True:
        errors.append("human_decision_required must be true")
    digest = record.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a 64-char hex sha256")
    else:
        from builder_ii.config_schema import digest_jsonable

        if digest != digest_jsonable(record):
            errors.append("digest mismatch")
    return errors


__all__ = [
    "S4_DRAFT_BACKEND_IDS",
    "S4_GATE_AUDIT_KIND",
    "S4_READINESS_DRAFT_PACKAGE_KIND",
    "build_s4_decision_record",
    "build_s4_gate_audit",
    "build_s4_readiness_record",
    "decision_path_for",
    "draft_all_s4_packages",
    "draft_s4_package",
    "gate_audit_path",
    "readiness_path_for",
    "s4_draft_backend_ids",
    "validate_s4_backend_id",
    "validate_s4_draft_package",
    "write_s4_evidence",
]
