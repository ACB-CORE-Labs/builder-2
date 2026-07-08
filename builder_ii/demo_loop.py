"""Governed demo loop for arbitrary generic target repositories (plan item 1.8 / B4.9).

CORE-born, generic-first: the demo proves the governed propose -> approve -> apply -> verify ->
rollback lifecycle against a temporary detached worktree of ANY operator-designated local git
repository. AssetOverflow/core remains one supported target profile (``target_name="core"``),
carrying its original identity check and sensitive-module policy; every other target name runs
under the generic spec.

Boundaries (unchanged from the CORE-only predecessor, ``core_demo_loop.py``):

- the source checkout is never mutated; the demo mutates only a disposable detached worktree;
- the only mutation is one approved temporary documentation marker patch, always rolled back;
- the approval consumed by the apply lane is the generic ``builder_ii.hitl_patch_approval``
  (plan item 1.1) minted in-process at the ``--approve`` gate — the demo loop is the single
  sanctioned in-process minter recorded by ``docs/audits/B4_CLOSURE_AUDIT.md``, contained by the
  disposable worktree plus mandatory auto-rollback and final clean postflight;
- no commit, push, model execution, Goose activation, MCP call, or hidden memory.

The ``builder_ii.demo_verification_receipt`` produced here is the demo-scoped fallback the apply
lane accepts (see ``hitl_patch_apply._verification_receipt_errors``); it self-describes demo scope
and is bound to the exact worktree it verified. Rationale for keeping that fallback is recorded in
``docs/audits/B4_9_DEMO_GENERALIZATION_AUDIT.md``.
"""

from __future__ import annotations

import hashlib
import json as json_lib
import shutil
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from builder_ii.context_packs import create_context_pack, dumps_context_pack
from builder_ii.execution_postflight_records import (
    create_execution_postflight_record,
    write_execution_postflight_record,
)
from builder_ii.hitl_patch_apply import apply_hitl_patch, rollback_hitl_patch
from builder_ii.hitl_patch_approval import (
    APPROVAL_CONFIRMATION_PREFIX_LENGTH,
    create_hitl_patch_approval,
)
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.hitl_rollback_approval import canonical_json_digest, create_hitl_rollback_approval
from builder_ii.repo_map import create_repo_map, dumps_repo_map

DEMO_PLANNER_KIND = "builder_ii.demo_deterministic_planner"
DEMO_PREFLIGHT_KIND = "builder_ii.demo_preflight"
DEMO_VERIFICATION_RECEIPT_KIND = "builder_ii.demo_verification_receipt"
DEMO_REPORT_KIND = "builder_ii.demo_loop_report"
DEMO_REPORT_SCHEMA_VERSION = 1

DEFAULT_DEMO_MARKER_PATH = "docs/builder_ii_demo_marker.md"

# CORE sensitive runtime modules the CORE-profile demo must prove untouched. These are part of the
# CORE target profile, not of the demo mechanism itself.
CORE_SENSITIVE_PATH_PREFIXES = (
    "algebra/",
    "field/",
    "generate/",
    "core/cognition/",
    "vault/",
    "teaching/",
    "calibration/",
    "sensorium/",
)

DemoPhase = Literal[
    "prepare",
    "approve",
    "apply",
    "verify",
    "rollback",
    "finalize",
    "all",
]

_PHASES: tuple[DemoPhase, ...] = (
    "prepare",
    "approve",
    "apply",
    "verify",
    "rollback",
    "finalize",
    "all",
)


@dataclass(frozen=True)
class DemoTargetSpec:
    """Parameterizes the demo loop for one target repository.

    ``name`` is the operator-facing display name recorded in demo-scoped artifacts.
    ``profile_name`` is the governed target profile ("generic" or "core") used wherever the
    demo feeds promoted lanes whose validators pin the target-name vocabulary (repo map,
    context pack, HITL patch proposal, execution postflight).
    """

    name: str
    profile_name: str = "generic"
    marker_path: str = DEFAULT_DEMO_MARKER_PATH
    sensitive_path_prefixes: tuple[str, ...] = ()
    expected_remote_substring: str | None = None
    expected_dirname: str | None = None
    description: str = ""


CORE_DEMO_TARGET_SPEC = DemoTargetSpec(
    name="core",
    profile_name="core",
    sensitive_path_prefixes=CORE_SENSITIVE_PATH_PREFIXES,
    expected_remote_substring="AssetOverflow/core",
    expected_dirname="core",
    description="AssetOverflow/core temporary detached worktree for the builder-II governed demo loop.",
)


