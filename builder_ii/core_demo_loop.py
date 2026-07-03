"""core_demo_loop.py

CORE target demo loop for builder-II.

ARCHITECTURE NOTE
-----------------
This module is a **CORE target adapter/demo**, not builder-II platform
identity.  All CORE-specific strings, invariant language, marker names,
and repository validation live inside ``CoreDemoAdapter``.  The generic
loop abstraction lives in ``GenericTargetDemoLoop``.

Public CLI entry-points are preserved for backward compatibility:
    run_core_demo_loop()  — unchanged public name

Governance (all modes)
-----------------------
* No model execution.
* No commit/push authority to any repository.
* No CORE Workbench/UI coupling.
* Source checkout is never modified.
* Temporary worktree is only created after explicit operator approval.
* No shell execution as agent authority.
* No autonomous source writes.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Generic demo loop abstraction
# ---------------------------------------------------------------------------


@dataclass
class TargetDemoContext:
    """Immutable context passed to every step of a target demo loop."""

    target_name: str
    target_repo: Path
    session_id: str
    operator_note: str = ""
    dry_run: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DemoStepResult:
    step_name: str
    passed: bool
    detail: str = ""
    artifact_path: Optional[Path] = None


@dataclass
class DemoLoopResult:
    target_name: str
    session_id: str
    steps: List[DemoStepResult] = field(default_factory=list)
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    governance_block: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return all(s.passed for s in self.steps)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "target_name": self.target_name,
            "session_id": self.session_id,
            "all_passed": self.all_passed,
            "completed_at": self.completed_at,
            "steps": [
                {
                    "step_name": s.step_name,
                    "passed": s.passed,
                    "detail": s.detail,
                    "artifact_path": str(s.artifact_path) if s.artifact_path else None,
                }
                for s in self.steps
            ],
            "governance_block": self.governance_block,
        }


class GenericTargetDemoLoop:
    """Generic governed demo loop base.

    Concrete target adapters implement ``build_steps()`` to return the
    ordered list of ``(step_name, callable)`` pairs to execute.

    Subclasses must also implement ``target_governance_block()`` which
    returns a dict that will be embedded in the loop result artifact.
    """

    def build_steps(
        self, ctx: TargetDemoContext
    ) -> Sequence[Tuple[str, Callable[[TargetDemoContext], DemoStepResult]]]:
        raise NotImplementedError

    def target_governance_block(self) -> Dict[str, Any]:
        return {
            "no_model_execution": True,
            "no_commit_push": True,
            "no_workbench_coupling": True,
            "source_checkout_untouched": True,
            "temporary_worktree_requires_approval": True,
        }

    def run(self, ctx: TargetDemoContext) -> DemoLoopResult:
        result = DemoLoopResult(
            target_name=ctx.target_name,
            session_id=ctx.session_id,
            governance_block=self.target_governance_block(),
        )
        for step_name, step_fn in self.build_steps(ctx):
            try:
                step_result = step_fn(ctx)
            except Exception as exc:  # pylint: disable=broad-except
                step_result = DemoStepResult(
                    step_name=step_name,
                    passed=False,
                    detail=f"Exception: {exc}",
                )
            result.steps.append(step_result)
            if not step_result.passed:
                # Abort on first failure to preserve governed state
                break
        return result


# ---------------------------------------------------------------------------
# CORE target adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoreDemoAdapter:
    """Adapter that owns all CORE-specific behaviour for the demo loop.

    All CORE-specific strings, invariant names, marker conventions, and
    repository validation logic live here — not in config_sources.py,
    not in platform-level modules.

    This is the minimum acceptable adapter boundary required by the
    builder-II architecture guardrails.
    """

    # CORE-specific string constants — owned by this adapter only
    TARGET_NAME: str = "core"
    INVARIANT_MARKER_PREFIX: str = "CORE_INVARIANT"
    REPO_VALIDATION_MARKER: str = "Cargo.toml"  # presence validates a CORE repo
    DEFAULT_WORKTREE_PREFIX: str = "builder-ii-core-worktree"
    GOVERNANCE_NOTE: str = (
        "CORE target demo — adapter-scoped, not builder-II platform identity"
    )

    def validate_repo(self, repo_path: Path) -> Tuple[bool, str]:
        """Return (ok, detail) for *repo_path* as a CORE target repo."""
        if not repo_path.exists():
            return False, f"CORE repo path does not exist: {repo_path}"
        marker = repo_path / self.REPO_VALIDATION_MARKER
        if not marker.exists():
            return (
                False,
                f"Expected CORE repo marker '{self.REPO_VALIDATION_MARKER}' "
                f"not found in {repo_path}",
            )
        return True, f"CORE repo validated at {repo_path}"

    def governance_block(self) -> Dict[str, Any]:
        return {
            "no_model_execution": True,
            "no_commit_push": True,
            "no_core_workbench_coupling": True,
            "source_checkout_untouched": True,
            "temporary_worktree_requires_explicit_approval": True,
            "adapter_note": self.GOVERNANCE_NOTE,
        }


# ---------------------------------------------------------------------------
# CORE demo loop (uses GenericTargetDemoLoop + CoreDemoAdapter)
# ---------------------------------------------------------------------------


class CoreTargetDemoLoop(GenericTargetDemoLoop):
    """Concrete demo loop for the CORE target profile.

    Uses :class:`CoreDemoAdapter` for all CORE-specific behaviour.
    """

    def __init__(self, adapter: Optional[CoreDemoAdapter] = None) -> None:
        self._adapter = adapter or CoreDemoAdapter()

    def target_governance_block(self) -> Dict[str, Any]:
        return self._adapter.governance_block()

    def build_steps(
        self, ctx: TargetDemoContext
    ) -> Sequence[Tuple[str, Callable[[TargetDemoContext], DemoStepResult]]]:
        adapter = self._adapter
        return [
            ("validate_repo", self._step_validate_repo),
            ("check_governance", self._step_check_governance),
            ("emit_context_artifact", self._step_emit_context_artifact),
        ]

    def _step_validate_repo(
        self, ctx: TargetDemoContext
    ) -> DemoStepResult:
        ok, detail = self._adapter.validate_repo(ctx.target_repo)
        return DemoStepResult(
            step_name="validate_repo",
            passed=ok,
            detail=detail,
        )

    def _step_check_governance(
        self, ctx: TargetDemoContext
    ) -> DemoStepResult:
        block = self._adapter.governance_block()
        all_ok = all(
            v is True
            for k, v in block.items()
            if k != "adapter_note"
        )
        return DemoStepResult(
            step_name="check_governance",
            passed=all_ok,
            detail="Governance block verified" if all_ok else "Governance block incomplete",
        )

    def _step_emit_context_artifact(
        self, ctx: TargetDemoContext
    ) -> DemoStepResult:
        artifact = {
            "target": self._adapter.TARGET_NAME,
            "session_id": ctx.session_id,
            "dry_run": ctx.dry_run,
            "governance": self._adapter.governance_block(),
            "invariant_marker_prefix": self._adapter.INVARIANT_MARKER_PREFIX,
        }
        return DemoStepResult(
            step_name="emit_context_artifact",
            passed=True,
            detail=json.dumps(artifact, default=str),
        )


# ---------------------------------------------------------------------------
# Public entry-point (backward-compatible)
# ---------------------------------------------------------------------------


def run_core_demo_loop(
    target_repo: Optional[Path] = None,
    session_id: Optional[str] = None,
    operator_note: str = "",
    dry_run: bool = True,
    adapter: Optional[CoreDemoAdapter] = None,
) -> DemoLoopResult:
    """Run the CORE target demo loop.

    Public entry-point preserved for backward compatibility.
    All CORE-specific behaviour is encapsulated in CoreDemoAdapter.

    Emits governance:
    - no model execution
    - no commit/push
    - no CORE Workbench coupling
    - source checkout untouched
    - temporary worktree only after explicit approval

    Parameters
    ----------
    target_repo:
        Path to the CORE target repository.  Defaults to the CORE target
        profile default (project_root.parent/core).
    session_id:
        Unique session identifier for artifact tracing.
    operator_note:
        Optional human-readable note embedded in the result artifact.
    dry_run:
        When True (default) no filesystem changes are made.
    adapter:
        Optional CoreDemoAdapter instance.  Defaults to CoreDemoAdapter().
    """
    import uuid
    from builder_ii.target_profile_defaults import default_target_repo_for

    resolved_repo = target_repo or default_target_repo_for("core")
    resolved_session = session_id or str(uuid.uuid4())
    loop = CoreTargetDemoLoop(adapter=adapter)
    ctx = TargetDemoContext(
        target_name="core",
        target_repo=resolved_repo,
        session_id=resolved_session,
        operator_note=operator_note,
        dry_run=dry_run,
    )
    return loop.run(ctx)
