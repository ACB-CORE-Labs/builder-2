from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

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


def test_artifacts_are_typed_digest_bound_and_non_authoritative(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    plan = _plan(repo, head)
    request = make_action_request(plan, "commit")
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
    request = make_action_request(plan, "commit")
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
    request = make_action_request(plan, "commit")
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_commit(plan, request, approval)
    assert receipt["status"] == "REFUSED"
    assert _head(repo) == head
    assert "unexpected dirty paths" in (receipt["error"] or "")


def test_commit_accepts_exact_planned_untracked_file(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "new.txt").write_text("planned\n")
    plan = _plan(repo, head, paths=["new.txt"])
    request = make_action_request(plan, "commit")
    approval = make_delivery_approval(request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_commit(plan, request, approval)
    assert receipt["status"] == "SUCCEEDED", receipt.get("error")
    assert _git(repo, "show", "HEAD:new.txt") == "planned"


def test_push_requires_exact_commit_receipt_and_reads_back_bare_remote(tmp_path: Path) -> None:
    repo, head, bare = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = make_action_request(plan, "commit")
    commit_approval = make_delivery_approval(commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    push_request = make_action_request(plan, "push", expected_remote_head="")
    push_approval = make_delivery_approval(push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    push_receipt = DeliveryService(repo).execute_push(plan, push_request, push_approval, verified_receipt=commit_receipt)
    assert push_receipt["status"] == "SUCCEEDED"
    assert push_receipt["result"]["remote_head"] == _head(repo)
    assert _git(bare, "show-ref", "refs/heads/feature/delivery").split()[0] == _head(repo)


def test_push_refuses_remote_movement_since_action_request(tmp_path: Path) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = make_action_request(plan, "commit")
    commit_approval = make_delivery_approval(commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    _git(repo, "push", "origin", "HEAD:refs/heads/feature/delivery")
    push_request = make_action_request(plan, "push", expected_remote_head="")
    push_approval = make_delivery_approval(push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    try:
        DeliveryService(repo).execute_push(plan, push_request, push_approval, verified_receipt=commit_receipt)
    except ValueError as exc:
        assert "remote branch moved" in str(exc)
    else:
        raise AssertionError("remote movement must refuse push")


def test_pr_create_uses_fixed_argv_and_binds_push_receipt(tmp_path: Path, monkeypatch) -> None:
    repo, head, _ = _repo(tmp_path)
    (repo / "README").write_text("planned\n")
    plan = _plan(repo, head)
    commit_request = make_action_request(plan, "commit")
    commit_approval = make_delivery_approval(commit_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    commit_receipt = DeliveryService(repo).execute_commit(plan, commit_request, commit_approval)
    push_request = make_action_request(plan, "push")
    push_approval = make_delivery_approval(push_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    push_receipt = DeliveryService(repo).execute_push(plan, push_request, push_approval, verified_receipt=commit_receipt)
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        "  list) printf '%s\\n' '[]' ;;\n"
        "  create|edit) printf '%s\\n' 'https://github.com/example/repo/pull/7' ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    pr_request = make_action_request(plan, "pr_create")
    pr_approval = make_delivery_approval(pr_request, approved_by="operator", approved_at=int(time.time()), ttl_seconds=1000)
    receipt = DeliveryService(repo).execute_pr(plan, pr_request, pr_approval, push_receipt=push_receipt)
    assert receipt["status"] == "SUCCEEDED"
    assert receipt["result"]["url"].endswith("/pull/7")