def marker_path_errors(marker_path: Any) -> list[str]:
    """Validate the temporary demo marker path shape (relative, no traversal, not .git)."""
    if not isinstance(marker_path, str) or not marker_path.strip():
        return ["marker path must be a non-empty string"]
    errors: list[str] = []
    if "\\" in marker_path:
        errors.append("marker path must use forward slashes")
    if marker_path.startswith("/") or PurePosixPath(marker_path).is_absolute():
        errors.append("marker path must be relative")
    if marker_path.endswith("/"):
        errors.append("marker path must name a file, not a directory")
    parts = PurePosixPath(marker_path).parts
    if ".." in parts:
        errors.append("marker path must not contain traversal segments")
    if parts and parts[0] == ".git":
        errors.append("marker path must not target .git")
    return errors


def validate_demo_target_spec(spec: DemoTargetSpec) -> list[str]:
    errors: list[str] = []
    if not spec.name or not spec.name.strip():
        errors.append("demo target name must be a non-empty string")
    elif any(ch.isspace() for ch in spec.name):
        errors.append("demo target name must not contain whitespace")
    if spec.profile_name not in ("generic", "core"):
        errors.append("demo target profile_name must be generic or core")
    errors.extend(marker_path_errors(spec.marker_path))
    for prefix in spec.sensitive_path_prefixes:
        if spec.marker_path.startswith(prefix):
            errors.append(f"marker path must not fall under sensitive path prefix: {prefix}")
    return errors


def demo_target_spec(target_name: str, *, marker_path: str | None = None) -> DemoTargetSpec:
    """Resolve the demo target spec for a target name.

    ``"core"`` selects the CORE profile (identity check + sensitive-module policy). Any other
    name selects the generic spec with that display name. Fails closed on an invalid spec.
    """
    if target_name == "core":
        spec = CORE_DEMO_TARGET_SPEC
    else:
        spec = DemoTargetSpec(
            name=target_name,
            description=(
                f"Temporary detached worktree of the {target_name} target repo "
                "for the builder-II governed demo loop."
            ),
        )
    if marker_path is not None:
        spec = replace(spec, marker_path=marker_path)
    errors = validate_demo_target_spec(spec)
    if errors:
        raise ValueError("invalid demo target spec: " + "; ".join(errors))
    return spec


@dataclass(frozen=True)
class DemoPaths:
    output_dir: Path

    @property
    def worktree(self) -> Path:
        return self.output_dir / "demo-worktree"

    @property
    def repo_map(self) -> Path:
        return self.output_dir / "repo-map.json"

    @property
    def context_pack(self) -> Path:
        return self.output_dir / "context-pack.json"

    @property
    def planner(self) -> Path:
        return self.output_dir / "deterministic-planner.json"

    @property
    def patch_file(self) -> Path:
        return self.output_dir / "demo.patch"

    @property
    def reverse_patch_file(self) -> Path:
        return self.output_dir / "demo.reverse.patch"

    @property
    def proposal(self) -> Path:
        return self.output_dir / "hitl-patch-proposal.json"

    @property
    def patch_approval(self) -> Path:
        # The generic governed approval (builder_ii.hitl_patch_approval, plan item 1.1) the
        # hardened apply lane validates — bound to the proposal content + patch digests. Minted
        # only at the explicit --approve gate; its absence IS the unapproved state (no separate
        # narrative "rejected approval" artifact exists).
        return self.output_dir / "hitl-patch-approval.json"

    @property
    def rollback_approval(self) -> Path:
        # Distinct governed rollback approval (plan item 1.4). The rollback lane requires
        # its own approval bound to the rollback plan, not just the machine-generated plan.
        return self.output_dir / "hitl-rollback-approval.json"

    @property
    def preflight(self) -> Path:
        return self.output_dir / "preflight.json"

    @property
    def pre_apply_verification_receipt(self) -> Path:
        return self.output_dir / "pre-apply-verification-receipt.json"

    @property
    def post_apply_verification_receipt(self) -> Path:
        return self.output_dir / "post-apply-verification-receipt.json"

    @property
    def patch_apply_dir(self) -> Path:
        return self.output_dir / "patch-apply"

    @property
    def patch_apply_receipt(self) -> Path:
        return self.patch_apply_dir / "patch_apply_receipt.json"

    @property
    def patch_postflight(self) -> Path:
        return self.patch_apply_dir / "postflight_record.json"

    @property
    def rollback_plan(self) -> Path:
        return self.patch_apply_dir / "rollback_plan.json"

    @property
    def generated_reverse_patch_file(self) -> Path:
        return self.patch_apply_dir / "rollback.patch"

    @property
    def rollback_dir(self) -> Path:
        return self.output_dir / "rollback"

    @property
    def rollback_receipt(self) -> Path:
        return self.rollback_dir / "rollback_receipt.json"

    @property
    def final_postflight(self) -> Path:
        return self.output_dir / "final-postflight.json"

    @property
    def chain_report(self) -> Path:
        return self.output_dir / "chain-verification-report.json"

    @property
    def artifact_index(self) -> Path:
        return self.output_dir / "artifact-index.json"

    @property
    def report(self) -> Path:
        return self.output_dir / "demo-loop-report.json"

    @property
    def evidence_md(self) -> Path:
        return self.output_dir / "DEMO_EVIDENCE.md"


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_digest(value: dict[str, Any]) -> str:
    return _sha256_text(json_lib.dumps(value, sort_keys=True, separators=(",", ":")))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _repo_head(repo: Path) -> str:
    return _run_git(repo, ["rev-parse", "HEAD"]).stdout.strip()


