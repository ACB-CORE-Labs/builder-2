"""Plan Set 1 governed-run lifecycle and runtime-adapter seam.

This module composes existing WRP/model/ledger artifacts into one bounded run
without making the adapter an authority source.  Adapters report lifecycle
outcomes; :class:`GovernedRun` owns checkpoints, evidence events, and the
fail-closed resume rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from builder_ii.core.canonical_json import canonical_digest
from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event

RUN_MANIFEST_KIND = "builder_ii.governed_run_manifest"
CHECKPOINT_KIND = "builder_ii.governed_run_checkpoint"
RUN_RECEIPT_KIND = "builder_ii.governed_run_receipt"
SCHEMA_VERSION = 1


def _write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _digest(data: dict[str, Any]) -> str:
    return canonical_digest({key: value for key, value in data.items() if key != "digest"})


@dataclass(frozen=True)
class AdapterResult:
    """A runtime adapter result; it contains no authority decision."""

    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class RuntimeAdapter(Protocol):
    """Lifecycle-only interface implemented by runtime substrates."""

    name: str
    version: str

    def prepare(self, run: GovernedRun) -> AdapterResult: ...

    def start(self, run: GovernedRun, step_index: int) -> AdapterResult: ...

    def resume(self, run: GovernedRun, checkpoint: dict[str, Any]) -> AdapterResult: ...

    def interrupt(self, run: GovernedRun) -> AdapterResult: ...

    def cancel(self, run: GovernedRun) -> AdapterResult: ...

    def inspect(self, run: GovernedRun) -> dict[str, Any]: ...

    def close(self, run: GovernedRun) -> AdapterResult: ...


class SyntheticRuntimeAdapter:
    """Deterministic adapter used by the Plan Set 1 exit-gate scenario.

    ``interrupt_at`` and ``fail_at`` are zero-based step indexes.  No model,
    tool, shell, filesystem target, or provider is invoked.
    """

    name = "synthetic"
    version = "1"
    executes_model = False

    def __init__(self, *, interrupt_at: int | None = None, fail_at: int | None = None) -> None:
        self.interrupt_at = interrupt_at
        self.fail_at = fail_at

    def prepare(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("prepared", {"synthetic": True})

    def start(self, run: GovernedRun, step_index: int) -> AdapterResult:
        if self.fail_at == step_index:
            return AdapterResult("failed", {"step_index": step_index}, "synthetic failure")
        if self.interrupt_at == step_index:
            return AdapterResult("interrupted", {"step_index": step_index})
        return AdapterResult("completed", {"step_index": step_index, "claim": "step executed"})

    def resume(self, run: GovernedRun, checkpoint: dict[str, Any]) -> AdapterResult:
        return self.start(run, int(checkpoint["next_step_index"]))

    def interrupt(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("interrupted", {"step_index": run.next_step_index})

    def cancel(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("cancelled", {"next_step_index": run.next_step_index})

    def inspect(self, run: GovernedRun) -> dict[str, Any]:
        return {"adapter": self.name, "version": self.version, "next_step_index": run.next_step_index}

    def close(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("closed", {"completed_steps": list(run.completed_steps)})


class WrpSubagentRuntimeAdapter:
    """Adapter for the existing governed WRP subagent step seam.

    The adapter delegates model work to ``run_governed_subagent_step``; it does
    not bypass the model gateway, budget, approval, or receipt path.
    """

    name = "wrp-subagent"
    version = "1"
    executes_model = True

    def __init__(self, *, role: str, model_id: str, plan_digest: str, approved_by: str, budget: dict[str, Any]):
        self.role = role
        self.model_id = model_id
        self.plan_digest = plan_digest
        self.approved_by = approved_by
        self.budget = budget

    def prepare(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("prepared", {"wrp": True, "role": self.role})

    def start(self, run: GovernedRun, step_index: int) -> AdapterResult:
        from builder_ii.wrp.subagent_executor import run_governed_subagent_step

        result = run_governed_subagent_step(
            role=self.role,
            task=f"{run.task} [step {step_index + 1}/{len(run.steps)}]",
            model_id=self.model_id,
            prompt=run.steps[step_index],
            plan_digest=self.plan_digest,
            approved_by=self.approved_by,
            budget=self.budget,
            session_id=run.run_id,
            artifact_dir=run.output_dir / "artifacts",
        )
        return AdapterResult("completed", {"wrp_receipt": result})

    def resume(self, run: GovernedRun, checkpoint: dict[str, Any]) -> AdapterResult:
        return self.start(run, int(checkpoint["next_step_index"]))

    def interrupt(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("interrupted", {"next_step_index": run.next_step_index})

    def cancel(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("cancelled", {"next_step_index": run.next_step_index})

    def inspect(self, run: GovernedRun) -> dict[str, Any]:
        return {"adapter": self.name, "version": self.version, "next_step_index": run.next_step_index}

    def close(self, run: GovernedRun) -> AdapterResult:
        return AdapterResult("closed", {})


class GovernedRun:
    """One lifecycle over existing artifacts and one ordered evidence chain."""

    def __init__(
        self,
        *,
        run_id: str,
        target: str,
        task: str,
        steps: list[str],
        output_dir: Path,
        adapter: RuntimeAdapter,
        base_revision_digest: str = "0" * 64,
        profile_digest: str = "0" * 64,
        policy_digest: str = "0" * 64,
        config_digest: str = "0" * 64,
        wrp_plan_digest: str = "0" * 64,
        tool_inventory_digest: str = "0" * 64,
    ) -> None:
        if not run_id or not task.strip() or not steps:
            raise ValueError("run_id, task, and at least one step are required")
        self.run_id = run_id
        self.target = target
        self.task = task.strip()
        self.steps = list(steps)
        self.output_dir = output_dir
        self.events_dir = output_dir / "events"
        self.checkpoint_path = output_dir / "checkpoint.json"
        self.manifest_path = output_dir / "run-manifest.json"
        self.receipt_path = output_dir / "run-receipt.json"
        self.adapter = adapter
        self.next_step_index = 0
        self.completed_steps: list[int] = []
        self.state = "prepared"
        self._manifest = self._create_manifest(
            base_revision_digest,
            profile_digest,
            policy_digest,
            config_digest,
            wrp_plan_digest,
            tool_inventory_digest,
        )

    def _create_manifest(self, *digests: str) -> dict[str, Any]:
        if any(len(value) != 64 for value in digests):
            raise ValueError("all lifecycle binding values must be SHA-256 digests")
        body: dict[str, Any] = {
            "kind": RUN_MANIFEST_KIND,
            "schema_version": SCHEMA_VERSION,
            "manifest_state": "RECORDED_ONLY",
            "run_id": self.run_id,
            "target": self.target,
            "task": self.task,
            "steps": list(self.steps),
            "base_revision_digest": digests[0],
            "profile_digest": digests[1],
            "policy_digest": digests[2],
            "config_digest": digests[3],
            "wrp_plan_digest": digests[4],
            "tool_inventory_digest": digests[5],
            "runtime_adapter": {"name": self.adapter.name, "version": self.adapter.version},
            "approval_requirements": ["operator approval is external to this artifact"],
            "executes_model": bool(getattr(self.adapter, "executes_model", False)),
            "grants_authority": False,
            "artifact_is_authority": False,
        }
        body["digest"] = _digest(body)
        return body

    @property
    def manifest_digest(self) -> str:
        return str(self._manifest["digest"])

    def _event(self, event_type: str, message: str, *, decision: str = "recorded") -> dict[str, Any]:
        return append_runtime_event(
            events_dir=self.events_dir,
            session_id=self.run_id,
            event_type=event_type,
            message=message,
            command_surface="builder-governed-run",
            stage="initialized",
            decision_result=decision,
        )

    def _checkpoint(self) -> dict[str, Any]:
        chain = validate_event_chain_integrity(self.events_dir)
        body: dict[str, Any] = {
            "kind": CHECKPOINT_KIND,
            "schema_version": SCHEMA_VERSION,
            "checkpoint_state": "INTERRUPT_RECORDED",
            "run_id": self.run_id,
            "manifest_digest": self.manifest_digest,
            "next_step_index": self.next_step_index,
            "completed_steps": list(self.completed_steps),
            "event_count": chain.get("event_count", 0),
            "event_chain_digest": canonical_digest(chain),
            "policy_digest": self._manifest["policy_digest"],
            "expires_at": None,
            "grants_authority": False,
            "artifact_is_authority": False,
        }
        body["digest"] = _digest(body)
        _write_json(body, self.checkpoint_path)
        return body

    def _record_result(self, result: AdapterResult) -> None:
        if result.status == "completed":
            self.completed_steps.append(self.next_step_index)
            self.next_step_index += 1
            self._event("subagent_step", f"completed step {self.completed_steps[-1]}", decision="executed")
        elif result.status == "interrupted":
            self.state = "interrupted"
            self._event("wrp_live_run_started", "run interrupted at checkpoint boundary")
            self._checkpoint()
        elif result.status == "failed":
            self.state = "failed"
            self._event("deepagents_runtime_failed", result.error or "runtime adapter failed", decision="failed")
        elif result.status == "cancelled":
            self.state = "cancelled"
            self._event("kill_switch", "run cancelled before remaining steps", decision="cancelled")

    def prepare(self) -> dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(self._manifest, self.manifest_path)
        result = self.adapter.prepare(self)
        if result.status != "prepared":
            raise RuntimeError(result.error or "adapter preparation failed")
        self._event("wrp_live_run_started", "governed run prepared")
        return dict(self._manifest)

    def start(self) -> str:
        if self.state not in {"prepared", "interrupted"}:
            raise RuntimeError(f"run cannot start from state {self.state}")
        while self.next_step_index < len(self.steps):
            result = self.adapter.start(self, self.next_step_index)
            self._record_result(result)
            if result.status != "completed":
                return self.state
        self.state = "completed"
        self._event("wrp_live_run_completed", "all declared steps completed", decision="completed")
        return self.state

    def interrupt(self) -> str:
        result = self.adapter.interrupt(self)
        self._record_result(result)
        return self.state

    def cancel(self) -> str:
        result = self.adapter.cancel(self)
        self._record_result(result)
        return self.state

    def resume(self) -> str:
        if self.state != "interrupted" or not self.checkpoint_path.is_file():
            raise RuntimeError("resume requires an interrupted run with a checkpoint")
        checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        errors = validate_checkpoint(checkpoint, manifest=self._manifest, events_dir=self.events_dir)
        if errors:
            raise ValueError("checkpoint rejected: " + "; ".join(errors))
        result = self.adapter.resume(self, checkpoint)
        self._record_result(result)
        return self.start() if result.status == "completed" else self.state

    def inspect(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state,
            "next_step_index": self.next_step_index,
            "completed_steps": list(self.completed_steps),
            "adapter": self.adapter.inspect(self),
        }

    def close(self) -> dict[str, Any]:
        if self.state not in {"completed", "failed", "cancelled"}:
            raise RuntimeError(f"close requires a terminal run, got {self.state}")
        result = self.adapter.close(self)
        chain = validate_event_chain_integrity(self.events_dir)
        receipt: dict[str, Any] = {
            "kind": RUN_RECEIPT_KIND,
            "schema_version": SCHEMA_VERSION,
            "receipt_state": "RECORDED_ONLY",
            "run_id": self.run_id,
            "manifest_digest": self.manifest_digest,
            "terminal_state": self.state,
            "completed_steps": list(self.completed_steps),
            "unexecuted_steps": list(range(self.next_step_index, len(self.steps))),
            "event_chain": chain,
            "adapter_close": result.evidence,
            "executes_model": False,
            "grants_authority": False,
            "artifact_is_authority": False,
        }
        receipt["digest"] = _digest(receipt)
        _write_json(receipt, self.receipt_path)
        return receipt


def validate_checkpoint(
    checkpoint: Any, *, manifest: dict[str, Any], events_dir: Path
) -> list[str]:
    errors: list[str] = []
    if not isinstance(checkpoint, dict):
        return ["checkpoint must be an object"]
    if checkpoint.get("kind") != CHECKPOINT_KIND:
        errors.append("checkpoint kind is invalid")
    if checkpoint.get("schema_version") != SCHEMA_VERSION:
        errors.append("checkpoint schema_version is invalid")
    if checkpoint.get("run_id") != manifest.get("run_id"):
        errors.append("checkpoint belongs to a different run")
    if checkpoint.get("manifest_digest") != manifest.get("digest"):
        errors.append("checkpoint manifest digest does not match run")
    if checkpoint.get("policy_digest") != manifest.get("policy_digest"):
        errors.append("checkpoint policy digest is incompatible")
    if checkpoint.get("grants_authority") is not False:
        errors.append("checkpoint cannot grant authority")
    if checkpoint.get("artifact_is_authority") is not False:
        errors.append("checkpoint cannot be authority")
    expires_at = checkpoint.get("expires_at")
    if expires_at is not None:
        try:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                errors.append("checkpoint is expired")
        except ValueError:
            errors.append("checkpoint expires_at is invalid")
    if checkpoint.get("digest") != _digest(checkpoint):
        errors.append("checkpoint digest is invalid")
    chain = validate_event_chain_integrity(events_dir)
    if checkpoint.get("event_chain_digest") != canonical_digest(chain):
        errors.append("checkpoint event chain digest does not match current chain")
    return errors
