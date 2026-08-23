from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from builder_ii.core.config_schema import attach_digest
from builder_ii.core.delivery import (
    DELIVERY_ACTION_REQUEST_KIND,
    DELIVERY_APPROVAL_KIND,
    DELIVERY_PLAN_KIND,
    DELIVERY_RECEIPT_KIND,
    DeliveryService,
    _diff_digest,
    _head,
    _tree,
    canonical_digest,
    make_action_request,
    make_delivery_approval,
    make_delivery_plan,
    validate_delivery_action_request,
    validate_delivery_approval,
    validate_delivery_plan,
    validate_delivery_receipt,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import finalize_verification_execution_approval
from builder_ii.lifecycle.candidate.verification_execution_plan import finalize_verification_execution_plan
from builder_ii.lifecycle.candidate.verification_execution_receipt import finalize_verification_execution_receipt


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, Path]:
    repo = tmp_path / "repo"
    bare = tmp_path / "remote.git"
    repo.mkdir()
    _git(repo, "init", "-b", "feature/delivery")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Delivery Test")
    (repo / "README").write_text("base\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "base")
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True, text=True)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "origin", "HEAD:refs/heads/main")
    return repo, _head(repo), bare


def _plan(repo: Path, head: str, *, paths: list[str] | None = None) -> dict:
    return make_delivery_plan(
        target="generic",
        target_repo=repo,
        repository_identity={"matches": True},
        remote_name="origin",
        remote_url=_git(repo, "config", "--get", "remote.origin.url"),
        feature_branch="feature/delivery",
        base_branch="main",
        base_revision=head,
        pre_commit_head=head,
        expected_paths=paths or ["README"],
        expected_diff_digest=_diff_digest(repo),
        expected_content_digest="a" * 64,
        commit_message="delivery: exact commit",
        pr_title="Delivery test",
        pr_body="Test body",
    )


def _commit_request(plan: dict, repo: Path) -> dict:
    return make_action_request(
        plan,
        "commit",
        expected_head=plan["pre_commit_head"],
        expected_tree=_tree(repo),
        expected_branch=plan["feature_branch"],
        expected_paths=plan["expected_paths"],
        expected_diff_digest=plan["expected_diff_digest"],
        remote_name=plan["remote_name"],
        remote_url=plan["remote_url"],
    )


def _verification_chain(repo: Path, commit: str, branch: str) -> tuple[dict, dict, dict]:
    allowed = [
        {
            "profile": "docs_audit",
            "command_profile_ref": "verification_profiles.builder_full.docs_audit",
            "description": "Bounded docs verification for delivery tests.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        }
    ]
    steps = [
        {
            "step_id": "docs_audit",
            "profile": "docs_audit",
            "command_profile_ref": "verification_profiles.builder_full.docs_audit",
            "description": "Run bounded docs audit.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        }
    ]
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(repo.resolve()),
        target_head_sha=commit,
        tree_clean=True,
        artifact_root=str(repo / ".builder" / "verification"),
        allowed_command_profiles=allowed,
        planned_steps=steps,
        generated_at="2026-08-23T00:00:00+00:00",
    )
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="/tmp/verification-plan.json",
        approval_actor="Test Operator",
        approval_reason="Authorize bounded deterministic delivery verification fixture.",
        approved_command_profiles=["docs_audit"],
        approved_step_ids=["docs_audit"],
        expires_at="2030-01-01T00:00:00Z",
        generated_at="2026-08-23T00:01:00+00:00",
    )
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path="/tmp/verification-plan.json",
        approval_path="/tmp/verification-approval.json",
        runner_mode="bounded_approved_verification",
        receipt_status="EXECUTED",
        executed_steps=[{"step_id": "docs_audit", "status": "executed"}],
        skipped_steps=[],
        process_results=[{"step_id": "docs_audit", "status": "success", "shell": False}],
        preflight_git_state={
            "state_label": "preflight",
            "captured": True,
            "clean": True,
            "head_sha": commit,
            "branch": branch,
            "porcelain_lines": [],
        },
        postflight_git_state={
            "state_label": "postflight",
            "captured": True,
            "clean": True,
            "head_sha": commit,
            "branch": branch,
            "porcelain_lines": [],
        },
        target_commit=commit,
        target_branch=branch,
        generated_at="2026-08-23T00:02:00+00:00",
    )
    assert plan["valid"] is True, plan["errors"]
    assert approval["valid"] is True, approval["errors"]
    assert receipt["valid"] is True, receipt["errors"]
    return plan, approval, receipt