def _repo_status(repo: Path) -> list[str]:
    # --untracked-files=all so a marker in a brand-new directory reports the file path itself
    # rather than a collapsed "?? dir/" line; the only-marker-mutated check depends on exact paths.
    result = _run_git(repo, ["status", "--porcelain=v1", "--untracked-files=all"])
    return result.stdout.splitlines()


def _ensure_target_repo(repo: Path, spec: DemoTargetSpec) -> Path:
    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"demo target repo does not exist: {resolved}")
    if not (resolved / ".git").exists():
        raise ValueError(f"demo target repo is not a git checkout: {resolved}")
    if spec.expected_remote_substring is not None or spec.expected_dirname is not None:
        try:
            remote = _run_git(resolved, ["remote", "-v"], check=False).stdout
        except OSError as exc:
            raise ValueError(f"failed to inspect demo target git remote: {exc}") from exc
        remote_ok = spec.expected_remote_substring is not None and spec.expected_remote_substring in remote
        dirname_ok = spec.expected_dirname is not None and resolved.name == spec.expected_dirname
        if not remote_ok and not dirname_ok:
            raise ValueError(f"repo does not look like the {spec.name} target: {resolved}")
    return resolved


def _prepare_worktree(source_repo: Path, worktree: Path, *, force: bool) -> None:
    if worktree.exists():
        if not force:
            raise ValueError(f"worktree path already exists; use --force to replace: {worktree}")
        shutil.rmtree(worktree)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    head = _repo_head(source_repo)
    _run_git(source_repo, ["worktree", "prune"], check=False)
    _run_git(source_repo, ["worktree", "add", "--detach", str(worktree), head])


def _remove_worktree(source_repo: Path, worktree: Path) -> None:
    if not worktree.exists():
        return
    _run_git(source_repo, ["worktree", "remove", "--force", str(worktree)], check=False)


def _marker_lines(spec: DemoTargetSpec) -> list[str]:
    return [
        "# builder-II Demo Marker",
        "",
        f"Target: {spec.name}",
        "",
        (
            "This temporary file is created by the builder-II governed demo loop "
            "and is rolled back before the demo completes."
        ),
    ]


def _unified_diff_for_marker(spec: DemoTargetSpec) -> str:
    lines = _marker_lines(spec)
    body = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{spec.marker_path} b/{spec.marker_path}\n"
        "new file mode 100644\n"
        "index 0000000..0000000\n"
        "--- /dev/null\n"
        f"+++ b/{spec.marker_path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


def _reverse_diff_for_marker(spec: DemoTargetSpec) -> str:
    lines = _marker_lines(spec)
    body = "".join(f"-{line}\n" for line in lines)
    return (
        f"diff --git a/{spec.marker_path} b/{spec.marker_path}\n"
        "deleted file mode 100644\n"
        "index 0000000..0000000\n"
        f"--- a/{spec.marker_path}\n"
        "+++ /dev/null\n"
        f"@@ -1,{len(lines)} +0,0 @@\n"
        f"{body}"
    )


def _write_repo_map_and_context(worktree: Path, paths: DemoPaths, spec: DemoTargetSpec) -> None:
    repo_map = create_repo_map(worktree, target_name=spec.profile_name, max_files=700)
    paths.repo_map.write_text(dumps_repo_map(repo_map), encoding="utf-8")
    context_pack = create_context_pack(
        repo_map,
        target_name=spec.profile_name,
        task=f"Demonstrate the builder-II governed patch, verify, rollback loop on the {spec.name} target.",
        max_entries=80,
    )
    paths.context_pack.write_text(dumps_context_pack(context_pack), encoding="utf-8")


