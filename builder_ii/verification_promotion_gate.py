"""B2.0 machine-checkable promotion-gate evaluator (post-beta ladder item 2).

Consumes a verification plan/approval/receipt chain (and optional ledger record) and emits a
digest-bound promotion-evidence artifact: pass/fail per gate, no authority granted.

This is not a promotion flip. A PASS evidence artifact is input to an operator-applied matrix
update — it never flips capability state itself.
"""

from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable
from builder_ii.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.verification_execution_approval import (
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_ledger import (
    VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
    validate_verification_execution_ledger_record,
)
from builder_ii.verification_execution_plan import (
    VERIFICATION_EXECUTION_PLAN_KIND,
    validate_verification_execution_plan_artifact,
)
from builder_ii.verification_execution_receipt import (
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
)

PROMOTION_EVIDENCE_KIND = "builder_ii.verification_promotion_evidence"
PROMOTION_EVIDENCE_SCHEMA_VERSION = 1
PROMOTION_EVIDENCE_STATE = "RECORDED_ONLY"

# Machine-checkable gates over a verification execution chain. These are the B2.0 checklist —
# evidence that a bounded run is promotion-*eligible*, not that a capability is promoted.
_GATE_NAMES = (
    "plan_valid",
    "approval_valid",
    "approval_bound_to_plan",
    "receipt_valid",
    "receipt_bound_to_plan_and_approval",
    "receipt_executed",
    "workspace_unmutated",
    "commit_identity_recorded",
    "approval_unexpired",
    "ledger_chain_consistent",
)


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _gate(name: str, passed: bool, evidence: str, detail: str = "") -> dict[str, Any]:
    return {
        "gate": name,
        "state": "PASS" if passed else "FAIL",
        "evidence": evidence,
        "detail": detail,
    }


def _parse_expires_at(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_verification_promotion_gates(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    receipt: dict[str, Any],
    plan_path: str | Path,
    approval_path: str | Path,
    receipt_path: str | Path,
    ledger_record: dict[str, Any] | None = None,
    ledger_path: str | Path | None = None,
    capability_name: str = "",
    expected_profile: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate machine-checkable promotion gates over a verification chain.

    Returns a digest-bound evidence artifact. Never grants runtime or action authority.
    """
    gates: list[dict[str, Any]] = []

    plan_errors = validate_verification_execution_plan_artifact(plan)
    gates.append(
        _gate(
            "plan_valid",
            not plan_errors and plan.get("kind") == VERIFICATION_EXECUTION_PLAN_KIND,
            f"plan_digest={plan.get('verification_execution_plan_digest', '')}",
            "; ".join(plan_errors) if plan_errors else "plan artifact validates",
        )
    )

    approval_errors = validate_verification_execution_approval_artifact(approval)
    gates.append(
        _gate(
            "approval_valid",
            not approval_errors and approval.get("kind") == VERIFICATION_EXECUTION_APPROVAL_KIND,
            f"approval_digest={approval.get('verification_execution_approval_digest', '')}",
            "; ".join(approval_errors) if approval_errors else "approval artifact validates",
        )
    )

    binding_errors = validate_verification_execution_approval_against_plan(approval, plan)
    gates.append(
        _gate(
            "approval_bound_to_plan",
            not binding_errors,
            f"plan_digest={approval.get('plan_digest', '')}",
            "; ".join(binding_errors) if binding_errors else "approval digests bind to plan",
        )
    )

    receipt_errors = validate_verification_execution_receipt_artifact(receipt)
    gates.append(
        _gate(
            "receipt_valid",
            not receipt_errors and receipt.get("kind") == VERIFICATION_EXECUTION_RECEIPT_KIND,
            f"receipt_digest={receipt.get('verification_execution_receipt_digest', '')}",
            "; ".join(receipt_errors) if receipt_errors else "receipt artifact validates",
        )
    )

    chain_errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)
    gates.append(
        _gate(
            "receipt_bound_to_plan_and_approval",
            not chain_errors,
            (
                f"plan_digest={receipt.get('plan_digest', '')};"
                f"approval_digest={receipt.get('approval_digest', '')}"
            ),
            "; ".join(chain_errors) if chain_errors else "receipt digests bind to plan and approval",
        )
    )

    receipt_status = receipt.get("receipt_status")
    receipt_executed = receipt_status == "EXECUTED" and receipt.get("valid") is True
    gates.append(
        _gate(
            "receipt_executed",
            receipt_executed,
            f"receipt_status={receipt_status};valid={receipt.get('valid')}",
            "receipt must be EXECUTED with valid=true" if not receipt_executed else "receipt executed cleanly",
        )
    )

    mutation = receipt.get("workspace_mutation_detected")
    gates.append(
        _gate(
            "workspace_unmutated",
            mutation is False,
            f"workspace_mutation_detected={mutation}",
            "workspace must be unmutated" if mutation is not False else "no workspace mutation detected",
        )
    )

    commit = receipt.get("target_commit")
    commit_ok = isinstance(commit, str) and bool(commit.strip())
    gates.append(
        _gate(
            "commit_identity_recorded",
            commit_ok,
            f"target_commit={commit};target_branch={receipt.get('target_branch')}",
            "target_commit missing" if not commit_ok else "commit identity present",
        )
    )

    now_utc = now or datetime.now(timezone.utc)
    expires_at = _parse_expires_at(approval.get("expires_at"))
    if expires_at is None:
        unexpired = True
        expiry_detail = "approval has no expires_at (open-ended)"
    else:
        unexpired = now_utc <= expires_at
        expiry_detail = f"expires_at={expires_at.isoformat()};now={now_utc.isoformat()}"
    gates.append(
        _gate(
            "approval_unexpired",
            unexpired,
            expiry_detail,
            "approval expired" if not unexpired else "approval unexpired",
        )
    )

    if ledger_record is None:
        gates.append(
            _gate(
                "ledger_chain_consistent",
                True,
                "ledger_record=absent",
                "optional ledger record not supplied; gate not required",
            )
        )
    else:
        ledger_errors = validate_verification_execution_ledger_record(ledger_record)
        receipt_digest = str(receipt.get("verification_execution_receipt_digest", ""))
        plan_digest = str(plan.get("verification_execution_plan_digest", ""))
        approval_digest = str(approval.get("verification_execution_approval_digest", ""))
        expected_chain = digest_jsonable(
            {
                "plan_digest": plan_digest,
                "approval_digest": approval_digest,
                "receipt_digest": receipt_digest,
                "receipt_status": receipt.get("receipt_status"),
                "runner_mode": receipt.get("runner_mode"),
            }
        )
        chain_matches = ledger_record.get("chain_digest") == expected_chain
        ledger_ok = (
            not ledger_errors
            and ledger_record.get("kind") == VERIFICATION_EXECUTION_LEDGER_RECORD_KIND
            and ledger_record.get("valid") is True
            and chain_matches
        )
        gates.append(
            _gate(
                "ledger_chain_consistent",
                ledger_ok,
                f"ledger_digest={ledger_record.get('verification_execution_ledger_record_digest', '')}",
                (
                    "; ".join(ledger_errors)
                    if ledger_errors
                    else ("chain_digest mismatch" if not chain_matches else "ledger binds plan/approval/receipt")
                ),
            )
        )

    if expected_profile:
        process_results = receipt.get("process_results") if isinstance(receipt.get("process_results"), list) else []
        profiles = {
            item.get("profile")
            for item in process_results
            if isinstance(item, dict) and isinstance(item.get("profile"), str)
        }
        profile_ok = expected_profile in profiles
        gates.append(
            _gate(
                "profile_matches_capability",
                profile_ok,
                f"expected_profile={expected_profile};observed={sorted(profiles)}",
                "profile mismatch" if not profile_ok else "expected profile present in process_results",
            )
        )

    failed = [gate for gate in gates if gate["state"] == "FAIL"]
    overall = "PASS" if not failed else "FAIL"
    evidence = {
        "kind": PROMOTION_EVIDENCE_KIND,
        "schema_version": PROMOTION_EVIDENCE_SCHEMA_VERSION,
        "evidence_state": PROMOTION_EVIDENCE_STATE,
        "capability_name": (capability_name or "").strip(),
        "overall_state": overall,
        "ready_for_operator_promotion_review": overall == "PASS",
        "gates": gates,
        "failed_gates": [gate["gate"] for gate in failed],
        "subject_refs": {
            "plan_path": str(plan_path),
            "plan_digest": plan.get("verification_execution_plan_digest", ""),
            "approval_path": str(approval_path),
            "approval_digest": approval.get("verification_execution_approval_digest", ""),
            "receipt_path": str(receipt_path),
            "receipt_digest": receipt.get("verification_execution_receipt_digest", ""),
            "ledger_path": str(ledger_path) if ledger_path is not None else None,
            "ledger_digest": (
                ledger_record.get("verification_execution_ledger_record_digest")
                if isinstance(ledger_record, dict)
                else None
            ),
        },
        "target_commit": receipt.get("target_commit"),
        "target_branch": receipt.get("target_branch"),
        "receipt_status": receipt.get("receipt_status"),
        "runner_mode": receipt.get("runner_mode"),
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "flips_matrix": False,
        "allowed_actions": ["evaluate_promotion_gates", "validate_promotion_evidence"],
        "performed_actions": ["evaluate_promotion_gates"],
        "governance": build_standard_governance("verification_promotion_evidence"),
    }
    return attach_digest(evidence, digest_key="verification_promotion_evidence_digest")


def evaluate_verification_promotion_gates_from_files(
    *,
    plan_path: Path,
    approval_path: Path,
    receipt_path: Path,
    ledger_path: Path | None = None,
    capability_name: str = "",
    expected_profile: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    plan = _load_json_object(plan_path)
    approval = _load_json_object(approval_path)
    receipt = _load_json_object(receipt_path)
    ledger_record = _load_json_object(ledger_path) if ledger_path is not None else None
    return evaluate_verification_promotion_gates(
        plan=plan,
        approval=approval,
        receipt=receipt,
        plan_path=plan_path,
        approval_path=approval_path,
        receipt_path=receipt_path,
        ledger_record=ledger_record,
        ledger_path=ledger_path,
        capability_name=capability_name,
        expected_profile=expected_profile,
        now=now,
    )


def dumps_promotion_evidence(evidence: dict[str, Any]) -> str:
    return json_lib.dumps(evidence, indent=2, sort_keys=True) + "\n"


def write_promotion_evidence(evidence: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_promotion_evidence(evidence), encoding="utf-8")


def validate_promotion_evidence(evidence: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return ["promotion evidence must be a JSON object"]
    if evidence.get("kind") != PROMOTION_EVIDENCE_KIND:
        errors.append(f"kind must be {PROMOTION_EVIDENCE_KIND}")
    if evidence.get("schema_version") != PROMOTION_EVIDENCE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROMOTION_EVIDENCE_SCHEMA_VERSION}")
    if evidence.get("evidence_state") != PROMOTION_EVIDENCE_STATE:
        errors.append(f"evidence_state must be {PROMOTION_EVIDENCE_STATE}")
    if evidence.get("overall_state") not in {"PASS", "FAIL"}:
        errors.append("overall_state must be PASS or FAIL")
    if evidence.get("grants_runtime_authority") is not False:
        errors.append("grants_runtime_authority must be false")
    if evidence.get("grants_action_authority") is not False:
        errors.append("grants_action_authority must be false")
    if evidence.get("flips_matrix") is not False:
        errors.append("flips_matrix must be false")
    gates = evidence.get("gates")
    if not isinstance(gates, list) or not gates:
        errors.append("gates must be a non-empty list")
    else:
        seen: set[str] = set()
        for index, gate in enumerate(gates):
            prefix = f"gates[{index}]"
            if not isinstance(gate, dict):
                errors.append(f"{prefix} must be an object")
                continue
            name = gate.get("gate")
            if not isinstance(name, str) or not name:
                errors.append(f"{prefix}.gate must be a non-empty string")
            elif name in seen:
                errors.append(f"{prefix}.gate must be unique")
            else:
                seen.add(name)
            if gate.get("state") not in {"PASS", "FAIL"}:
                errors.append(f"{prefix}.state must be PASS or FAIL")
            if not isinstance(gate.get("evidence"), str):
                errors.append(f"{prefix}.evidence must be a string")
    errors.extend(validate_standard_governance(evidence.get("governance"), "verification_promotion_evidence"))
    digest = evidence.get("verification_promotion_evidence_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("verification_promotion_evidence_digest must be a 64-character hex string")
    return errors
