"""Digest-bound, least-authority GitHub delivery for Plan Set 6.

This module deliberately keeps planning, approval, execution, and receipts as
separate records.  It is the only owner of Git/GitHub delivery effects; CLI and
MCP surfaces must provide validated records to this service rather than
reimplementing subprocess policy.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
)

DELIVERY_PLAN_KIND = "builder_ii.delivery_plan"
DELIVERY_ACTION_REQUEST_KIND = "builder_ii.delivery_action_request"
DELIVERY_APPROVAL_KIND = "builder_ii.delivery_approval"
DELIVERY_RECEIPT_KIND = "builder_ii.delivery_receipt"
DELIVERY_SCHEMA_VERSION = 1
DELIVERY_ACTIONS = ("commit", "push", "pr_create", "pr_update")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

_ACTION_BINDINGS: dict[str, dict[str, type]] = {
    "commit": {
        "expected_head": str,
        "expected_tree": str,
        "expected_branch": str,
        "expected_paths": list,
        "expected_diff_digest": str,
        "remote_name": str,
        "remote_url": str,
    },
    "push": {
        "commit_receipt_digest": str,
        "commit_sha": str,
        "commit_tree": str,
        "verification_receipt_digest": str,
        "branch": str,
        "remote_name": str,
        "remote_url": str,
        "expected_remote_head": str,
    },
    "pr_create": {
        "push_receipt_digest": str,
        "hosted_head_sha": str,
        "head_branch": str,
        "base_branch": str,
        "expected_base_sha": str,
        "expected_state": str,
        "title": str,
        "body": str,
        "draft": bool,
    },
    "pr_update": {
        "push_receipt_digest": str,
        "hosted_head_sha": str,
        "head_branch": str,
        "base_branch": str,
        "expected_base_sha": str,
        "expected_state": str,
        "title": str,
        "body": str,
        "draft": bool,
        "pr_number": int,
    },
}


class DeliveryError(ValueError):
    """A fail-closed delivery validation or execution error."""


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _copy_without_digest(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    result.pop(key, None)
    return result


def _governance(capability: str) -> dict[str, Any]:
    return {
        "capability_state": capability,
        "artifact_is_authority": False,
        "grants_action_authority": False,
        "grants_runtime_authority": False,
        "source_writes": "DISABLED",
        "network_mutation": "DISABLED",
        "generic_shell": "UNREACHABLE",
    }


def _required_string(data: dict[str, Any], key: str, errors: list[str]) -> None:
    if not isinstance(data.get(key), str) or not data[key].strip():
        errors.append(f"{key} must be a non-empty string")


def make_delivery_plan(**fields: Any) -> dict[str, Any]:
    """Build and finalize a static pre-commit delivery plan."""
    plan = {
        "kind": DELIVERY_PLAN_KIND,
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "target": fields.get("target", "generic"),
        "target_repo": str(fields.get("target_repo", Path.cwd())),
        "repository_identity": fields.get("repository_identity", {}),
        "remote_name": fields.get("remote_name", "origin"),
        "remote_url": fields.get("remote_url", ""),
        "feature_branch": fields.get("feature_branch", ""),
        "base_branch": fields.get("base_branch", "main"),
        "base_revision": fields.get("base_revision", ""),
        "pre_commit_head": fields.get("pre_commit_head", ""),
        "expected_paths": sorted(fields.get("expected_paths", [])),
        "expected_diff_digest": fields.get("expected_diff_digest", ""),
        "expected_content_digest": fields.get("expected_content_digest", ""),
        "expected_post_commit_tree": fields.get("expected_post_commit_tree", ""),
        "commit_message": fields.get("commit_message", ""),
        "pr_head_branch": fields.get("pr_head_branch", fields.get("feature_branch", "")),
        "pr_base_branch": fields.get("pr_base_branch", fields.get("base_branch", "main")),
        "pr_title": fields.get("pr_title", ""),
        "pr_body": fields.get("pr_body", ""),
        "draft": bool(fields.get("draft", False)),
        "verification_profile": fields.get("verification_profile", {}),
        "denied_operations": list(fields.get("denied_operations", [])),
        "artifact_is_authority": False,
        "governance": _governance("delivery_plan"),
    }
    plan["plan_digest"] = canonical_digest(plan)
    return plan


def validate_delivery_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["delivery plan must be an object"]
    if data.get("kind") != DELIVERY_PLAN_KIND:
        errors.append(f"kind must be {DELIVERY_PLAN_KIND}")
    if data.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    for key in (
        "target_repo",
        "remote_name",
        "remote_url",
        "feature_branch",
        "base_branch",
        "base_revision",
        "pre_commit_head",
        "commit_message",
    ):
        _required_string(data, key, errors)
    if data.get("feature_branch") == "main":
        errors.append("feature_branch may not be main")
    if not isinstance(data.get("expected_paths"), list) or any(
        not isinstance(x, str) or not x for x in data.get("expected_paths", [])
    ):
        errors.append("expected_paths must be a list of non-empty strings")
    for key in ("expected_diff_digest", "expected_content_digest"):
        if not isinstance(data.get(key), str) or not _DIGEST.fullmatch(data[key]):
            errors.append(f"{key} must be a 64-character hex digest")
    if data.get("expected_post_commit_tree") and not _SHA.fullmatch(str(data["expected_post_commit_tree"])):
        errors.append("expected_post_commit_tree must be a 40-character hex SHA when supplied")
    if not isinstance(data.get("artifact_is_authority"), bool) or data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("plan_digest") != canonical_digest(_copy_without_digest(data, "plan_digest")):
        errors.append("plan_digest does not match canonical plan content")
    governance = data.get("governance")
    if not isinstance(governance, dict) or governance.get("artifact_is_authority") is not False:
        errors.append("governance must deny authority")
    return errors


def make_action_request(plan: dict[str, Any], action: str, **bindings: Any) -> dict[str, Any]:
    if action not in DELIVERY_ACTIONS:
        raise DeliveryError(f"unsupported delivery action: {action}")
    errors = validate_delivery_plan(plan)
    if errors:
        raise DeliveryError("invalid delivery plan: " + "; ".join(errors))
    request = {
        "kind": DELIVERY_ACTION_REQUEST_KIND,
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "action": action,
        "plan_digest": plan["plan_digest"],
        "target_repo": plan["target_repo"],
        "feature_branch": plan["feature_branch"],
        "remote_name": plan["remote_name"],
        "remote_url": plan["remote_url"],
        "bindings": dict(bindings),
        "artifact_is_authority": False,
        "governance": _governance("delivery_action_request"),
    }
    request["action_request_digest"] = canonical_digest(request)
    return request


def validate_delivery_action_request(data: Any, plan: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["delivery action request must be an object"]
    if data.get("kind") != DELIVERY_ACTION_REQUEST_KIND:
        errors.append(f"kind must be {DELIVERY_ACTION_REQUEST_KIND}")
    if data.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if data.get("action") not in DELIVERY_ACTIONS:
        errors.append("action is unsupported")
    for key in ("plan_digest", "action_request_digest"):
        if not isinstance(data.get(key), str) or not _DIGEST.fullmatch(data[key]):
            errors.append(f"{key} must be a 64-character hex digest")
    if data.get("action_request_digest") != canonical_digest(_copy_without_digest(data, "action_request_digest")):
        errors.append("action_request_digest does not match canonical content")
    if plan is not None and data.get("plan_digest") != plan.get("plan_digest"):
        errors.append("action request is bound to a different plan")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    action = data.get("action")
    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("bindings must be an object")
    elif action in _ACTION_BINDINGS:
        required = _ACTION_BINDINGS[action]
        missing = sorted(set(required) - set(bindings))
        extras = sorted(set(bindings) - set(required))
        if missing:
            errors.append(f"{action} bindings missing required keys: {', '.join(missing)}")
        if extras:
            errors.append(f"{action} bindings contain unsupported keys: {', '.join(extras)}")
        for key, expected_type in required.items():
            value = bindings.get(key)
            if expected_type is bool:
                if not isinstance(value, bool):
                    errors.append(f"bindings.{key} must be a boolean")
            elif expected_type is int:
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    errors.append(f"bindings.{key} must be a positive integer")
            elif expected_type is list:
                if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
                    errors.append(f"bindings.{key} must be a list of non-empty strings")
            elif not isinstance(value, str) or (key != "expected_remote_head" and not value):
                errors.append(f"bindings.{key} must be a non-empty string")
        for key in (
            "expected_head",
            "expected_tree",
            "commit_sha",
            "commit_tree",
            "hosted_head_sha",
            "expected_base_sha",
        ):
            if key in bindings and (not isinstance(bindings[key], str) or not _SHA.fullmatch(bindings[key])):
                errors.append(f"bindings.{key} must be a 40-character hex SHA")
        for key in (
            "commit_receipt_digest",
            "verification_receipt_digest",
            "push_receipt_digest",
            "expected_diff_digest",
        ):
            if key in bindings and (not isinstance(bindings[key], str) or not _DIGEST.fullmatch(bindings[key])):
                errors.append(f"bindings.{key} must be a 64-character hex digest")
        if (
            "expected_remote_head" in bindings
            and bindings["expected_remote_head"]
            and not _SHA.fullmatch(bindings["expected_remote_head"])
        ):
            errors.append("bindings.expected_remote_head must be empty or a 40-character hex SHA")
        if bindings.get("expected_state") not in (None, "OPEN"):
            errors.append("bindings.expected_state must be OPEN")
    if plan is not None and isinstance(bindings, dict) and action in _ACTION_BINDINGS:
        expected_from_plan = {
            "commit": {
                "expected_head": plan.get("pre_commit_head"),
                "expected_branch": plan.get("feature_branch"),
                "expected_paths": sorted(plan.get("expected_paths", [])),
                "expected_diff_digest": plan.get("expected_diff_digest"),
                "remote_name": plan.get("remote_name"),
                "remote_url": plan.get("remote_url"),
            },
            "push": {
                "branch": plan.get("feature_branch"),
                "remote_name": plan.get("remote_name"),
                "remote_url": plan.get("remote_url"),
            },
            "pr_create": {
                "head_branch": plan.get("pr_head_branch"),
                "base_branch": plan.get("pr_base_branch"),
                "title": plan.get("pr_title"),
                "body": plan.get("pr_body"),
                "draft": plan.get("draft"),
            },
            "pr_update": {
                "head_branch": plan.get("pr_head_branch"),
                "base_branch": plan.get("pr_base_branch"),
                "title": plan.get("pr_title"),
                "body": plan.get("pr_body"),
                "draft": plan.get("draft"),
            },
        }[action]
        for key, expected in expected_from_plan.items():
            actual = (
                sorted(bindings.get(key, []))
                if key == "expected_paths" and isinstance(bindings.get(key), list)
                else bindings.get(key)
            )
            if actual != expected:
                errors.append(f"bindings.{key} does not match delivery plan")
    return errors


def make_delivery_approval(
    request: dict[str, Any], *, approved_by: str, approved_at: int | None = None, ttl_seconds: int = 86_400
) -> dict[str, Any]:
    errors = validate_delivery_action_request(request)
    if errors:
        raise DeliveryError("invalid action request: " + "; ".join(errors))
    now = int(time.time()) if approved_at is None else approved_at
    approval = {
        "kind": DELIVERY_APPROVAL_KIND,
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "action": request["action"],
        "action_request_digest": request["action_request_digest"],
        "approved_by": approved_by,
        "approved_at": now,
        "expires_at": now + int(ttl_seconds),
        "artifact_is_authority": False,
        "governance": _governance("delivery_approval"),
    }
    approval["approval_digest"] = canonical_digest(approval)
    return approval


def validate_delivery_approval(
    data: Any, request: dict[str, Any] | None = None, *, now: int | None = None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["delivery approval must be an object"]
    if data.get("kind") != DELIVERY_APPROVAL_KIND:
        errors.append(f"kind must be {DELIVERY_APPROVAL_KIND}")
    if data.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if data.get("action") not in DELIVERY_ACTIONS:
        errors.append("action is unsupported")
    if not isinstance(data.get("approved_by"), str) or not data["approved_by"].strip():
        errors.append("approved_by is required")
    if not isinstance(data.get("approved_at"), int) or isinstance(data.get("approved_at"), bool):
        errors.append("approved_at must be an integer")
    if (
        not isinstance(data.get("expires_at"), int)
        or isinstance(data.get("expires_at"), bool)
        or data.get("expires_at", 0) <= data.get("approved_at", 0)
    ):
        errors.append("expires_at must be an integer after approved_at")
    if now is not None and isinstance(data.get("expires_at"), int) and now > data["expires_at"]:
        errors.append("approval is expired")
    if request is not None:
        if data.get("action_request_digest") != request.get("action_request_digest"):
            errors.append("approval is bound to a different action request")
        if data.get("action") != request.get("action"):
            errors.append("approval action does not match action request")
    if data.get("approval_digest") != canonical_digest(_copy_without_digest(data, "approval_digest")):
        errors.append("approval_digest does not match canonical content")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    return errors


def make_delivery_receipt(
    action: str,
    *,
    status: str,
    request: dict[str, Any],
    approval: dict[str, Any],
    result: dict[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    receipt = {
        "kind": DELIVERY_RECEIPT_KIND,
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "action": action,
        "status": status,
        "action_request_digest": request.get("action_request_digest"),
        "approval_digest": approval.get("approval_digest"),
        "result": result,
        "error": error,
        "recovery": "Create a new exact action request and human approval; published history must not be rewritten."
        if status != "SUCCEEDED"
        else "",
        "artifact_is_authority": False,
        "governance": _governance("delivery_receipt"),
    }
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def validate_delivery_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["delivery receipt must be an object"]
    if data.get("kind") != DELIVERY_RECEIPT_KIND:
        errors.append(f"kind must be {DELIVERY_RECEIPT_KIND}")
    if data.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if data.get("action") not in DELIVERY_ACTIONS:
        errors.append("action is unsupported")
    if data.get("status") not in ("SUCCEEDED", "FAILED", "REFUSED"):
        errors.append("status must be SUCCEEDED, FAILED, or REFUSED")
    for key in ("action_request_digest", "approval_digest", "receipt_digest"):
        if not isinstance(data.get(key), str) or not _DIGEST.fullmatch(data[key]):
            errors.append(f"{key} must be a 64-character hex digest")
    if data.get("receipt_digest") != canonical_digest(_copy_without_digest(data, "receipt_digest")):
        errors.append("receipt_digest does not match canonical content")
    if not isinstance(data.get("result"), dict):
        errors.append("result must be an object")
    if data.get("status") != "SUCCEEDED" and not data.get("recovery"):
        errors.append("failed receipts require recovery guidance")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    return errors


def _run(repo: Path, argv: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not argv or any(not isinstance(part, str) or not part for part in argv):
        raise DeliveryError("fixed argv must contain non-empty strings")
    try:
        result = subprocess.run(
            list(argv), cwd=repo, check=False, capture_output=True, text=True, shell=False, env=os.environ.copy()
        )
    except OSError as exc:
        raise DeliveryError(f"command failed to start: {exc}") from exc
    if check and result.returncode:
        raise DeliveryError(f"{argv[0]} failed with exit code {result.returncode}: {result.stderr[-1000:]}")
    return result


def _git(repo: Path, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(repo, ("git", *argv), check=check)


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _tree(repo: Path, ref: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{ref}^{{tree}}").stdout.strip()


def _status(repo: Path) -> list[str]:
    return _git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()


def _diff_digest(repo: Path, *, cached: bool = False) -> str:
    if not cached:
        entries = []
        for line in _status(repo):
            if len(line) < 4:
                continue
            code, path = line[:2].strip(), line[3:]
            if code == "??":
                code = "A"
            file_path = repo / path
            entries.append(
                {"code": code, "path": path, "content": file_path.read_bytes().hex() if file_path.is_file() else None}
            )
    else:
        raw = _git(repo, "diff", "--cached", "--name-status", "-z").stdout
        parts = raw.split("\0")
        entries = []
        index = 0
        while index < len(parts) and parts[index]:
            status = parts[index]
            path = parts[index + 1] if index + 1 < len(parts) else ""
            index += 2
            if status.startswith("A"):
                status = "A"
            elif status.startswith("M"):
                status = "M"
            try:
                content = _git(repo, "show", f":{path}").stdout.encode().hex()
            except DeliveryError:
                content = None
            entries.append({"code": status, "path": path, "content": content})
    return canonical_digest(entries)


def _remote(repo: Path, name: str) -> str:
    return _git(repo, "config", "--get", f"remote.{name}.url").stdout.strip()


def _check_approval(request: dict[str, Any], approval: dict[str, Any]) -> None:
    errors = validate_delivery_action_request(request)
    errors.extend(validate_delivery_approval(approval, request, now=int(time.time())))
    if errors:
        raise DeliveryError("approval refused: " + "; ".join(errors))


def _check_request(plan: dict[str, Any], request: dict[str, Any], action: str) -> dict[str, Any]:
    errors = validate_delivery_action_request(request, plan)
    if request.get("action") != action:
        errors.append(f"action request must be {action}")
    if errors:
        raise DeliveryError("action request refused: " + "; ".join(errors))
    return request["bindings"]


def _successful_delivery_receipt(receipt: dict[str, Any], action: str) -> bool:
    return (
        not validate_delivery_receipt(receipt)
        and receipt.get("action") == action
        and receipt.get("status") == "SUCCEEDED"
    )


class DeliveryService:
    """The sole effect owner for exact commit, push, and PR operations."""

    def __init__(self, repo: Path):
        self.repo = repo.resolve()

    def execute_commit(self, plan: dict[str, Any], request: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
        bindings = _check_request(plan, request, "commit")
        _check_approval(request, approval)
        errors = validate_delivery_plan(plan)
        if errors:
            raise DeliveryError("plan refused: " + "; ".join(errors))
        try:
            branch = _git(self.repo, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
            head = _head(self.repo)
            if head != bindings["expected_head"] or _tree(self.repo) != bindings["expected_tree"]:
                raise DeliveryError("commit refused: request HEAD/tree binding drifted")
            if branch != plan["feature_branch"] or branch == "main":
                raise DeliveryError("commit refused: wrong branch or direct main commit")
            if head != plan["pre_commit_head"]:
                raise DeliveryError("commit refused: HEAD moved since plan")
            if _remote(self.repo, plan["remote_name"]) != plan["remote_url"]:
                raise DeliveryError("commit refused: remote identity mismatch")
            status = _status(self.repo)
            paths = sorted(line[3:] for line in status if len(line) >= 4)
            if paths != sorted(plan["expected_paths"]):
                raise DeliveryError(f"commit refused: unexpected dirty paths {paths}")
            if _diff_digest(self.repo) != plan["expected_diff_digest"]:
                raise DeliveryError("commit refused: working-tree diff digest changed")
            _git(self.repo, "add", "--", *sorted(plan["expected_paths"]))
            if _diff_digest(self.repo, cached=True) != plan["expected_diff_digest"]:
                raise DeliveryError("commit refused: staged tree does not equal plan")
            _git(self.repo, "commit", "--no-verify", "-m", plan["commit_message"])
            commit = _head(self.repo)
            tree = _tree(self.repo)
            if plan.get("expected_post_commit_tree") and tree != plan["expected_post_commit_tree"]:
                raise DeliveryError("commit failed: resulting tree does not equal plan")
            return make_delivery_receipt(
                "commit",
                status="SUCCEEDED",
                request=request,
                approval=approval,
                result={"commit_sha": commit, "tree": tree, "parent": head, "branch": branch},
            )
        except DeliveryError as exc:
            return make_delivery_receipt(
                "commit",
                status="REFUSED",
                request=request,
                approval=approval,
                result={"branch": _git(self.repo, "branch", "--show-current", check=False).stdout.strip()},
                error=str(exc),
            )

    def execute_push(
        self,
        plan: dict[str, Any],
        request: dict[str, Any],
        approval: dict[str, Any],
        *,
        commit_receipt: dict[str, Any] | None = None,
        verification_plan: dict[str, Any] | None = None,
        verification_approval: dict[str, Any] | None = None,
        verification_receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        bindings = _check_request(plan, request, "push")
        _check_approval(request, approval)
        if not isinstance(commit_receipt, dict) or not _successful_delivery_receipt(commit_receipt, "commit"):
            raise DeliveryError("push refused: exact successful commit receipt required")
        if commit_receipt.get("receipt_digest") != bindings["commit_receipt_digest"]:
            raise DeliveryError("push refused: commit receipt digest substitution")
        if (
            not isinstance(verification_plan, dict)
            or not isinstance(verification_approval, dict)
            or not isinstance(verification_receipt, dict)
        ):
            raise DeliveryError("push refused: canonical verification plan, approval, and receipt are required")
        verification_errors = validate_verification_execution_receipt_artifact(verification_receipt)
        verification_errors.extend(
            validate_verification_execution_receipt_against_plan_and_approval(
                verification_receipt, verification_plan, verification_approval
            )
        )
        if verification_errors:
            raise DeliveryError("push refused: invalid verification chain: " + "; ".join(verification_errors))
        if verification_receipt.get("verification_execution_receipt_digest") != bindings["verification_receipt_digest"]:
            raise DeliveryError("push refused: verification receipt digest substitution")
        if verification_receipt.get("valid") is not True or verification_receipt.get("receipt_status") != "EXECUTED":
            raise DeliveryError("push refused: verification receipt must be valid and EXECUTED")
        if Path(str(verification_receipt.get("target_repo"))).resolve() != self.repo:
            raise DeliveryError("push refused: verification target repo mismatch")
        if verification_receipt.get("target_branch") != plan["feature_branch"]:
            raise DeliveryError("push refused: verification target branch mismatch")
        for label in ("preflight_git_state", "postflight_git_state"):
            runner_state = verification_receipt.get(label)
            if (
                not isinstance(runner_state, dict)
                or runner_state.get("captured") is not True
                or runner_state.get("clean") is not True
                or runner_state.get("head_sha") != bindings["commit_sha"]
                or runner_state.get("branch") != bindings["branch"]
            ):
                raise DeliveryError(f"push refused: verification {label} does not prove the exact clean tip")
        if verification_receipt.get("workspace_mutation_detected") is not False:
            raise DeliveryError("push refused: verification observed workspace/source drift")
        process_results = verification_receipt.get("process_results")
        approved_steps = set(verification_approval.get("approved_step_ids", []))
        result_steps = (
            {item.get("step_id") for item in process_results if isinstance(item, dict)}
            if isinstance(process_results, list)
            else set()
        )
        if (
            not process_results
            or any(item.get("status") != "success" for item in process_results if isinstance(item, dict))
            or result_steps != approved_steps
        ):
            raise DeliveryError("push refused: every approved verification process must succeed")
        if verification_receipt.get("skipped_steps"):
            raise DeliveryError("push refused: verification contains skipped steps")
        commit = commit_receipt.get("result", {}).get("commit_sha")
        commit_tree = commit_receipt.get("result", {}).get("tree")
        if commit != bindings["commit_sha"] or commit_tree != bindings["commit_tree"]:
            raise DeliveryError("push refused: commit receipt does not match action request")
        if verification_receipt.get("target_commit") != commit or verification_plan.get("target_head_sha") != commit:
            raise DeliveryError("push refused: verification is not bound to the committed tip")
        if commit != _head(self.repo) or commit_tree != _tree(self.repo) or _status(self.repo):
            raise DeliveryError("push refused: local HEAD differs from verified commit")
        branch = _git(self.repo, "branch", "--show-current").stdout.strip()
        if branch != plan["feature_branch"] or branch == "main":
            raise DeliveryError("push refused: wrong branch or direct main push")
        if _remote(self.repo, bindings["remote_name"]) != bindings["remote_url"]:
            raise DeliveryError("push refused: remote identity mismatch")
        remote_lines = _git(self.repo, "ls-remote", plan["remote_name"], f"refs/heads/{branch}").stdout.split()
        remote_before = remote_lines[0] if remote_lines else ""
        expected_remote = request.get("bindings", {}).get("expected_remote_head", "")
        if expected_remote != remote_before:
            raise DeliveryError("push refused: remote branch moved since action request")
        result = _git(self.repo, "push", plan["remote_name"], f"HEAD:refs/heads/{branch}", check=False)
        if result.returncode:
            return make_delivery_receipt(
                "push",
                status="FAILED",
                request=request,
                approval=approval,
                result={"branch": branch, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]},
                error="git push was rejected",
            )
        remote_head = _git(self.repo, "ls-remote", plan["remote_name"], f"refs/heads/{branch}").stdout.split()[0]
        if remote_head != commit:
            raise DeliveryError("push failed: hosted branch readback differs from intended commit")
        return make_delivery_receipt(
            "push",
            status="SUCCEEDED",
            request=request,
            approval=approval,
            result={
                "commit_sha": commit,
                "tree": _tree(self.repo),
                "branch": branch,
                "remote": plan["remote_url"],
                "remote_head": remote_head,
            },
        )

    def execute_pr(
        self, plan: dict[str, Any], request: dict[str, Any], approval: dict[str, Any], *, push_receipt: dict[str, Any]
    ) -> dict[str, Any]:
        action = request.get("action")
        if action not in ("pr_create", "pr_update"):
            raise DeliveryError("PR refused: action must be pr_create or pr_update")
        bindings = _check_request(plan, request, action)
        _check_approval(request, approval)
        if not _successful_delivery_receipt(push_receipt, "push"):
            raise DeliveryError("PR refused: successful push receipt required")
        if (
            push_receipt.get("receipt_digest") != bindings["push_receipt_digest"]
            or push_receipt.get("result", {}).get("remote_head") != bindings["hosted_head_sha"]
        ):
            raise DeliveryError("PR refused: push receipt custody does not match action request")
        base = plan["pr_base_branch"]
        head = plan["pr_head_branch"]
        head_lines = _git(self.repo, "ls-remote", plan["remote_name"], f"refs/heads/{head}").stdout.split()
        if not head_lines or head_lines[0] != bindings["hosted_head_sha"]:
            raise DeliveryError("PR refused: hosted head SHA differs from action request")
        base_lines = _git(self.repo, "ls-remote", plan["remote_name"], f"refs/heads/{base}").stdout.split()
        if not base_lines or base_lines[0] != bindings["expected_base_sha"]:
            raise DeliveryError("PR refused: hosted base SHA differs from action request")
        if action == "pr_create":
            existing = _run(
                self.repo,
                ["gh", "pr", "list", "--head", head, "--state", "all", "--json", "number,headRefName,baseRefName"],
                check=False,
            )
            if existing.returncode:
                raise DeliveryError("PR create refused: existing-PR custody preflight failed")
            try:
                existing_prs = json.loads(existing.stdout or "[]")
            except json.JSONDecodeError as exc:
                raise DeliveryError("PR create refused: malformed existing-PR preflight") from exc
            if not isinstance(existing_prs, list) or existing_prs:
                raise DeliveryError("PR create refused: an applicable PR already exists")
        else:
            number = bindings["pr_number"]
            if not isinstance(number, int) or number <= 0:
                raise DeliveryError("PR update refused: exact PR number binding required")
            existing = _run(
                self.repo,
                ["gh", "pr", "view", str(number), "--json", "number,headRefName,baseRefName,headRefOid"],
                check=False,
            )
            if existing.returncode:
                raise DeliveryError("PR update refused: bound PR does not exist")
            try:
                existing_pr = json.loads(existing.stdout or "{}")
            except json.JSONDecodeError as exc:
                raise DeliveryError("PR update refused: malformed PR custody readback") from exc
            expected_head = push_receipt["result"].get("remote_head")
            if (
                not isinstance(existing_pr, dict)
                or existing_pr.get("number") != number
                or existing_pr.get("headRefName") != head
                or existing_pr.get("baseRefName") != base
                or (existing_pr.get("headRefOid") and existing_pr.get("headRefOid") != expected_head)
            ):
                raise DeliveryError("PR update refused: existing PR custody differs from action request")
        args = ["gh", "pr", "create" if action == "pr_create" else "edit"]
        if action == "pr_create":
            args += ["--base", base, "--head", head, "--title", plan["pr_title"], "--body", plan["pr_body"]]
            if plan.get("draft"):
                args.append("--draft")
        else:
            args += [str(number), "--title", plan["pr_title"], "--body", plan["pr_body"]]
        result = _run(self.repo, args, check=False)
        if result.returncode:
            return make_delivery_receipt(
                action,
                status="FAILED",
                request=request,
                approval=approval,
                result={"stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]},
                error="gh PR operation was rejected",
            )
        returned_url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        identity = returned_url if action == "pr_create" else str(number)
        if not identity:
            raise DeliveryError("PR refused: operation returned no PR identity")
        readback = _run(
            self.repo,
            [
                "gh",
                "pr",
                "view",
                identity,
                "--json",
                "number,url,state,headRefName,headRefOid,baseRefName,baseRefOid,title,body,isDraft",
            ],
            check=False,
        )
        if readback.returncode:
            raise DeliveryError("PR refused: hosted custody readback failed")
        try:
            custody = json.loads(readback.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise DeliveryError("PR refused: malformed hosted custody readback") from exc
        expected = {
            "state": bindings["expected_state"],
            "headRefName": bindings["head_branch"],
            "headRefOid": bindings["hosted_head_sha"],
            "baseRefName": bindings["base_branch"],
            "baseRefOid": bindings["expected_base_sha"],
            "title": bindings["title"],
            "body": bindings["body"],
            "isDraft": bindings["draft"],
        }
        if (
            not isinstance(custody, dict)
            or not isinstance(custody.get("number"), int)
            or not isinstance(custody.get("url"), str)
            or not custody["url"]
        ):
            raise DeliveryError("PR refused: missing hosted custody fields")
        if action == "pr_create" and custody["url"] != returned_url:
            raise DeliveryError("PR refused: hosted URL differs from created PR")
        if action == "pr_update" and custody["number"] != number:
            raise DeliveryError("PR refused: hosted PR number changed")
        mismatches = sorted(key for key, value in expected.items() if custody.get(key) != value)
        if mismatches:
            raise DeliveryError("PR refused: hosted custody mismatch: " + ", ".join(mismatches))
        return make_delivery_receipt(
            action,
            status="SUCCEEDED",
            request=request,
            approval=approval,
            result={
                "number": custody["number"],
                "url": custody["url"],
                "state": custody["state"],
                "head_branch": custody["headRefName"],
                "head_sha": custody["headRefOid"],
                "base_branch": custody["baseRefName"],
                "base_sha": custody["baseRefOid"],
                "title": custody["title"],
                "body": custody["body"],
                "draft": custody["isDraft"],
                "operation": action,
            },
        )


__all__ = [
    "DELIVERY_ACTION_REQUEST_KIND",
    "DELIVERY_APPROVAL_KIND",
    "DELIVERY_PLAN_KIND",
    "DELIVERY_RECEIPT_KIND",
    "DELIVERY_ACTIONS",
    "DeliveryError",
    "DeliveryService",
    "canonical_digest",
    "make_delivery_plan",
    "make_action_request",
    "make_delivery_approval",
    "make_delivery_receipt",
    "validate_delivery_plan",
    "validate_delivery_action_request",
    "validate_delivery_approval",
    "validate_delivery_receipt",
]