def _write_planner(paths: DemoPaths, worktree: Path, patch_digest: str, spec: DemoTargetSpec) -> dict[str, Any]:
    planner = {
        "kind": DEMO_PLANNER_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "target": {
            "name": spec.name,
            "profile": spec.profile_name,
            "repo": str(worktree),
            "source": f"{spec.name} temporary detached worktree",
        },
        "selected_change": {
            "path": spec.marker_path,
            "operation": "temporary_add_then_rollback",
            "patch_digest": patch_digest,
            "reason": (
                "Use a low-risk documentation marker outside any sensitive target module "
                "to prove the governed lifecycle."
            ),
        },
        "target_invariant_policy": {
            "sensitive_path_prefixes": list(spec.sensitive_path_prefixes),
            "mutation_scope": "single temporary documentation marker file, rolled back before completion",
            "stochastic_generation": "not introduced",
        },
        "governance": {
            "capability_state": "DEMO_PLANNED",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT APPROVED TEMPORARY DEMO WORKTREE PATCH",
            "target_repo_writes": "TEMPORARY_WORKTREE_ONLY_AFTER_APPROVAL",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    _write_json(paths.planner, planner)
    return planner


def _write_patch_proposal(
    paths: DemoPaths, worktree: Path, patch_text: str, patch_digest: str, spec: DemoTargetSpec
) -> dict[str, Any]:
    paths.patch_file.write_text(patch_text, encoding="utf-8")
    paths.reverse_patch_file.write_text(_reverse_diff_for_marker(spec), encoding="utf-8")
    proposal = create_hitl_patch_proposal(
        target_name="generic",
        generic_repo=worktree,
        patch_description=f"Governed demo ({spec.name}): add temporary builder-II demo marker",
        reason=(
            "Prove the governed inspect -> propose -> approve -> apply -> verify -> rollback "
            f"lifecycle on the {spec.name} target without touching sensitive target modules."
        ),
        patch_digest=patch_digest,
        unified_diff=patch_text,
    )
    proposal["target"]["name"] = spec.profile_name
    proposal["target"]["description"] = spec.description
    write_hitl_patch_proposal(proposal, paths.proposal)
    return proposal


def validate_demo_planner(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["demo planner must be a JSON object"]
    if data.get("kind") != DEMO_PLANNER_KIND:
        errors.append(f"kind must be {DEMO_PLANNER_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    target = data.get("target")
    if not isinstance(target, dict) or not target.get("name") or not target.get("repo"):
        errors.append("target must describe the demo target repository")
    policy = data.get("target_invariant_policy")
    sensitive_prefixes: list[str] = []
    if not isinstance(policy, dict) or not isinstance(policy.get("sensitive_path_prefixes"), list):
        errors.append("target_invariant_policy.sensitive_path_prefixes must be a list")
    else:
        sensitive_prefixes = [prefix for prefix in policy["sensitive_path_prefixes"] if isinstance(prefix, str)]
    change = data.get("selected_change")
    if not isinstance(change, dict):
        errors.append("selected_change must be an object")
    else:
        path_errors = marker_path_errors(change.get("path"))
        if path_errors:
            errors.extend(f"selected_change.path: {error}" for error in path_errors)
        else:
            for prefix in sensitive_prefixes:
                if str(change["path"]).startswith(prefix):
                    errors.append(f"selected_change.path must not fall under sensitive path prefix: {prefix}")
        if not isinstance(change.get("patch_digest"), str) or len(change["patch_digest"]) != 64:
            errors.append("selected_change.patch_digest must be a SHA-256 string")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_demo_preflight(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["demo preflight must be a JSON object"]
    if data.get("kind") != DEMO_PREFLIGHT_KIND:
        errors.append(f"kind must be {DEMO_PREFLIGHT_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("source_repo", "demo_worktree", "source_head", "worktree_head"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    if not isinstance(data.get("source_repo_status"), list):
        errors.append("source_repo_status must be a list")
    if data.get("worktree_status") != []:
        errors.append("worktree_status must be empty")
    if data.get("ready") is not True:
        errors.append("ready must be true")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("source_writes") != "DISABLED":
            errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_demo_verification_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["demo verification receipt must be a JSON object"]
    if data.get("kind") != DEMO_VERIFICATION_RECEIPT_KIND:
        errors.append(f"kind must be {DEMO_VERIFICATION_RECEIPT_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("label") not in ("before_apply", "after_apply"):
        errors.append("label must be before_apply or after_apply")
    if data.get("receipt_status") != "EXECUTED":
        errors.append("receipt_status must be EXECUTED")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list")
    elif any(not isinstance(check, dict) or check.get("status") != "PASS" for check in checks):
        errors.append("all checks must be PASS")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED or NOT_AUTHORIZED")
        if governance.get("source_writes") != "DISABLED":
            errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def _write_preflight(paths: DemoPaths, source_repo: Path, worktree: Path) -> dict[str, Any]:
    source_status = _repo_status(source_repo)
    worktree_status = _repo_status(worktree)
    record = {
        "kind": DEMO_PREFLIGHT_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "source_repo": str(source_repo),
        "demo_worktree": str(worktree),
        "source_head": _repo_head(source_repo),
        "worktree_head": _repo_head(worktree),
        "source_repo_status": source_status,
        "worktree_status": worktree_status,
        "ready": len(worktree_status) == 0,
        "source_repo_dirty_ok": True,
        "note": "The source checkout may be dirty; the demo mutates only the detached temporary worktree.",
        "governance": {
            "capability_state": "DEMO_PREFLIGHT",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    _write_json(paths.preflight, record)
    if not record["ready"]:
        raise ValueError(f"demo worktree is not clean: {worktree_status}")
    return record


def _write_verification_receipt(
    paths: DemoPaths, worktree: Path, *, label: str, spec: DemoTargetSpec
) -> dict[str, Any]:
    marker_exists = (worktree / spec.marker_path).is_file()
    expected_marker = label == "after_apply"
    status_lines = _repo_status(worktree)
    checks: list[dict[str, Any]] = [
        {
            "name": "demo_marker_state",
            "expected_exists": expected_marker,
            "observed_exists": marker_exists,
            "status": "PASS" if marker_exists is expected_marker else "FAIL",
        },
        {
            # Strictly stronger than a sensitive-prefix check: the ONLY allowed worktree
            # mutation at any phase is the demo marker itself.
            "name": "only_demo_marker_mutated",
            "status_lines": status_lines,
            "status": "PASS" if all(line[3:] == spec.marker_path for line in status_lines) else "FAIL",
        },
    ]
    if spec.sensitive_path_prefixes:
        checks.append(
            {
                "name": "sensitive_target_modules_untouched",
                "sensitive_path_prefixes": list(spec.sensitive_path_prefixes),
                "status_lines": status_lines,
                "status": "PASS"
                if all(not line[3:].startswith(spec.sensitive_path_prefixes) for line in status_lines)
                else "FAIL",
            }
        )
    receipt_status = "EXECUTED" if all(check["status"] == "PASS" for check in checks) else "FAILED"
    receipt = {
        "kind": DEMO_VERIFICATION_RECEIPT_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "label": label,
        "target": {
            "name": spec.name,
            "profile": spec.profile_name,
            "repo": str(worktree),
        },
        "checks": checks,
        "receipt_status": receipt_status,
        "workspace_mutation_detected": bool(status_lines),
        "status_lines": status_lines,
        "governance": {
            "capability_state": "DEMO_VERIFICATION",
            "runtime_execution": "BOUNDED_IN_PROCESS_CHECKS",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    output = paths.pre_apply_verification_receipt if label == "before_apply" else paths.post_apply_verification_receipt
    _write_json(output, receipt)
    if receipt_status != "EXECUTED":
        failed = [str(check.get("name")) for check in checks if check.get("status") != "PASS"]
        raise ValueError(f"demo verification failed ({label}); failing checks: {', '.join(failed)}")
    return receipt


def _write_final_postflight(paths: DemoPaths, worktree: Path, spec: DemoTargetSpec) -> dict[str, Any]:
    status_lines = _repo_status(worktree)
    postflight = create_execution_postflight_record(
        target_name="generic",
        generic_repo=worktree,
        request_ref=str(paths.proposal),
        receipt_ref=str(paths.rollback_receipt),
        preflight_ref=str(paths.preflight),
        approval_ref=str(paths.patch_approval),
        expected_outcome="Temporary demo patch rolled back; detached worktree returned clean.",
        observed_state_ref="git status --porcelain=v1 --untracked-files=all",
    )
    postflight["target"]["name"] = spec.profile_name
    postflight["target"]["description"] = spec.description
    postflight["postflight_state"] = "RUN_COMPLETE"
    postflight["performed_actions"] = ["read git status for the detached demo worktree"]
    postflight["observed_status_lines"] = status_lines
    postflight["workspace_clean"] = len(status_lines) == 0
    write_execution_postflight_record(postflight, paths.final_postflight)
    if status_lines:
        raise ValueError(f"demo rollback did not return worktree clean: {status_lines}")
    return postflight


def create_demo_report(
    *,
    paths: DemoPaths,
    source_repo: Path,
    worktree: Path,
    spec: DemoTargetSpec,
    phase: DemoPhase,
    completed_steps: list[str],
    chain_report: dict[str, Any] | None,
    artifact_paths: list[Path],
    ready_for_recording: bool,
    next_command: str,
) -> dict[str, Any]:
    refs = []
    for path in artifact_paths:
        if path.is_file() and path.suffix == ".json":
            try:
                data = _read_json(path)
            except Exception:
                continue
            refs.append(
                {
                    "path": str(path),
                    "kind": data.get("kind", ""),
                    "sha256": _json_digest(data),
                }
            )
    report = {
        "kind": DEMO_REPORT_KIND,
        "schema_version": DEMO_REPORT_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "phase": phase,
        "target": {
            "name": spec.name,
            "profile": spec.profile_name,
            "source_repo": str(source_repo),
            "demo_worktree": str(worktree),
        },
        "completed_steps": completed_steps,
        "ready_for_recording": ready_for_recording,
        "next_command": next_command,
        "artifact_refs": refs,
        "chain_verification": {
            "path": str(paths.chain_report),
            "valid": bool(chain_report and chain_report.get("valid")),
            "errors": list(chain_report.get("errors", [])) if isinstance(chain_report, dict) else [],
        },
        "final_state": {
            "source_repo_untouched_by_demo": True,
            "demo_worktree_clean_after_rollback": paths.final_postflight.is_file()
            and not _read_json(paths.final_postflight).get("observed_status_lines"),
        },
        "governance": {
            "capability_state": "GOVERNED_DEMO_LOOP",
            "runtime_execution": "GUIDED_DEMO_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED_FOR_DEMO_PAYLOAD",
            "source_writes": "TEMPORARY_DEMO_WORKTREE_ONLY_AFTER_APPROVAL",
            "commit_push": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    report["report_digest"] = _json_digest(report)
    return report


def validate_demo_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["demo loop report must be a JSON object"]
    if data.get("kind") != DEMO_REPORT_KIND:
        errors.append(f"kind must be {DEMO_REPORT_KIND}")
    if data.get("schema_version") != DEMO_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEMO_REPORT_SCHEMA_VERSION}")
    if data.get("phase") not in _PHASES:
        errors.append("phase must be a known demo phase")
    target = data.get("target")
    if not isinstance(target, dict) or not target.get("name") or not target.get("demo_worktree"):
        errors.append("target must describe the demo target and worktree")
    if not isinstance(data.get("artifact_refs"), list):
        errors.append("artifact_refs must be a list")
    if not isinstance(data.get("ready_for_recording"), bool):
        errors.append("ready_for_recording must be a boolean")
    final_state = data.get("final_state")
    if not isinstance(final_state, dict):
        errors.append("final_state must be an object")
    else:
        if final_state.get("source_repo_untouched_by_demo") is not True:
            errors.append("final_state.source_repo_untouched_by_demo must be true")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED or NOT_AUTHORIZED")
        if governance.get("commit_push") != "DISABLED":
            errors.append("governance.commit_push must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    digest = data.get("report_digest")
    if isinstance(digest, str):
        clone = dict(data)
        clone.pop("report_digest", None)
        if _json_digest(clone) != digest:
            errors.append("report_digest does not match canonical content")
    else:
        errors.append("report_digest is required")
    return errors


def verify_demo_report_artifact_refs(data: Any) -> list[str]:
    """Re-verify every artifact_refs digest against the file on disk (tamper evidence).

    The demo report records the canonical-JSON sha256 of each evidence artifact at finalize
    time. Recomputing those digests here means any post-hoc edit to a receipt, approval, or
    other evidence file is named explicitly instead of passing silently — the report alone
    proves nothing about files it no longer matches.
    """
    if not isinstance(data, dict) or not isinstance(data.get("artifact_refs"), list):
        return ["artifact_refs must be a list"]
    errors: list[str] = []
    for ref in data["artifact_refs"]:
        if not isinstance(ref, dict) or not ref.get("path"):
            errors.append("artifact_refs entries must be objects with a path")
            continue
        path = Path(str(ref["path"]))
        if not path.is_file():
            errors.append(f"referenced evidence artifact is missing: {path}")
            continue
        try:
            content = _read_json(path)
        except Exception:
            errors.append(f"referenced evidence artifact is not valid JSON: {path}")
            continue
        if _json_digest(content) != ref.get("sha256"):
            errors.append(f"evidence artifact content does not match its recorded sha256: {path}")
    return errors


def _write_evidence_markdown(paths: DemoPaths, report: dict[str, Any], spec: DemoTargetSpec) -> None:
    lines = [
        "# builder-II Governed Demo Evidence",
        "",
        (
            "This evidence bundle records a guided builder-II run against a temporary detached "
            f"worktree of the {spec.name} target repository."
        ),
        "",
        "## Boundary",
        "",
        "- The source checkout is not mutated by the demo.",
        "- The temporary demo worktree is patched only after explicit approval.",
        "- The patch is rolled back before completion.",
        "- No commit, push, model execution, Goose activation, MCP call, or hidden memory is used.",
        "",
        "## Artifact Chain",
        "",
    ]
    for ref in report.get("artifact_refs", []):
        path = ref["path"]
        lines.append(f"- `{ref['kind']}`: `{path}` (`{ref['sha256']}`)")
    lines.extend(
        [
            "",
            "## Recording Beats",
            "",
            "1. Show preflight and the detached demo worktree boundary.",
            "2. Show deterministic planner and HITL patch proposal.",
            "3. Show explicit approval digest.",
            "4. Apply the patch, verify the temporary marker exists, then roll it back.",
            "5. Show final postflight, artifact index, chain verification, and clean worktree proof.",
            "",
            f"Report digest: `{report.get('report_digest', '')}`",
            "",
        ]
    )
    paths.evidence_md.write_text("\n".join(lines), encoding="utf-8")


def _artifact_paths_for_chain(paths: DemoPaths) -> list[Path]:
    candidates = [
        paths.preflight,
        paths.repo_map,
        paths.context_pack,
        paths.planner,
        paths.proposal,
        paths.patch_approval,
        paths.rollback_approval,
        paths.pre_apply_verification_receipt,
        paths.post_apply_verification_receipt,
        paths.rollback_plan,
        paths.patch_apply_receipt,
        paths.patch_postflight,
        paths.rollback_receipt,
        paths.final_postflight,
    ]
    return [path for path in candidates if path.is_file()]


def _is_demo_artifact_path(path: Path, paths: DemoPaths) -> bool:
    resolved = path.resolve()
    return resolved.is_file() and not resolved.is_relative_to(paths.worktree.resolve())


def _demo_json_artifact_paths(paths: DemoPaths) -> list[Path]:
    return sorted(
        path
        for path in paths.output_dir.rglob("*.json")
        if _is_demo_artifact_path(path, paths) and path.resolve() != paths.report.resolve()
    )


def _clear_stale_final_outputs(paths: DemoPaths) -> None:
    for path in (paths.report, paths.artifact_index, paths.evidence_md):
        if path.exists():
            path.unlink()


def _finalize(
    paths: DemoPaths,
    source_repo: Path,
    worktree: Path,
    spec: DemoTargetSpec,
    phase: DemoPhase,
    completed_steps: list[str],
) -> dict[str, Any]:
    from builder_ii.artifact_chain_verification import verify_artifact_chain
    from builder_ii.artifact_index_records import create_artifact_index_record, write_artifact_index_record

    _clear_stale_final_outputs(paths)
    chain_paths = _artifact_paths_for_chain(paths)
    chain_report = verify_artifact_chain(chain_paths)
    _write_json(paths.chain_report, chain_report)
    index = create_artifact_index_record(paths.output_dir, recursive=True, exclude_paths=(paths.worktree,))
    write_artifact_index_record(index, paths.artifact_index)
    all_artifacts = _demo_json_artifact_paths(paths)
    report = create_demo_report(
        paths=paths,
        source_repo=source_repo,
        worktree=worktree,
        spec=spec,
        phase=phase,
        completed_steps=completed_steps,
        chain_report=chain_report,
        artifact_paths=all_artifacts,
        ready_for_recording=True,
        next_command="Demo loop complete. Open DEMO_EVIDENCE.md and demo-loop-report.json.",
    )
    errors = validate_demo_report(report)
    if errors:
        raise ValueError("invalid demo report: " + "; ".join(errors))
    _write_json(paths.report, report)
    _write_evidence_markdown(paths, report, spec)
    return report


def run_demo_loop(
    *,
    target_repo: Path,
    output_dir: Path,
    target_name: str = "generic",
    marker_path: str | None = None,
    phase: DemoPhase = "all",
    approve: bool = False,
    force: bool = False,
    cleanup_worktree: bool = False,
) -> dict[str, Any]:
    if phase not in _PHASES:
        raise ValueError(f"phase must be one of: {', '.join(_PHASES)}")

    spec = demo_target_spec(target_name, marker_path=marker_path)
    source_repo = _ensure_target_repo(target_repo, spec)
    paths = DemoPaths(output_dir.resolve())
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    completed: list[str] = []

    if phase in ("prepare", "all"):
        _prepare_worktree(source_repo, paths.worktree, force=force)
        _write_preflight(paths, source_repo, paths.worktree)
        _write_repo_map_and_context(paths.worktree, paths, spec)
        patch_text = _unified_diff_for_marker(spec)
        patch_digest = _sha256_text(patch_text)
        _write_planner(paths, paths.worktree, patch_digest, spec)
        _write_patch_proposal(paths, paths.worktree, patch_text, patch_digest, spec)
        completed.extend(
            [
                "temporary demo worktree created",
                "preflight recorded",
                "repo map and context pack emitted",
                "HITL patch proposal emitted",
            ]
        )
        if phase == "prepare" and not approve:
            marker_option = "" if spec.marker_path == DEFAULT_DEMO_MARKER_PATH else f" --marker-path {spec.marker_path}"
            report = create_demo_report(
                paths=paths,
                source_repo=source_repo,
                worktree=paths.worktree,
                spec=spec,
                phase=phase,
                completed_steps=completed,
                chain_report=None,
                artifact_paths=[paths.preflight, paths.repo_map, paths.context_pack, paths.planner, paths.proposal],
                ready_for_recording=True,
                next_command=(
                    "builder-platform demo-loop --phase approve "
                    f"--target-repo {source_repo} --target-name {spec.name}{marker_option} "
                    f"--output-dir {paths.output_dir} --approve"
                ),
            )
            _write_json(paths.report, report)
            _write_evidence_markdown(paths, report, spec)
            return report

    if phase in ("approve", "all"):
        if not paths.proposal.is_file():
            raise ValueError("prepare phase must run before approval")
        if not approve:
            # No approval artifact is minted on the unapproved path. The absence of a valid
            # builder_ii.hitl_patch_approval IS the unapproved state; a narrative "rejected
            # approval" record would blur planned != approved.
            report = create_demo_report(
                paths=paths,
                source_repo=source_repo,
                worktree=paths.worktree,
                spec=spec,
                phase=phase,
                completed_steps=completed,
                chain_report=None,
                artifact_paths=[paths.proposal],
                ready_for_recording=True,
                next_command=(
                    "Approval checkpoint reached; no approval artifact was minted. "
                    "Rerun with --approve to authorize the temporary demo worktree patch."
                ),
            )
            _write_json(paths.report, report)
            _write_evidence_markdown(paths, report, spec)
            return report
        # Mint the generic governed approval (builder_ii.hitl_patch_approval) the hardened
        # apply lane requires, bound to this exact on-disk proposal. The --approve flag is the
        # human decision; this is the machine-checkable, proposal-bound authorization artifact.
        # This in-process mint is the single sanctioned one recorded by the B4 closure audit,
        # contained by the disposable detached worktree + mandatory auto-rollback.
        proposal = _read_json(paths.proposal)
        patch_approval = create_hitl_patch_approval(
            proposal,
            confirmed_digest_prefix=str(proposal.get("patch_digest", ""))[:APPROVAL_CONFIRMATION_PREFIX_LENGTH],
            approved_by="demo-operator",
        )
        _write_json(paths.patch_approval, patch_approval)
        completed.append("governed patch approval minted (builder_ii.hitl_patch_approval)")

    if phase in ("apply", "all"):
        if not paths.patch_approval.is_file():
            raise ValueError("approval phase must run before apply (no hitl_patch_approval found)")
        if not paths.pre_apply_verification_receipt.is_file():
            _write_verification_receipt(paths, paths.worktree, label="before_apply", spec=spec)
        apply_hitl_patch(
            proposal_path=paths.proposal,
            approval_path=paths.patch_approval,
            verification_receipt_path=paths.pre_apply_verification_receipt,
            output_dir=paths.patch_apply_dir,
        )
        completed.append("approved patch applied to temporary demo worktree")

    if phase in ("verify", "all"):
        _write_verification_receipt(paths, paths.worktree, label="after_apply", spec=spec)
        completed.append("post-apply verification receipt emitted")

    if phase in ("rollback", "all"):
        # Mint the distinct governed rollback approval the hardened rollback lane requires,
        # bound to this exact rollback plan. Same pattern as the apply-side patch_approval: a
        # machine-checkable, plan-bound authorization artifact minted at the boundary.
        rollback_plan_for_approval = _read_json(paths.rollback_plan)
        rollback_approval = create_hitl_rollback_approval(
            rollback_plan_for_approval,
            confirmed_digest_prefix=canonical_json_digest(rollback_plan_for_approval)[
                :APPROVAL_CONFIRMATION_PREFIX_LENGTH
            ],
            approved_by="demo-operator",
        )
        _write_json(paths.rollback_approval, rollback_approval)
        rollback_hitl_patch(
            rollback_plan_path=paths.rollback_plan,
            reverse_patch_path=paths.generated_reverse_patch_file,
            output_dir=paths.rollback_dir,
            approval_path=paths.rollback_approval,
        )
        _write_final_postflight(paths, paths.worktree, spec)
        completed.append("rollback executed and final clean postflight recorded")

    if phase in ("finalize", "all"):
        report = _finalize(paths, source_repo, paths.worktree, spec, phase, completed)
        if cleanup_worktree:
            _remove_worktree(source_repo, paths.worktree)
        return report

    report = create_demo_report(
        paths=paths,
        source_repo=source_repo,
        worktree=paths.worktree,
        spec=spec,
        phase=phase,
        completed_steps=completed,
        chain_report=None,
        artifact_paths=_demo_json_artifact_paths(paths),
        ready_for_recording=True,
        next_command="Run the next demo phase explicitly.",
    )
    _write_json(paths.report, report)
    _write_evidence_markdown(paths, report, spec)
    return report


def dumps_demo_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"
