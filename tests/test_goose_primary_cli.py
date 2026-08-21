from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt
from typer.testing import CliRunner

import builder_ii.cli.main as main_cli
from builder_ii.adapters.goose.goose_receipts import create_goose_launch_receipt
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness, _get_target_files
from builder_ii.adapters.mcp.governed_services import run_service
from builder_ii.cli.main import app
from builder_ii.governance.authority import CommandAuthorityError
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal


def test_primary_builder_start_uses_governed_lifecycle_and_persists_receipts(monkeypatch, tmp_path: Path) -> None:
    session = SimpleNamespace(
        mode="orchestrator", model_alias="alias", model_tier="3", target_name="builder", agent_profile="patch_planner"
    )
    settings = SimpleNamespace(
        project_root=tmp_path,
        target_repo=tmp_path,
        model_alias="alias",
        backend="openai",
        active_model_id="model",
    )
    launch = create_goose_launch_receipt(
        "primary-test", "builder", "patch_planner", 42, "2026-01-01T00:00:00+00:00", {"runtime": "goose_governed"}
    )
    close = {"kind": "builder_ii.goose_close_receipt", "digest": "close-digest"}
    postflight = {"kind": "builder_ii.no_mutation_postflight", "valid": True, "digest": "postflight-digest"}
    calls: list[str] = []

    monkeypatch.setattr(main_cli, "enforce_command_authority", lambda *_args, **_kwargs: calls.append("authority"))

    class FakeHarness:
        def __init__(self, *_args):
            self.session_id = "primary-test"

        def admit_governed(self):
            calls.append("admit")
            return SimpleNamespace(binary="/mock/goose", version="1.46.0", policy=">=1.45.0,<1.47.0"), "r" * 64

        def launch_governed(self):
            calls.append("launch")
            return launch

        def wait_for_exit(self):
            calls.append("wait")
            return 0

        def close(self, digest):
            calls.append(f"close:{digest}")
            return close, postflight

    monkeypatch.setattr("builder_ii.core.config.load_settings", lambda: settings)
    monkeypatch.setattr("builder_ii.core.config.normalize_model_alias", lambda alias, tier_fallback: alias)
    monkeypatch.setattr("builder_ii.routing.model_router.plan_session", lambda mode, task: session)
    monkeypatch.setattr("builder_ii.routing.model_router.explain_plan", lambda session: "plan")
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: calls.append("backend"))
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness", FakeHarness)

    result = CliRunner().invoke(app, ["start", "--task", "test", "--name", "primary-test"])

    assert result.exit_code == 0, result.output
    assert calls == ["authority", "admit", "backend", "launch", "wait", f"close:{launch['digest']}"]
    receipts = tmp_path / ".builder" / "receipts"
    assert json.loads((receipts / "primary-test_launch.json").read_text())["schema_version"] == 2
    assert json.loads((receipts / "primary-test_postflight.json").read_text()) == postflight


def test_primary_builder_start_denied_authority_has_no_side_effects(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def deny(*_args, **_kwargs):
        calls.append("authority")
        raise CommandAuthorityError("builder start denied")

    monkeypatch.setattr(main_cli, "enforce_command_authority", deny)
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: calls.append("backend"))
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness", lambda *_args: calls.append("goose")
    )

    result = CliRunner().invoke(app, ["start", "--task", "test", "--name", "denied-test"])

    assert result.exit_code != 0
    assert calls == ["authority"]
    assert not (tmp_path / ".builder" / "receipts").exists()


def test_primary_builder_start_closes_real_session_bound_mcp_patch(monkeypatch, tmp_path: Path) -> None:
    real_subprocess_run = subprocess.run
    target = init_target_repo(tmp_path)
    builder_root = tmp_path / "builder-artifacts"
    builder_root.mkdir()
    verification = builder_root / "verification.json"
    shutil.copyfile(real_verification_receipt(tmp_path, target), verification)
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, check=True, capture_output=True, text=True
    ).stdout.strip()
    proposal = create_hitl_patch_proposal(
        generic_repo=target,
        patch_digest=patch_digest,
        unified_diff=PATCH_DIFF,
        target_head_sha=head,
        verification_receipt_file_sha256=hashlib.sha256(verification.read_bytes()).hexdigest(),
    )
    proposal_path = builder_root / "proposal.json"
    approval_path = builder_root / "approval.json"
    write_hitl_patch_proposal(proposal, proposal_path)
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )
    session = SimpleNamespace(
        mode="orchestrator",
        model_alias="alias",
        model_tier="primary",
        target_name="generic",
        agent_profile="patch_planner",
    )
    settings = SimpleNamespace(
        project_root=tmp_path,
        target_repo=target,
        model_alias="alias",
        backend="openai",
        active_model_id="model",
    )

    class ProductHarness(GooseRuntimeHarness):
        def admit_governed(self):
            self._admitted_artifact_root = builder_root
            return SimpleNamespace(binary="/mock/goose", version="1.46.0", policy=">=1.45.0,<1.47.0"), "r" * 64

        def launch_governed(self):
            self._preflight_snapshot = _get_target_files(self.target_root)
            receipt, _, _ = run_service(
                tool_name="patch_apply",
                arguments={
                    "proposal_path": str(proposal_path),
                    "approval_path": str(approval_path),
                    "verification_receipt_path": str(verification),
                },
                session_id=self.session_id,
                builder_root=builder_root,
                target_root=target,
                target_name="generic",
            )
            assert receipt["status"] == "succeeded"
            return create_goose_launch_receipt(
                self.session_id,
                "generic",
                "patch_planner",
                42,
                "2026-01-01T00:00:00+00:00",
                {"runtime": "goose_governed"},
            )

        def wait_for_exit(self):
            return 0

    monkeypatch.setattr(main_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builder_ii.core.config.load_settings", lambda: settings)
    monkeypatch.setattr("builder_ii.core.config.normalize_model_alias", lambda alias, tier_fallback: alias)
    monkeypatch.setattr("builder_ii.routing.model_router.plan_session", lambda mode, task: session)
    monkeypatch.setattr("builder_ii.routing.model_router.explain_plan", lambda session: "plan")
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: None)
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness", ProductHarness)

    def bounded_run(args, *run_args, **run_kwargs):
        if isinstance(args, list) and args[:3] == ["goose", "session", "export"]:
            return SimpleNamespace(returncode=0)
        return real_subprocess_run(args, *run_args, **run_kwargs)

    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run", bounded_run)

    result = CliRunner().invoke(app, ["start", "--task", "test", "--name", "primary-r2"])

    assert result.exit_code == 0, result.output
    assert (target / "file.txt").read_text(encoding="utf-8") == "Line 1\nLine 2 modified\n"
    postflight = json.loads((target / ".builder" / "receipts" / "primary-r2_postflight.json").read_text())
    assert postflight["valid"] is True
    assert postflight["mutation_mode"] == "approved_hitl_patch"