def _push_request(
    plan: dict, commit_receipt: dict, verification_receipt: dict, *, expected_remote_head: str = ""
) -> dict:
    return make_action_request(
        plan,
        "push",
        commit_receipt_digest=commit_receipt["receipt_digest"],
        commit_sha=commit_receipt["result"]["commit_sha"],
        commit_tree=commit_receipt["result"]["tree"],
        verification_receipt_digest=verification_receipt["verification_execution_receipt_digest"],
        branch=plan["feature_branch"],
        remote_name=plan["remote_name"],
        remote_url=plan["remote_url"],
        expected_remote_head=expected_remote_head,
    )


def _pr_request(plan: dict, push_receipt: dict, action: str = "pr_create", **extra: object) -> dict:
    bindings = {
        "push_receipt_digest": push_receipt["receipt_digest"],
        "hosted_head_sha": push_receipt["result"]["remote_head"],
        "head_branch": plan["pr_head_branch"],
        "base_branch": plan["pr_base_branch"],
        "expected_base_sha": plan["base_revision"],
        "expected_state": "OPEN",
        "title": plan["pr_title"],
        "body": plan["pr_body"],
        "draft": plan["draft"],
        **extra,
    }
    return make_action_request(plan, action, **bindings)


def _prepared_push(tmp_path: Path) -> tuple[Path, dict, dict, dict, dict, dict]:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = _commit_request(plan, repo)
    commit_approval = make_delivery_approval(
        commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    verification_plan, verification_approval, verification_receipt = _verification_chain(
        repo, _head(repo), plan["feature_branch"]
    )
    return repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt


def _execute_prepared_push(
    repo: Path,
    plan: dict,
    commit_receipt: dict,
    verification_plan: dict,
    verification_approval: dict,
    verification_receipt: dict,
) -> dict:
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    return DeliveryService(repo).execute_push(
        plan,
        request,
        approval,
        commit_receipt=commit_receipt,
        verification_plan=verification_plan,
        verification_approval=verification_approval,
        verification_receipt=verification_receipt,
    )


def _write_gh(tmp_path: Path, hosted: dict, *, preflight: dict | None = None) -> None:
    gh = tmp_path / "gh"
    preflight_json = json.dumps(preflight or hosted)
    hosted_json = json.dumps(hosted)
    gh.write_text(
        "#!/bin/sh\n"
        'case "$2" in\n'
        "  list) printf '%s\\n' '[]' ;;\n"
        "  create|edit) printf '%s\\n' 'https://github.com/example/repo/pull/7' ;;\n"
        f"  view) case \"$5\" in number,headRefName,baseRefName,headRefOid) printf '%s\\n' '{preflight_json}' ;; *) printf '%s\\n' '{hosted_json}' ;; esac ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)


def test_artifacts_are_typed_digest_bound_and_non_authoritative(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    plan = _plan(repo, head)
    request = _commit_request(plan, repo)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=100)
    assert plan["kind"] == DELIVERY_PLAN_KIND
    assert request["kind"] == DELIVERY_ACTION_REQUEST_KIND
    assert approval["kind"] == DELIVERY_APPROVAL_KIND
    assert validate_delivery_plan(plan) == []
    assert validate_delivery_action_request(request, plan) == []
    assert validate_delivery_approval(approval, request, now=int(time.time()) + 1) == []
    assert plan["artifact_is_authority"] is False
    changed = dict(plan, commit_message="changed")
    changed["plan_digest"] = canonical_digest({k: v for k, v in changed.items() if k != "plan_digest"})
    assert changed["plan_digest"] != plan["plan_digest"]
    assert validate_delivery_plan(changed) == []
    assert validate_delivery_approval(approval, request, now=approval["expires_at"] + 1)


def test_commit_requires_exact_planned_dirty_delta_and_records_sha_tree(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    request = _commit_request(plan, repo)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_commit(plan, request, approval)
    assert receipt["kind"] == DELIVERY_RECEIPT_KIND
    assert receipt["status"] == "SUCCEEDED", receipt.get("error")
    assert receipt["result"]["commit_sha"] == _head(repo)
    assert receipt["result"]["tree"] == _tree(repo)
    assert validate_delivery_receipt(receipt) == []


def test_commit_refuses_unexpected_dirty_path_without_commit(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    (repo / "unexpected.txt").write_text("outside\n")
    request = _commit_request(plan, repo)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_commit(plan, request, approval)
    assert receipt["status"] == "REFUSED"
    assert _head(repo) == head
    assert "unexpected dirty paths" in (receipt["error"] or "")


def test_commit_accepts_exact_planned_untracked_file(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "new.txt").write_text("planned\n")
    plan = _plan(repo, head, paths=["new.txt"])
    request = _commit_request(plan, repo)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_commit(plan, request, approval)
    assert receipt["status"] == "SUCCEEDED", receipt.get("error")
    assert _git(repo, "show", "HEAD:new.txt") == "planned"


def test_push_requires_exact_commit_receipt_and_reads_back_bare_remote(tmp_path: Path) -> None:
    repo, head, bare = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = _commit_request(plan, repo)
    commit_approval = make_delivery_approval(
        commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    verification_plan, verification_approval, verification_receipt = _verification_chain(
        repo, _head(repo), plan["feature_branch"]
    )
    push_request = _push_request(plan, commit_receipt, verification_receipt)
    push_approval = make_delivery_approval(
        push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    push_receipt = DeliveryService(repo).execute_push(
        plan,
        push_request,
        push_approval,
        commit_receipt=commit_receipt,
        verification_plan=verification_plan,
        verification_approval=verification_approval,
        verification_receipt=verification_receipt,
    )
    assert push_receipt["status"] == "SUCCEEDED"
    assert push_receipt["result"]["remote_head"] == _head(repo)
    assert _git(bare, "show-ref", "refs/heads/feature/delivery").split()[0] == _head(repo)


def test_push_refuses_remote_movement_since_action_request(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = _commit_request(plan, repo)
    commit_approval = make_delivery_approval(
        commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    verification_plan, verification_approval, verification_receipt = _verification_chain(
        repo, _head(repo), plan["feature_branch"]
    )
    _git(repo, "push", "origin", "HEAD:refs/heads/feature/delivery")
    push_request = _push_request(plan, commit_receipt, verification_receipt)
    push_approval = make_delivery_approval(
        push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    try:
        DeliveryService(repo).execute_push(
            plan,
            push_request,
            push_approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )
    except ValueError as exc:
        assert "remote branch moved" in str(exc)
    else:
        raise AssertionError("remote movement must refuse push")


def test_pr_create_uses_fixed_argv_and_binds_push_receipt(tmp_path: Path, monkeypatch) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = _commit_request(plan, repo)
    commit_approval = make_delivery_approval(
        commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    verification_plan, verification_approval, verification_receipt = _verification_chain(
        repo, _head(repo), plan["feature_branch"]
    )
    push_request = _push_request(plan, commit_receipt, verification_receipt)
    push_approval = make_delivery_approval(
        push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    push_receipt = DeliveryService(repo).execute_push(
        plan,
        push_request,
        push_approval,
        commit_receipt=commit_receipt,
        verification_plan=verification_plan,
        verification_approval=verification_approval,
        verification_receipt=verification_receipt,
    )
    hosted = {
        "number": 7,
        "url": "https://github.com/example/repo/pull/7",
        "state": "OPEN",
        "headRefName": plan["pr_head_branch"],
        "headRefOid": push_receipt["result"]["remote_head"],
        "baseRefName": plan["pr_base_branch"],
        "baseRefOid": plan["base_revision"],
        "title": plan["pr_title"],
        "body": plan["pr_body"],
        "isDraft": plan["draft"],
    }
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'case "$2" in\n'
        "  list) printf '%s\\n' '[]' ;;\n"
        "  create|edit) printf '%s\\n' 'https://github.com/example/repo/pull/7' ;;\n"
        f"  view) printf '%s\\n' '{json.dumps(hosted)}' ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    pr_request = _pr_request(plan, push_receipt)
    pr_approval = make_delivery_approval(
        pr_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000
    )
    receipt = DeliveryService(repo).execute_pr(plan, pr_request, pr_approval, push_receipt=push_receipt)
    assert receipt["status"] == "SUCCEEDED"
    assert receipt["result"]["url"].endswith("/pull/7")


def test_push_with_commit_receipt_but_no_verification_refuses(tmp_path: Path) -> None:
    repo, plan, commit_receipt, _verification_plan, _verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="canonical verification plan, approval, and receipt are required"):
        DeliveryService(repo).execute_push(plan, request, approval, commit_receipt=commit_receipt)


def test_push_verification_for_previous_commit_refuses(tmp_path: Path) -> None:
    repo, plan, commit_receipt, _verification_plan, _verification_approval, _verification_receipt = _prepared_push(
        tmp_path
    )
    previous = commit_receipt["result"]["parent"]
    verification_plan, verification_approval, verification_receipt = _verification_chain(
        repo, previous, plan["feature_branch"]
    )
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="does not prove the exact clean tip|not bound to the committed tip"):
        DeliveryService(repo).execute_push(
            plan,
            request,
            approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )


@pytest.mark.parametrize("receipt_status", ["FAILED", "NOT_EXECUTED"])
def test_push_failed_or_nonexecuted_verification_refuses(tmp_path: Path, receipt_status: str) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    verification_receipt["receipt_status"] = receipt_status
    verification_receipt = attach_digest(verification_receipt, digest_key="verification_execution_receipt_digest")
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="valid and EXECUTED"):
        DeliveryService(repo).execute_push(
            plan,
            request,
            approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )


def test_push_verification_digest_substitution_refuses(tmp_path: Path) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    request = _push_request(plan, commit_receipt, verification_receipt)
    request["bindings"]["verification_receipt_digest"] = "f" * 64
    request["action_request_digest"] = canonical_digest(
        {k: v for k, v in request.items() if k != "action_request_digest"}
    )
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="verification receipt digest substitution"):
        DeliveryService(repo).execute_push(
            plan,
            request,
            approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )


def test_push_head_or_tree_drift_after_verification_refuses(tmp_path: Path) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    (repo / "README").write_text("drifted after verification\n")
    with pytest.raises(ValueError, match="local HEAD differs from verified commit"):
        DeliveryService(repo).execute_push(
            plan,
            request,
            approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )


def test_push_verification_runner_state_without_exact_clean_tip_refuses(tmp_path: Path) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    verification_receipt["postflight_git_state"]["clean"] = False
    verification_receipt = attach_digest(verification_receipt, digest_key="verification_execution_receipt_digest")
    request = _push_request(plan, commit_receipt, verification_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="postflight_git_state does not prove the exact clean tip"):
        DeliveryService(repo).execute_push(
            plan,
            request,
            approval,
            commit_receipt=commit_receipt,
            verification_plan=verification_plan,
            verification_approval=verification_approval,
            verification_receipt=verification_receipt,
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("headRefOid", "f" * 40),
        ("baseRefOid", "e" * 40),
        ("title", "wrong title"),
        ("body", "wrong body"),
        ("isDraft", True),
    ],
)
def test_pr_create_hosted_custody_mismatch_refuses(tmp_path: Path, monkeypatch, field: str, bad_value: object) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    push_receipt = _execute_prepared_push(
        repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt
    )
    hosted = {
        "number": 7,
        "url": "https://github.com/example/repo/pull/7",
        "state": "OPEN",
        "headRefName": plan["pr_head_branch"],
        "headRefOid": push_receipt["result"]["remote_head"],
        "baseRefName": plan["pr_base_branch"],
        "baseRefOid": plan["base_revision"],
        "title": plan["pr_title"],
        "body": plan["pr_body"],
        "isDraft": plan["draft"],
    }
    hosted[field] = bad_value
    _write_gh(tmp_path, hosted)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    request = _pr_request(plan, push_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="hosted custody mismatch"):
        DeliveryService(repo).execute_pr(plan, request, approval, push_receipt=push_receipt)


@pytest.mark.parametrize("stdout", ["", "not-json"])
def test_pr_create_missing_or_malformed_readback_refuses(tmp_path: Path, monkeypatch, stdout: str) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    push_receipt = _execute_prepared_push(
        repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt
    )
    gh = tmp_path / "gh"
    gh.write_text(
        '#!/bin/sh\ncase "$2" in\n'
        "list) printf '%s\\n' '[]' ;;\n"
        "create) printf '%s\\n' 'https://github.com/example/repo/pull/7' ;;\n"
        f"view) printf '%s\\n' '{stdout}' ;;\nesac\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    request = _pr_request(plan, push_receipt)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="malformed hosted custody readback|missing hosted custody fields"):
        DeliveryService(repo).execute_pr(plan, request, approval, push_receipt=push_receipt)


def test_pr_update_external_custody_change_refuses(tmp_path: Path, monkeypatch) -> None:
    repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt = _prepared_push(
        tmp_path
    )
    push_receipt = _execute_prepared_push(
        repo, plan, commit_receipt, verification_plan, verification_approval, verification_receipt
    )
    preflight = {
        "number": 7,
        "headRefName": plan["pr_head_branch"],
        "baseRefName": plan["pr_base_branch"],
        "headRefOid": push_receipt["result"]["remote_head"],
    }
    changed = {
        "number": 7,
        "url": "https://github.com/example/repo/pull/7",
        "state": "OPEN",
        "headRefName": "externally-changed",
        "headRefOid": push_receipt["result"]["remote_head"],
        "baseRefName": plan["pr_base_branch"],
        "baseRefOid": plan["base_revision"],
        "title": plan["pr_title"],
        "body": plan["pr_body"],
        "isDraft": plan["draft"],
    }
    _write_gh(tmp_path, changed, preflight=preflight)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    request = _pr_request(plan, push_receipt, "pr_update", pr_number=7)
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    with pytest.raises(ValueError, match="hosted custody mismatch"):
        DeliveryService(repo).execute_pr(plan, request, approval, push_receipt=push_receipt)


@pytest.mark.parametrize("action", ["commit", "push", "pr_create", "pr_update"])
def test_missing_action_specific_predecessor_binding_is_schema_invalid(tmp_path: Path, action: str) -> None:
    repo, head, _ = _repo(tmp_path)
    plan = _plan(repo, head)
    request = make_action_request(plan, action)
    errors = validate_delivery_action_request(request, plan)
    assert any(f"{action} bindings missing required keys" in error for error in errors)
