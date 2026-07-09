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
from builder_ii.deepagents_execution import (
    DISCHARGE_BLOCKED,
    PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
    PROTOCOL_FAKE_BACKEND,
    classify_discharge,
    create_deepagents_replay_report,
    is_ladder4_seal,
    validate_deepagents_event_ledger,
    validate_deepagents_execution_approval,
    validate_deepagents_execution_approval_against_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
    validate_deepagents_run_envelope,
)
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


def evaluate_delegation_tree_promotion_gates(
    *,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    obligations: list[dict[str, Any]],
    event_records: list[tuple[dict[str, Any], Path]],
    replay_report: dict[str, Any],
    replay_report_path: str | Path,
    event_ledger: dict[str, Any],
    event_ledger_path: str | Path,
    run_envelope: dict[str, Any],
    envelope_path: str | Path,
    receipt: dict[str, Any],
    receipt_path: str | Path,
    candidate_path: str | Path,
    approval_path: str | Path,
    capability_name: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate machine-checkable promotion gates over a governed obligation-delegation run bundle.

    Gate coverage mapping:
    1. seal_valid -> R2 HITL boundary (Gate 5)
    2. candidate_bound_to_seal -> R2 HITL boundary (Gate 5)
    3. backend_is_ci_truth -> R2 Scope anti-inflation guard
    4. event_chain_intact -> Law 2 chain integrity + R2 Output artifact (Gate 6)
    5. mints_attenuate_authority -> Law 1 authority attenuation
    6. refusals_named_and_fixable -> R2 Failure mode (Gate 4)
    7. discharges_rederive -> Law 2 (no belief without discharge) + anti-forgery
    8. bundle_artifacts_valid -> R2 Output artifact (Gate 6)
    9. ledger_binds_replay -> chain consistency

    NOTE: This artifact does NOT cover Docs (Gate 1), Tests (Gate 2), Command surface (Gate 3),
    or Rollback (Gate 7). Those are human/closure-audit gates asserted by the operator in PR-8.
    """
    gates: list[dict[str, Any]] = []

    # 1. seal_valid
    seal_valid = is_ladder4_seal(approval) and not validate_deepagents_execution_approval(approval)
    gates.append(
        _gate(
            "seal_valid",
            seal_valid,
            f"approval_digest={approval.get('deepagents_execution_approval_digest', '')}",
            "seal validates" if seal_valid else "seal invalid or not a ladder4 seal",
        )
    )

    # 2. candidate_bound_to_seal
    binding_errors = validate_deepagents_execution_approval_against_candidate(approval, candidate)
    gates.append(
        _gate(
            "candidate_bound_to_seal",
            not binding_errors,
            f"candidate_digest={approval.get('candidate_digest', '')}",
            "; ".join(binding_errors) if binding_errors else "exactly one root seal binds candidate",
        )
    )

    # 3. backend_is_ci_truth
    backend_ok = candidate.get("backend_mode") == PROTOCOL_FAKE_BACKEND
    gates.append(
        _gate(
            "backend_is_ci_truth",
            backend_ok,
            f"backend_mode={candidate.get('backend_mode')}",
            "backend is protocol_fake" if backend_ok else "backend must be protocol_fake",
        )
    )

    # 4. event_chain_intact
    rederived_replay = create_deepagents_replay_report(
        session_id=receipt.get("session_id", ""),
        event_records=event_records
    )
    chain_ok = rederived_replay.get("valid") is True and rederived_replay.get("status") == "COMPLETED"
    gates.append(
        _gate(
            "event_chain_intact",
            chain_ok,
            f"rederived_status={rederived_replay.get('status')};valid={rederived_replay.get('valid')}",
            "chain intact and COMPLETED" if chain_ok else "chain invalid or not COMPLETED",
        )
    )

    # 5. mints_attenuate_authority
    mints_ok = True
    mint_details = []
    allowed_kinds = {k.get("kind"): k.get("max_count", 0) for k in approval.get("allowed_obligation_kinds", [])}
    mint_counts = {k: 0 for k in allowed_kinds}
    root_budget = approval.get("root_budget", {})

    for event, _ in event_records:
        if event.get("event_type") == "obligation_minted":
            payload = event.get("payload", {})
            kind = payload.get("obligation_kind")
            part = payload.get("budget_partition", {})
            if kind not in allowed_kinds:
                mints_ok = False
                mint_details.append(f"unapproved kind: {kind}")
                continue
            mint_counts[kind] += 1
            if mint_counts[kind] > allowed_kinds[kind]:
                mints_ok = False
                mint_details.append(f"count exceeded for {kind}")

            for k in ["max_subagents", "max_events", "max_output_bytes", "max_human_gates"]:
                if part.get(k, 0) > root_budget.get(k, 0):
                    mints_ok = False
                    mint_details.append(f"{k} widened")

    gates.append(
        _gate(
            "mints_attenuate_authority",
            mints_ok,
            f"mints_checked={sum(mint_counts.values())}",
            "; ".join(mint_details) if not mints_ok else "mints attenuate authority",
        )
    )

    # 6. refusals_named_and_fixable
    refusals_ok = True
    refusal_details = []
    for event, _ in event_records:
        if event.get("event_type") == "obligation_mint_refused":
            payload = event.get("payload", {})
            v_rule = payload.get("violated_rule")
            f_edit = payload.get("fixing_edit")
            d_state = payload.get("discharge_state")
            if not v_rule or not f_edit or d_state != DISCHARGE_BLOCKED:
                refusals_ok = False
                refusal_details.append(f"malformed refusal: {v_rule=} {f_edit=} {d_state=}")

    gates.append(
        _gate(
            "refusals_named_and_fixable",
            refusals_ok,
            "refusals_checked",
            "; ".join(refusal_details) if not refusals_ok else "refusals are named and fixable",
        )
    )

    # 7. discharges_rederive
    discharges_ok = True
    discharge_details = []
    ob_map = {ob.get("obligation_id", ""): ob for ob in obligations}

    result_map = {}
    for event, _ in event_records:
        if event.get("event_type") == "subagent_result_recorded":
            payload = event.get("payload", {})
            ob_digest = payload.get("obligation_digest")
            if ob_digest:
                result_map[ob_digest] = payload

    consumed_count = 0
    for event, _ in event_records:
        if event.get("event_type") == "obligation_consumed":
            consumed_count += 1
            payload = event.get("payload", {})
            ob_digest = payload.get("obligation_digest")
            recorded_state = payload.get("discharge_state")
            ob = ob_map.get(ob_digest)
            res = result_map.get(ob_digest, {})
            if not ob:
                discharges_ok = False
                discharge_details.append(f"obligation not found for digest {ob_digest}")
                continue
            produced_kind = res.get("kind", PROPOSAL_ONLY_RESULT_CONTRACT_KIND)
            rederived = classify_discharge(ob, res, produced_kind=produced_kind)
            if rederived.get("discharge_state") != recorded_state:
                discharges_ok = False
                discharge_details.append(f"forgery detected: recorded {recorded_state}, rederived {rederived}")

    gates.append(
        _gate(
            "discharges_rederive",
            discharges_ok,
            f"discharges_checked={consumed_count}",
            "; ".join(discharge_details) if not discharges_ok else "discharges matched re-derivation",
        )
    )

    # 8. bundle_artifacts_valid
    bundle_errors = []
    e = validate_deepagents_replay_report(replay_report)
    if e:
        bundle_errors.extend(e)
    e = validate_deepagents_event_ledger(event_ledger)
    if e:
        bundle_errors.extend(e)
    e = validate_deepagents_run_envelope(run_envelope)
    if e:
        bundle_errors.extend(e)
    e = validate_deepagents_execution_receipt(receipt)
    if e:
        bundle_errors.extend(e)

    if receipt.get("receipt_state") != "COMPLETED":
        bundle_errors.append(f"receipt_state must be COMPLETED, got {receipt.get('receipt_state')}")

    bundle_ok = len(bundle_errors) == 0
    gates.append(
        _gate(
            "bundle_artifacts_valid",
            bundle_ok,
            "artifacts_validated",
            "; ".join(bundle_errors) if not bundle_ok else "bundle artifacts validated",
        )
    )

    # 9. ledger_binds_replay
    ledger_ok = (
        not validate_deepagents_event_ledger(event_ledger)
        and event_ledger.get("replay_report_ref", {}).get("sha256") == replay_report.get("replay_digest")
        and event_ledger.get("event_count") == len(event_records)
    )
    gates.append(
        _gate(
            "ledger_binds_replay",
            ledger_ok,
            f"ledger_digest={event_ledger.get('ledger_digest', '')}",
            "ledger binds replay report" if ledger_ok else "ledger does not bind replay report or events",
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
            "candidate_path": str(candidate_path),
            "candidate_digest": candidate.get("deepagents_execution_candidate_digest", ""),
            "approval_path": str(approval_path),
            "seal_digest": approval.get("deepagents_execution_approval_digest", ""),
            "lane_policy_digest": approval.get("lane_policy_digest", ""),
            "events_dir": str(Path(replay_report_path).parent / "events"),
            "replay_report_path": str(replay_report_path),
            "replay_report_digest": replay_report.get("deepagents_replay_report_digest", ""),
            "event_ledger_path": str(event_ledger_path),
            "event_ledger_digest": event_ledger.get("deepagents_event_ledger_digest", ""),
            "envelope_path": str(envelope_path),
            "envelope_digest": run_envelope.get("deepagents_run_envelope_digest", ""),
            "receipt_path": str(receipt_path),
            "receipt_digest": receipt.get("deepagents_execution_receipt_digest", ""),
            "obligation_digests": [ob.get("obligation_id", "") for ob in obligations],
        },
        "target_commit": receipt.get("target_commit"),
        "target_branch": receipt.get("target_branch"),
        "receipt_status": receipt.get("receipt_status"),
        "runner_mode": receipt.get("runner_mode"),
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "flips_matrix": False,
        "gate_profile": "delegation_tree",
        "allowed_actions": ["evaluate_promotion_gates", "validate_promotion_evidence"],
        "performed_actions": ["evaluate_promotion_gates"],
        "governance": build_standard_governance("verification_promotion_evidence"),
    }
    return attach_digest(evidence, digest_key="verification_promotion_evidence_digest")

def evaluate_delegation_tree_promotion_gates_from_run(
    *,
    run_output_dir: Path,
    candidate_path: Path,
    approval_path: Path,
    obligation_paths: list[Path],
    capability_name: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    candidate = _load_json_object(candidate_path)
    approval = _load_json_object(approval_path)
    obligations = [_load_json_object(p) for p in obligation_paths]

    replay_report_path = run_output_dir / "deepagents-replay-report.json"
    event_ledger_path = run_output_dir / "deepagents-event-ledger.json"
    envelope_path = run_output_dir / "deepagents-run-envelope.json"
    receipt_path = run_output_dir / "deepagents-execution-receipt.json"

    replay_report = _load_json_object(replay_report_path)
    event_ledger = _load_json_object(event_ledger_path)
    run_envelope = _load_json_object(envelope_path)
    receipt = _load_json_object(receipt_path)

    events_dir = run_output_dir / "events"
    event_records = []
    if events_dir.is_dir():
        for p in events_dir.glob("event-*.json"):
            event_records.append((_load_json_object(p), p))
    event_records.sort(key=lambda item: item[0].get("timestamp", ""))

    return evaluate_delegation_tree_promotion_gates(
        candidate=candidate,
        approval=approval,
        obligations=obligations,
        event_records=event_records,
        replay_report=replay_report,
        replay_report_path=replay_report_path,
        event_ledger=event_ledger,
        event_ledger_path=event_ledger_path,
        run_envelope=run_envelope,
        envelope_path=envelope_path,
        receipt=receipt,
        receipt_path=receipt_path,
        candidate_path=candidate_path,
        approval_path=approval_path,
        capability_name=capability_name,
        now=now,
    )
