from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.config_schema import attach_digest
from builder_ii.setup_cli import setup_app
from builder_ii.setup_receipt import validate_setup_receipt_artifact

runner = CliRunner()


def _change(path: Path, op: str = "create", content: str = "safe=value\n") -> dict:
    import hashlib
    return {
        "change_id": path.name.replace('.', '_'),
        "change_kind": "env_recommendation_candidate",
        "raw_target_path": str(path),
        "target_path": str(path),
        "path_scope_classification": "artifact_root",
        "inside_builder_repo": False,
        "inside_target_repo": False,
        "inside_user_config_dir": False,
        "inside_artifact_root": True,
        "path_traversal_rejected": False,
        "path_safety_errors": [],
        "operation_type": op,
        "expected_path_kind": "directory" if op == "mkdir" else "file",
        "content_digest": hashlib.sha256(content.encode()).hexdigest(),
        "source_path": "",
        "redacted_preview": content,
        "conflict_classification": "none",
        "requires_future_approval": op != "no-op",
        "rollback_requirement": {"required": op != "no-op"},
        "safety_notes": [],
        "planned_only": True,
        "metadata": content,
    }


def _artifacts(tmp_path: Path, changes: list[dict] | None = None):
    target = tmp_path / "target"
    artifact = tmp_path / "artifacts"
    target.mkdir(exist_ok=True)
    artifact.mkdir(exist_ok=True)
    changes = changes or [_change(artifact / "setup" / "created.txt")]
    overlay = {
        "kind": "builder_ii.setup_overlay_plan",
        "schema_version": 1,
        "artifact_is_authority": False,
        "planned_only": True,
        "setup_plan_ref": {"kind": "builder_ii.setup_plan", "digest": "a" * 64},
        "builder_repo_canonical_path": str(tmp_path / "builder"),
        "target_repo_canonical_path": str(target),
        "artifact_root_canonical_path": str(artifact),
        "user_config_dir_canonical_path": str(tmp_path / "config"),
        "path_policy": {"declared_setup_scopes": {"builder_repo": str(tmp_path / "builder"), "target_repo": str(target), "artifact_root": str(artifact), "user_config_dir": str(tmp_path / "config")}, "path_traversal_allowed": False, "symlink_following_allowed": False, "future_apply_requires_atomic_writes": True},
        "capability_map": {"runtime_execution": "disabled", "model_execution": "disabled", "shell_execution": "disabled", "source_writes": "disabled", "goose_runtime": "disabled", "deepagents_runtime": "disabled", "mcp_tool_invocation": "disabled", "patch_authority": "disabled", "autonomous_writes": "disabled", "setup_apply": "disabled", "setup_rollback_execution": "disabled", "artifact_output": "explicit_output_path_only"},
        "planned_changes": changes,
        "goose_overlay_candidate": {},
        "skill_install_plan": {"copy_skills": False, "entries": []},
        "safety_summary": {},
        "no_mutation_proof": {"overlay_plan_generation_performs_writes": False, "target_repo_writes": False, "goose_config_writes": False, "goosehints_writes": False, "skill_copy": False, "recipe_installation_writes": False, "runtime_start": False, "model_calls": False, "shell_execution": False, "mcp_tool_invocation": False, "patch_application": False, "deepagents_construction": False, "setup_apply": False, "setup_rollback_execution": False, "only_explicit_output_artifact_may_be_written_by_cli": True},
        "governance": {"artifact_is_authority": False},
    }
    overlay = attach_digest(overlay, digest_key="overlay_plan_digest")
    states = [{"target_path": c["target_path"], "change_ids": [c["change_id"]], "change_kinds": [c["change_kind"]], "planned_operation_types": [c["operation_type"]], "prior_existence_state": "missing", "missing_file_marker": True, "directory_marker": False, "symlink_marker": False, "unsupported_path_marker": False, "prior_content_digest": "", "prior_content_size_bytes": 0, "prior_redacted_preview": "", "prior_content_storage_policy": "not_stored_missing_file_marker_only", "secret_redaction_state": "not_read", "raw_content_included": False, "snapshot_only": True, "artifact_is_authority": False, "future_rollback_operation_needed": "delete_future_created_path", "path_notes": []} for c in changes]
    snap = {"kind": "builder_ii.setup_rollback_snapshot", "schema_version": 1, "artifact_is_authority": False, "snapshot_only": True, "setup_plan_digest": "a" * 64, "overlay_plan_digest": overlay["overlay_plan_digest"], "snapshot_id": "b" * 64, "target_paths_covered": [c["target_path"] for c in changes], "target_path_states": states, "prior_content_default_storage_policy": "x", "secret_policy": {"raw_secrets_stored_in_json": False, "raw_prior_content_stored_in_json": False, "redacted_preview_only": True}, "no_mutation_proof": {"snapshot_generation_performs_writes": False, "target_repo_writes": False, "goose_config_writes": False, "goosehints_writes": False, "skill_copy": False, "recipe_installation_writes": False, "runtime_start": False, "model_calls": False, "shell_execution": False, "mcp_tool_invocation": False, "patch_application": False, "deepagents_construction": False, "setup_apply": False, "setup_rollback_execution": False, "only_explicit_output_artifact_may_be_written_by_cli": True}, "governance": {"artifact_is_authority": False}}
    snap = attach_digest(snap, digest_key="snapshot_digest")
    return overlay, snap


