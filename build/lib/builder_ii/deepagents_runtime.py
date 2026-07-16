from __future__ import annotations

import hashlib
import json as json_lib
import uuid
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.deepagents_bridge import deepagents_availability
from builder_ii.deepagents_work_artifacts import (
    DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
    DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
    _artifact_ref,
    _default_authority_boundary,
    _default_governance,
    create_deepagents_blocked_action_record,
    create_deepagents_proposal_result,
    create_deepagents_subagent_assignment,
    create_deepagents_subagent_result,
)


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json_lib.load(f)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _ref_path(ref: Any, *, field: str) -> Path:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} must be a JSON object reference")

    raw_path = ref.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"{field}.path must be a non-empty string")

    path = Path(raw_path)
    if not path.is_file():
        raise ValueError(f"{field}.path must point to a readable file: {path}")

    return path


def _string_list(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return value


def _assert_work_plan_ref_matches(envelope: dict[str, Any], plan: dict[str, Any], work_plan_path: Path) -> None:
    actual_ref = envelope.get("work_plan_ref")
    if not isinstance(actual_ref, dict):
        raise ValueError("Envelope work_plan_ref must be a JSON object reference")

    expected_ref = _artifact_ref(
        plan,
        role="work_plan",
        path=work_plan_path,
        name="work plan",
    )
    for field in ("role", "kind", "path", "sha256"):
        if actual_ref.get(field) != expected_ref[field]:
            raise ValueError("Envelope work_plan_ref does not match requested work plan")


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

        plan = _load_json_object(self.work_plan_path, label="Work plan")

        policy_ref = plan.get("deepagents_policy_ref")
        if policy_ref is not None:
            policy_path = _ref_path(policy_ref, field="deepagents_policy_ref")
            policy = _load_json_object(policy_path, label="Deepagents policy")
            governed_factory = policy.get("governed_factory")
            if not isinstance(governed_factory, dict):
                raise ValueError("Deepagents policy governed_factory must be a JSON object")

            denied_tools = _string_list(
                governed_factory.get("deny_tools"),
                field="deepagents_policy.governed_factory.deny_tools",
            )
            allow_tools = _string_list(
                governed_factory.get("allow_tools"),
                field="deepagents_policy.governed_factory.allow_tools",
            )

            for tool in denied_tools:
                if tool in allow_tools:
                    blocked_record = create_deepagents_blocked_action_record(
                        target=plan.get("target", "builder"),
                        denied_capability="tool execution",
                        triggering_artifact=plan,
                        triggering_artifact_path=self.work_plan_path,
                    )
                    output_receipts_dir.mkdir(parents=True, exist_ok=True)
                    record_path = output_receipts_dir / "blocked-action.json"
                    record_path.write_text(
                        json_lib.dumps(blocked_record, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                    raise ValueError(f"Plan allows denied tool: {tool}")

        blocked_caps = _string_list(
            plan.get("blocked_capabilities"),
            field="work_plan.blocked_capabilities",
        )
        if "model execution" in blocked_caps and plan.get("executes_model"):
            raise ValueError("Plan contains blocked capability: model execution")

        proposed_subagents = _string_list(
            plan.get("proposed_subagents"),
            field="work_plan.proposed_subagents",
        )
        receipt_refs = []
        output_receipts_dir.mkdir(parents=True, exist_ok=True)

        for idx, subagent in enumerate(proposed_subagents):
            assignment = create_deepagents_subagent_assignment(
                target=plan.get("target", "builder"),
                task=plan.get("task", ""),
                subagent_profile=subagent,
                work_plan=plan,
                work_plan_path=self.work_plan_path,
            )
            assignment_path = output_receipts_dir / f"assignment-{idx}.json"
            assignment_path.write_text(
                json_lib.dumps(assignment, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            # R3 honesty: this legacy run-plan path projects assignment/result/receipt artifacts
            # structurally — it runs no backend and verifies nothing. The summary is derived from
            # that fact (proposal-only, no execution, no verified result), never an asserted success.
            # The bounded protocol lane (candidate -> seal -> run-approved) is where execution and
            # discharge classification actually live.
            result = create_deepagents_subagent_result(
                target=plan.get("target", "builder"),
                subagent_profile=subagent,
                summary=(
                    f"Subagent {subagent}: planning assignment projected as a proposal-only structural "
                    "record; no backend ran and no result was checked (run-plan legacy projection)."
                ),
                subagent_assignment=assignment,
                subagent_assignment_path=assignment_path,
            )
            result_path = output_receipts_dir / f"result-{idx}.json"
            result_path.write_text(
                json_lib.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            receipt = create_deepagents_subagent_execution_receipt(
                subagent_profile=subagent,
                assignment_ref=_artifact_ref(
                    assignment,
                    role="assignment",
                    path=assignment_path,
                    name=f"subagent assignment {subagent}",
                ),
                result_ref=_artifact_ref(
                    result,
                    role="result",
                    path=result_path,
                    name=f"subagent result {subagent}",
                ),
            )
            receipt_path = output_receipts_dir / f"receipt-{idx}.json"
            receipt_path.write_text(
                json_lib.dumps(receipt, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            receipt_refs.append(
                _artifact_ref(
                    receipt,
                    role=f"execution_receipt_{idx}",
                    path=receipt_path,
                    name=f"execution receipt {subagent}",
                )
            )

        envelope = create_deepagents_runtime_envelope(
            session_id=self.session_id,
            work_plan_ref=_artifact_ref(
                plan,
                role="work_plan",
                path=self.work_plan_path,
                name="work plan",
            ),
            execution_receipt_refs=receipt_refs,
            envelope_state="COMPLETED",
        )
        output_envelope_path.parent.mkdir(parents=True, exist_ok=True)
        output_envelope_path.write_text(
            json_lib.dumps(envelope, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return envelope

    def collect_results(self, envelope_path: Path, output_proposal_path: Path) -> dict[str, Any]:
        envelope = _load_json_object(envelope_path, label="Envelope")
        plan = _load_json_object(self.work_plan_path, label="Work plan")
        _assert_work_plan_ref_matches(envelope, plan, self.work_plan_path)

        execution_receipt_refs = envelope.get("execution_receipt_refs")
        if not isinstance(execution_receipt_refs, list):
            raise ValueError("Envelope execution_receipt_refs must be a list")

        results = []
        result_paths = []
        for idx, ref in enumerate(execution_receipt_refs):
            receipt_path = _ref_path(ref, field=f"execution_receipt_refs[{idx}]")
            receipt = _load_json_object(receipt_path, label="Subagent execution receipt")

            result_ref = receipt.get("result_ref")
            result_path = _ref_path(result_ref, field=f"execution_receipt_refs[{idx}].result_ref")
            result = _load_json_object(result_path, label="Subagent result")
            results.append(result)
            result_paths.append(result_path)

        if not results:
            raise ValueError("No results found to collect.")

        proposal = create_deepagents_proposal_result(
            target=plan.get("target", "builder"),
            work_plan=plan,
            reviewed_results=results,
            work_plan_path=self.work_plan_path,
            reviewed_result_paths=result_paths,
        )

        output_proposal_path.parent.mkdir(parents=True, exist_ok=True)
        output_proposal_path.write_text(
            json_lib.dumps(proposal, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return proposal
