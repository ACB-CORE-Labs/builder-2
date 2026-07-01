from __future__ import annotations

import uuid
import json as json_lib
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.deepagents_bridge import deepagents_availability
from builder_ii.deepagents_work_artifacts import (
    DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
    DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
    DEEPAGENTS_WORK_PLAN_KIND,
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
    DEEPAGENTS_SUBAGENT_RESULT_KIND,
    DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
    create_deepagents_subagent_assignment,
    create_deepagents_subagent_result,
    create_deepagents_blocked_action_record,
    create_deepagents_proposal_result,
    canonical_digest,
    _default_authority_boundary,
    _default_governance,
    _artifact_ref
)

def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def create_deepagents_runtime_envelope(
    session_id: str,
    work_plan_ref: dict[str, Any],
    execution_receipt_refs: list[dict[str, Any]],
    envelope_state: str = "RUNNING",
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
        "schema_version": 1,
        "session_id": session_id,
        "work_plan_ref": work_plan_ref,
        "execution_receipt_refs": execution_receipt_refs,
        "envelope_state": envelope_state,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_runtime"),
        "governance": _default_governance("deepagents_runtime"),
    }
    content["digest"] = _digest(content)
    return content

def create_deepagents_subagent_execution_receipt(
    subagent_profile: str,
    assignment_ref: dict[str, Any],
    result_ref: dict[str, Any],
    receipt_state: str = "EXECUTED_ONLY",
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
        "schema_version": 1,
        "subagent_profile": subagent_profile,
        "assignment_ref": assignment_ref,
        "result_ref": result_ref,
        "receipt_state": receipt_state,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_runtime"),
        "governance": _default_governance("deepagents_runtime"),
    }
    content["digest"] = _digest(content)
    return content

class DeepAgentsRuntimeHarness:
    def __init__(self, settings: Settings, work_plan_path: Path):
        self.settings = settings
        self.work_plan_path = work_plan_path
        self.session_id = str(uuid.uuid4())

    def run(self, output_envelope_path: Path, output_receipts_dir: Path) -> dict[str, Any]:
        availability = deepagents_availability()
        if not availability.available:
            raise ImportError("deepagents dependency is not available")

        # Load plan
        with open(self.work_plan_path, "r", encoding="utf-8") as f:
            plan = json_lib.load(f)

        # Check policy allowed/denied tools and ensure no mutation/writes
        policy_ref = plan.get("deepagents_policy_ref")
        if policy_ref:
            policy_path = Path(policy_ref.get("path", ""))
            if policy_path.exists():
                with open(policy_path, "r", encoding="utf-8") as f:
                    policy = json_lib.load(f)
                
                # Check for denied tools
                denied_tools = policy.get("governed_factory", {}).get("deny_tools", [])
                allow_tools = policy.get("governed_factory", {}).get("allow_tools", [])
                
                # If any tool required/used is denied, or model/tool/shell is unapproved
                for tool in denied_tools:
                    if tool in allow_tools:
                        blocked_record = create_deepagents_blocked_action_record(
                            target=plan.get("target", "builder"),
                            denied_capability="tool execution",
                            triggering_artifact=plan,
                            triggering_artifact_path=self.work_plan_path
                        )
                        output_receipts_dir.mkdir(parents=True, exist_ok=True)
                        record_path = output_receipts_dir / "blocked-action.json"
                        with open(record_path, "w", encoding="utf-8") as f:
                            json_lib.dump(blocked_record, f, indent=2, sort_keys=True)
                        raise ValueError(f"Plan allows denied tool: {tool}")

        # Check if plan contains denied capabilities
        blocked_caps = plan.get("blocked_capabilities", [])
        if "model execution" in blocked_caps and plan.get("executes_model"):
            raise ValueError("Plan contains blocked capability: model execution")

        receipt_refs = []
        proposed_subagents = plan.get("proposed_subagents", [])
        for idx, subagent in enumerate(proposed_subagents):
            # Create assignment
            assignment = create_deepagents_subagent_assignment(
                target=plan.get("target", "builder"),
                task=plan.get("task", ""),
                subagent_profile=subagent,
                work_plan=plan,
                work_plan_path=self.work_plan_path
            )
            output_receipts_dir.mkdir(parents=True, exist_ok=True)
            assignment_path = output_receipts_dir / f"assignment-{idx}.json"
            with open(assignment_path, "w", encoding="utf-8") as f:
                json_lib.dump(assignment, f, indent=2, sort_keys=True)

            # Create proposal result
            result = create_deepagents_subagent_result(
                target=plan.get("target", "builder"),
                subagent_profile=subagent,
                summary=f"Subagent {subagent} successfully completed planning task.",
                subagent_assignment=assignment,
                subagent_assignment_path=assignment_path
            )
            result_path = output_receipts_dir / f"result-{idx}.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json_lib.dump(result, f, indent=2, sort_keys=True)

            # Create execution receipt
            receipt = create_deepagents_subagent_execution_receipt(
                subagent_profile=subagent,
                assignment_ref=_artifact_ref(assignment, role="assignment", path=assignment_path, name=f"subagent assignment {subagent}"),
                result_ref=_artifact_ref(result, role="result", path=result_path, name=f"subagent result {subagent}"),
            )
            receipt_path = output_receipts_dir / f"receipt-{idx}.json"
            with open(receipt_path, "w", encoding="utf-8") as f:
                json_lib.dump(receipt, f, indent=2, sort_keys=True)

            receipt_refs.append(_artifact_ref(receipt, role=f"execution_receipt_{idx}", path=receipt_path, name=f"execution receipt {subagent}"))

        # Create envelope
        envelope = create_deepagents_runtime_envelope(
            session_id=self.session_id,
            work_plan_ref=_artifact_ref(plan, role="work_plan", path=self.work_plan_path, name="work plan"),
            execution_receipt_refs=receipt_refs,
            envelope_state="COMPLETED",
        )
        output_envelope_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_envelope_path, "w", encoding="utf-8") as f:
            json_lib.dump(envelope, f, indent=2, sort_keys=True)

        return envelope

    def collect_results(self, envelope_path: Path, output_proposal_path: Path) -> dict[str, Any]:
        with open(envelope_path, "r", encoding="utf-8") as f:
            envelope = json_lib.load(f)

        # Load plan
        with open(self.work_plan_path, "r", encoding="utf-8") as f:
            plan = json_lib.load(f)

        # Retrieve results
        results = []
        result_paths = []
        for ref in envelope.get("execution_receipt_refs", []):
            receipt_path = Path(ref.get("path", ""))
            if receipt_path.exists():
                with open(receipt_path, "r", encoding="utf-8") as f:
                    receipt = json_lib.load(f)
                result_ref = receipt.get("result_ref", {})
                res_path = Path(result_ref.get("path", ""))
                if res_path.exists():
                    with open(res_path, "r", encoding="utf-8") as f:
                        results.append(json_lib.load(f))
                    result_paths.append(res_path)

        if not results:
            raise ValueError("No results found to collect.")

        proposal = create_deepagents_proposal_result(
            target=plan.get("target", "builder"),
            work_plan=plan,
            reviewed_results=results,
            work_plan_path=self.work_plan_path,
            reviewed_result_paths=result_paths
        )

        output_proposal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_proposal_path, "w", encoding="utf-8") as f:
            json_lib.dump(proposal, f, indent=2, sort_keys=True)

        return proposal