def _write(tmp_path, overlay, snap):
    op = tmp_path / "overlay.json"; sp = tmp_path / "snapshot.json"
    op.write_text(json.dumps(overlay), encoding="utf-8"); sp.write_text(json.dumps(snap), encoding="utf-8")
    return op, sp


def test_apply_denied_without_or_wrong_digest(tmp_path):
    overlay, snap = _artifacts(tmp_path); op, sp = _write(tmp_path, overlay, snap)
    assert runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(tmp_path/"r.json")]).exit_code != 0
    assert runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", "0"*64, "--output", str(tmp_path/"r.json")]).exit_code != 0


def test_apply_denied_mismatched_snapshot_and_undeclared_path(tmp_path):
    overlay, snap = _artifacts(tmp_path); snap["overlay_plan_digest"] = "c"*64; snap = attach_digest(snap, digest_key="snapshot_digest"); op, sp = _write(tmp_path, overlay, snap)
    assert runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", overlay["overlay_plan_digest"], "--output", str(tmp_path/"r.json")]).exit_code != 0


def test_apply_denied_path_traversal_symlink_and_unsupported(tmp_path):
    symlink = tmp_path / "artifacts" / "link.txt"; (tmp_path / "artifacts").mkdir(); symlink.symlink_to(tmp_path / "elsewhere")
    for change in [_change(tmp_path / "artifacts" / "bad.txt", op="merge"), {**_change(symlink), "conflict_classification": "symlink_path"}, {**_change(tmp_path / "artifacts" / "trav.txt"), "path_traversal_rejected": True}]:
        overlay, snap = _artifacts(tmp_path, [change]); op, sp = _write(tmp_path, overlay, snap)
        assert runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", overlay["overlay_plan_digest"], "--output", str(tmp_path/f"{change['change_id']}.json")]).exit_code != 0


def test_apply_writes_declared_path_receipt_digests_noop_and_redaction(tmp_path):
    secret_change = _change(tmp_path / "artifacts" / "setup" / "secret.txt", content="API_TOKEN=supersecret\n")
    noop = _change(tmp_path / "artifacts" / "setup" / "noop.txt", op="no-op")
    overlay, snap = _artifacts(tmp_path, [secret_change, noop]); op, sp = _write(tmp_path, overlay, snap); receipt_path = tmp_path / "receipt.json"
    result = runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", overlay["overlay_plan_digest"], "--output", str(receipt_path)])
    assert result.exit_code == 0, result.output
    assert Path(secret_change["target_path"]).exists()
    receipt = json.loads(receipt_path.read_text())
    assert not validate_setup_receipt_artifact(receipt)
    assert receipt["changed_paths"] == [secret_change["target_path"]]
    assert noop["target_path"] in receipt["skipped_paths"]
    assert receipt["operations"][0]["before_digest"] != receipt["operations"][0]["after_digest"]
    assert "supersecret" not in json.dumps(receipt)


def test_create_existing_target_denied_in_preflight_without_mutating_prior_change(tmp_path):
    new_path = tmp_path / "artifacts" / "setup" / "new.txt"
    existing_path = tmp_path / "artifacts" / "setup" / "existing.txt"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_text("preexisting\n", encoding="utf-8")
    change_a = _change(new_path, op="create", content="A=created\n")
    change_b = _change(existing_path, op="create", content="B=must-not-overwrite\n")
    overlay, snap = _artifacts(tmp_path, [change_a, change_b])
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "receipt.json"

    result = runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", overlay["overlay_plan_digest"], "--output", str(receipt_path)])

    assert result.exit_code != 0
    receipt = json.loads(receipt_path.read_text())
    assert receipt["operation_result"] == "denied"
    assert receipt["changed_paths"] == []
    assert change_b["target_path"] in receipt["denied_paths"]
    assert not new_path.exists()
    assert existing_path.read_text(encoding="utf-8") == "preexisting\n"


def test_noop_source_repo_paths_are_skipped_not_denied(tmp_path):
    source = tmp_path / "builder" / ".goosehints"
    source.parent.mkdir()
    change = {**_change(source, op="no-op"), "inside_builder_repo": True, "inside_artifact_root": False, "path_scope_classification": "builder_repo"}
    overlay, snap = _artifacts(tmp_path, [change]); op, sp = _write(tmp_path, overlay, snap); receipt_path = tmp_path / "receipt.json"
    result = runner.invoke(setup_app, ["apply", str(op), "--rollback-snapshot", str(sp), "--approve-digest", overlay["overlay_plan_digest"], "--output", str(receipt_path)])
    assert result.exit_code == 0, result.output
    receipt = json.loads(receipt_path.read_text())
    assert change["target_path"] in receipt["skipped_paths"]
    assert receipt["denied_paths"] == []


def test_command_authority_apply_does_not_grant_runtime_model_tool_patch():
    record = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}["builder-setup apply"]
    assert record.allows_source_writes
    assert not record.allows_runtime_start
    assert not record.allows_model_execution
    assert not record.allows_shell_execution
    assert not record.allows_external_tool_invocation
    assert not record.allows_git_mutation
