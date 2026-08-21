"""Closed, typed last-mile command seam for STRATUM.

The TUI selects one of five typed requests. It cannot provide an executable,
shell, environment, cwd, timeout, passthrough argument, or arbitrary output
path. Each command owns its canonical validator and invocation bindings.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeAlias
from uuid import uuid4

from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
    validate_deepagents_subagent_assignment,
    validate_deepagents_work_plan,
)
from builder_ii.core.canonical_json import canonical_digest
from builder_ii.core.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    validate_governed_prepare_package_directory,
)
from builder_ii.governance.authority import check_command_authority
from builder_ii.governance.hitl.hitl_patch_approval import (
    HITL_PATCH_APPROVAL_KIND,
    approval_binding_errors,
    approval_is_expired,
    validate_hitl_patch_approval,
)
from builder_ii.governance.hitl.hitl_patch_proposal import validate_hitl_patch_proposal
from builder_ii.governance.hitl.hitl_patch_refusal import (
    HITL_PATCH_REFUSAL_KIND,
    validate_hitl_patch_refusal,
)
from builder_ii.lifecycle.setup.target_profiles import target_names
from builder_ii.routing.agent_profiles import get_agent_profile

_SESSION_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_MAX_TASK = 2_000
_MAX_STDERR = 4_096


@dataclass(frozen=True)
class PreparePackageInputs:
    target: str
    task: str
    output_root: Path
    session_id: str


@dataclass(frozen=True)
class ValidatePackageInputs:
    package: Path
    output_root: Path
    session_id: str


@dataclass(frozen=True)
class AssignSubagentInputs:
    target: str
    task: str
    profile: str
    work_plan: Path
    output_root: Path
    session_id: str


@dataclass(frozen=True)
class HitlPatchInputs:
    proposal: Path
    output_root: Path
    session_id: str


StratumInputs: TypeAlias = PreparePackageInputs | ValidatePackageInputs | AssignSubagentInputs | HitlPatchInputs


@dataclass(frozen=True)
class ValidationResult:
    artifact_kind: str
    artifact_sha256: str
    canonical_digest: str
    errors: tuple[str, ...]


@dataclass(frozen=True)
class StratumCommand:
    identity: str
    entrypoint: str
    argv: tuple[str, ...]
    output: Path
    invocation_dir: Path
    validator: Callable[[Path], ValidationResult]
    authority: str
    creates_output: bool = True
    input_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class InvocationObservation:
    command: str
    session_id: str
    returncode: int | None
    cancelled: bool
    output: Path
    validation_errors: tuple[str, ...]
    artifact_kind: str = ""
    artifact_sha256: str = ""
    canonical_digest: str = ""
    stderr: str = ""
    projection_stage: str = ""
    next_action: str = ""
    observation_path: Path | None = None
    input_paths: tuple[Path, ...] = ()

    @property
    def successful(self) -> bool:
        return self.returncode == 0 and not self.cancelled and not self.validation_errors


def _read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.is_file():
        return None, [f"canonical output does not exist: {path}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"canonical output is not valid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, ["canonical output must be a JSON object"]
    return value, []


def _result(path: Path, kind: str, value: dict[str, Any] | None, errors: list[str]) -> ValidationResult:
    byte_digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    content_digest = canonical_digest(value) if value is not None else ""
    return ValidationResult(kind, byte_digest, content_digest, tuple(errors))


def _package_validator(expected_target: str | None = None) -> Callable[[Path], ValidationResult]:
    def validate(path: Path) -> ValidationResult:
        errors = list(validate_governed_prepare_package_directory(path))
        manifest = path / "prepare-package.json" if path.is_dir() else path
        value, load_errors = _read_json(manifest)
        errors.extend(load_errors)
        if value is not None and expected_target is not None and value.get("target_name") != expected_target:
            errors.append("prepare package target_name does not match the invocation target")
        return _result(manifest, GOVERNED_PREPARE_PACKAGE_KIND, value, errors)

    return validate


def _assignment_validator(inputs: AssignSubagentInputs) -> Callable[[Path], ValidationResult]:
    def validate(path: Path) -> ValidationResult:
        work_plan, work_plan_load_errors = _read_json(inputs.work_plan)
        work_plan_errors = list(work_plan_load_errors)
        if work_plan is not None:
            work_plan_errors.extend(validate_deepagents_work_plan(work_plan))
        value, errors = _read_json(path)
        errors.extend(work_plan_errors)
        if value is not None:
            errors.extend(validate_deepagents_subagent_assignment(value))
            if value.get("target") != inputs.target:
                errors.append("assignment target does not match the invocation target")
            if value.get("task") != inputs.task:
                errors.append("assignment task does not match the invocation task")
            if value.get("subagent_profile") != inputs.profile:
                errors.append("assignment profile does not match the selected canonical profile")
            ref = value.get("work_plan_ref")
            if not isinstance(ref, dict) or work_plan is None:
                errors.append("assignment work_plan_ref cannot be bound to the invocation work plan")
            else:
                if ref.get("sha256") != canonical_digest(work_plan):
                    errors.append("assignment work_plan_ref digest does not match the invocation work plan")
                if Path(str(ref.get("path", ""))).resolve() != inputs.work_plan.resolve():
                    errors.append("assignment work_plan_ref path does not match the invocation work plan")
        return _result(path, DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND, value, errors)

    return validate


def _proposal(inputs: HitlPatchInputs) -> tuple[dict[str, Any] | None, list[str]]:
    value, errors = _read_json(inputs.proposal)
    if value is not None:
        errors.extend(validate_hitl_patch_proposal(value))
    return value, errors


def _approval_validator(inputs: HitlPatchInputs) -> Callable[[Path], ValidationResult]:
    proposal, proposal_errors = _proposal(inputs)
    proposal_digest_at_build = canonical_digest(proposal) if proposal is not None else ""

    def validate(path: Path) -> ValidationResult:
        value, errors = _read_json(path)
        errors.extend(proposal_errors)
        current_proposal, current_errors = _proposal(inputs)
        errors.extend(current_errors)
        if current_proposal is not None and canonical_digest(current_proposal) != proposal_digest_at_build:
            errors.append("invocation proposal bytes changed after command construction")
        if value is not None:
            errors.extend(validate_hitl_patch_approval(value))
            if proposal is not None:
                errors.extend(
                    approval_binding_errors(
                        value,
                        proposal_digest=canonical_digest(proposal),
                        patch_digest=str(proposal.get("patch_digest", "")),
                    )
                )
                if value.get("target") != proposal.get("target"):
                    errors.append("approval target does not match the exact proposal target")
            if approval_is_expired(value, now=int(time.time())):
                errors.append("approval is expired")
        return _result(path, HITL_PATCH_APPROVAL_KIND, value, errors)

    return validate


def _refusal_validator(inputs: HitlPatchInputs) -> Callable[[Path], ValidationResult]:
    proposal, proposal_errors = _proposal(inputs)
    proposal_digest_at_build = canonical_digest(proposal) if proposal is not None else ""

    def validate(path: Path) -> ValidationResult:
        value, errors = _read_json(path)
        errors.extend(proposal_errors)
        current_proposal, current_errors = _proposal(inputs)
        errors.extend(current_errors)
        if current_proposal is not None and canonical_digest(current_proposal) != proposal_digest_at_build:
            errors.append("invocation proposal bytes changed after command construction")
        if value is not None:
            errors.extend(validate_hitl_patch_refusal(value))
            if proposal is not None:
                if value.get("proposal_kind") != proposal.get("kind"):
                    errors.append("refusal proposal_kind does not match the exact proposal")
                if value.get("proposal_digest") != canonical_digest(proposal):
                    errors.append("refusal proposal_digest does not match the exact proposal")
                if value.get("patch_digest") != proposal.get("patch_digest"):
                    errors.append("refusal patch_digest does not match the exact proposal")
                if Path(str(value.get("proposal_path", ""))).resolve() != inputs.proposal.resolve():
                    errors.append("refusal proposal_path does not match the invocation proposal")
        return _result(path, HITL_PATCH_REFUSAL_KIND, value, errors)

    return validate


def _checked_session(value: str) -> str:
    if not value or not _SESSION_RE.fullmatch(value):
        raise ValueError("session_id must use only letters, digits, dot, underscore, colon, or hyphen")
    return value


def _invocation(output_root: Path, session_id: str) -> Path:
    return output_root.resolve() / "stratum" / "sessions" / _checked_session(session_id) / "invocations" / uuid4().hex


def _check_target_task(target: str, task: str) -> None:
    if target not in target_names():
        raise ValueError(f"target must be one of: {', '.join(target_names())}")
    if len(task) > _MAX_TASK:
        raise ValueError(f"task must be at most {_MAX_TASK} characters")


def command_inventory() -> tuple[str, ...]:
    return _COMMANDS


def build_command(identity: str, inputs: StratumInputs) -> StratumCommand:
    if identity not in _COMMANDS:
        raise ValueError(f"STRATUM command is not admitted: {identity}")
    invocation = _invocation(inputs.output_root, inputs.session_id)

    if identity == "builder-session prepare-package" and isinstance(inputs, PreparePackageInputs):
        _check_target_task(inputs.target, inputs.task)
        output = invocation / "package"
        return StratumCommand(
            identity,
            "builder_ii.cli.session_cli",
            ("prepare-package", inputs.target, "--output-dir", str(output), "--task", inputs.task),
            output,
            invocation,
            _package_validator(inputs.target),
            identity,
        )
    if identity == "builder-session validate-prepare-package" and isinstance(inputs, ValidatePackageInputs):
        package = inputs.package.resolve()
        return StratumCommand(
            identity,
            "builder_ii.cli.session_cli",
            ("validate-prepare-package", str(package)),
            package,
            invocation,
            _package_validator(),
            identity,
            creates_output=False,
            input_paths=(package,),
        )
    if identity == "builder-deepagents assign-subagent" and isinstance(inputs, AssignSubagentInputs):
        _check_target_task(inputs.target, inputs.task)
        profile = get_agent_profile(inputs.profile)  # type: ignore[arg-type]
        if inputs.target not in profile.compatible_targets:
            raise ValueError(f"agent profile {inputs.profile} is not compatible with target {inputs.target}")
        output = invocation / "assignment.json"
        return StratumCommand(
            identity,
            "builder_ii.cli.deepagents_cli",
            (
                "assign-subagent",
                "--target",
                inputs.target,
                "--task",
                inputs.task,
                "--subagent-profile",
                inputs.profile,
                "--work-plan",
                str(inputs.work_plan.resolve()),
                "--output",
                str(output),
            ),
            output,
            invocation,
            _assignment_validator(inputs),
            identity,
            input_paths=(inputs.work_plan.resolve(),),
        )
    if identity in {"builder-hitl approve-patch", "builder-hitl refuse-patch"} and isinstance(inputs, HitlPatchInputs):
        output = invocation / ("approval.json" if identity.endswith("approve-patch") else "refusal.json")
        verb = "approve-patch" if identity.endswith("approve-patch") else "refuse-patch"
        validator = _approval_validator(inputs) if verb == "approve-patch" else _refusal_validator(inputs)
        return StratumCommand(
            identity,
            "builder_ii.cli.hitl_execution_cli",
            (verb, "--proposal", str(inputs.proposal.resolve()), "--output", str(output)),
            output,
            invocation,
            validator,
            identity,
            input_paths=(inputs.proposal.resolve(),),
        )
    raise TypeError(f"typed inputs do not match admitted command {identity}")


_COMMANDS = (
    "builder-session prepare-package",
    "builder-session validate-prepare-package",
    "builder-deepagents assign-subagent",
    "builder-hitl approve-patch",
    "builder-hitl refuse-patch",
)


def admit(command: StratumCommand) -> None:
    if command.identity not in _COMMANDS or command.entrypoint not in {
        "builder_ii.cli.session_cli",
        "builder_ii.cli.deepagents_cli",
        "builder_ii.cli.hitl_execution_cli",
    }:
        raise PermissionError("command is not admitted by the STRATUM registry")
    decision = check_command_authority(command.authority)
    if not decision.allowed:
        raise PermissionError("command authority denied: " + ", ".join(decision.reasons))


def bounded_stderr(value: str) -> str:
    cleaned = value.strip()
    return cleaned[-_MAX_STDERR:] if len(cleaned) > _MAX_STDERR else cleaned


def observation_record(observation: InvocationObservation) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": "builder_ii.stratum_invocation_observation",
        "schema_version": 1,
        "command": observation.command,
        "session_id": observation.session_id,
        "returncode": observation.returncode,
        "cancelled": observation.cancelled,
        "successful": observation.successful,
        "output_path": str(observation.output),
        "input_paths": [str(path) for path in observation.input_paths],
        "artifact_kind": observation.artifact_kind,
        "artifact_sha256": observation.artifact_sha256,
        "canonical_digest": observation.canonical_digest,
        "validation_errors": list(observation.validation_errors),
        "stderr": bounded_stderr(observation.stderr),
        "projection_stage": observation.projection_stage,
        "next_action": observation.next_action,
        "artifact_is_authority": False,
        "grants_authority": False,
    }
    record["observation_digest"] = canonical_digest(record)
    return record


def write_observation(observation: InvocationObservation, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(observation_record(observation), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
