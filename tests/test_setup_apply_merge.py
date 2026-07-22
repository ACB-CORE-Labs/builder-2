"""Ladder 7: the secrets-preserving `merge` apply operation for the Goose config overlay.

`setup_overlay._OPERATIONS` has always included `"merge"`; `setup_apply.SUPPORTED_OPERATIONS`
refused it, so an overlay plan that validated could never be applied. These tests pin the
mechanics that make `merge` safe to execute: unknown keys (including a credential under a
non-marker name) round-trip untouched, a nested secret never surfaces in any emitted
artifact, mutation only happens with rollback-snapshot coverage, atomic writes leave the
original file intact on failure, and a repeated merge is a no-op.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from builder_ii.setup_cli import setup_app
from test_setup_apply import _artifacts, _write
from typer.testing import CliRunner

from builder_ii.lifecycle.setup.setup_apply import _MERGE_PREVIEW_WITHHELD, SUPPORTED_OPERATIONS, _redact
from builder_ii.lifecycle.setup.setup_overlay import _OPERATIONS as OVERLAY_OPERATIONS
from builder_ii.lifecycle.setup.setup_rollback import _OPERATOR_FILE_PREVIEW_WITHHELD as _SNAPSHOT_PREVIEW_WITHHELD
from builder_ii.lifecycle.setup.setup_rollback import (
    create_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
)
from builder_ii.lifecycle.setup.setup_rollback_execute import _preflight_state

runner = CliRunner()

MERGE_FRAGMENT = {
    "extensions": {
        "builder_ii": {"developer": {"bundled": True, "enabled": True, "type": "builtin", "timeout": 600}}
    },
    "recipes": {"builder_ii": {"path": "/recipes/builder_ii.yaml"}},
    "slash_commands": {"builder_ii": {"recipe_path": "/recipes/builder_ii.yaml"}},
}
OVERLAY_KEYS = ["extensions.builder_ii", "recipes.builder_ii.path", "slash_commands.builder_ii.recipe_path"]


def _merge_change(path: Path, *, fragment: dict | None = None, keys: list[str] | None = None) -> dict:
    fragment = MERGE_FRAGMENT if fragment is None else fragment
    keys = OVERLAY_KEYS if keys is None else keys
    preview = yaml.safe_dump(fragment, sort_keys=False)
    return {
        "change_id": path.name.replace(".", "_"),
        "change_kind": "goose_config_overlay_candidate",
        "raw_target_path": str(path),
        "target_path": str(path),
        "path_scope_classification": "user_config_dir",
        "inside_builder_repo": False,
        "inside_target_repo": False,
        "inside_user_config_dir": True,
        "inside_artifact_root": False,
        "path_traversal_rejected": False,
        "path_safety_errors": [],
        "operation_type": "merge",
        "expected_path_kind": "file",
        "content_digest": hashlib.sha256(preview.encode()).hexdigest(),
        "source_path": "",
        "redacted_preview": preview,
        "conflict_classification": "none",
        "requires_future_approval": True,
        "rollback_requirement": {"required": True},
        "safety_notes": [],
        "planned_only": True,
        "metadata": {"merge_fragment": fragment, "overlay_keys": keys},
    }


def _apply(tmp_path: Path, op: Path, sp: Path, overlay: dict, *, name: str = "receipt.json"):
    receipt_path = tmp_path / name
    result = runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--approve-digest",
            overlay["overlay_plan_digest"],
            "--output",
            str(receipt_path),
        ],
    )
    receipt = json.loads(receipt_path.read_text())
    return result, receipt


def test_plan_apply_operation_parity() -> None:
    """setup_apply.SUPPORTED_OPERATIONS must cover every overlay operation except a
    named, tested refusal. `merge` is now covered; `copy` remains the one gap, and it
    must refuse loudly rather than silently no-op."""
    assert SUPPORTED_OPERATIONS <= OVERLAY_OPERATIONS
    assert OVERLAY_OPERATIONS - SUPPORTED_OPERATIONS == {"copy"}


def test_copy_is_an_explicit_named_refusal(tmp_path: Path) -> None:
    change = _merge_change(tmp_path / "config" / "goose" / "config.yaml")
    change["operation_type"] = "copy"
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)
    result, receipt = _apply(tmp_path, op, sp, overlay)
    assert result.exit_code != 0
    assert receipt["operation_result"] == "denied"
    assert "unsupported operation: copy" in receipt["operations"][0]["reason"]


def test_redact_nested_secret_never_leaks_through_unmarked_descendant() -> None:
    text = (
        "extensions:\n"
        "  openai:\n"
        "    api_key:\n"
        "      value: sk-proj-REAL_SECRET_HERE\n"
    )
    redacted = _redact(text)
    assert "sk-proj-REAL_SECRET_HERE" not in redacted
    assert "api_key: <redacted>" in redacted


def test_merge_preserves_unknown_keys_including_non_marker_credential(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "providers:\n"
        "  openai:\n"
        "    api_key:\n"
        "      value: sk-proj-REAL_SECRET_HERE\n"
        "extensions:\n"
        "  other_tool:\n"
        "    enabled: true\n"
        "    nested:\n"
        "      deeply:\n"
        "        license_blob: my-secret-token-xyz\n",
        encoding="utf-8",
    )
    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code == 0, result.output
    assert receipt["operation_result"] == "applied"
    written = yaml.safe_load(target.read_text(encoding="utf-8"))

    # Untouched by the merge, byte-for-byte in value, including the non-marker-named credential.
    assert written["providers"]["openai"]["api_key"]["value"] == "sk-proj-REAL_SECRET_HERE"
    assert written["extensions"]["other_tool"]["enabled"] is True
    assert written["extensions"]["other_tool"]["nested"]["deeply"]["license_blob"] == "my-secret-token-xyz"

    # The three overlay_keys were added as siblings, not a replacement of the extensions block.
    assert written["extensions"]["builder_ii"]["developer"]["enabled"] is True
    assert written["recipes"]["builder_ii"]["path"] == "/recipes/builder_ii.yaml"
    assert written["slash_commands"]["builder_ii"]["recipe_path"] == "/recipes/builder_ii.yaml"

    op_record = next(op for op in receipt["operations"] if op["target_path"] == str(target))
    assert op_record["merge_keys_written"] == sorted(OVERLAY_KEYS)
    assert op_record["merge_keys_preserved_count"] >= 4  # providers, openai, api_key, value, ... (nested count)


def test_nested_secret_never_leaks_into_any_emitted_artifact(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "extensions:\n"
        "  openai:\n"
        "    api_key:\n"
        "      value: sk-proj-REAL_SECRET_HERE\n",
        encoding="utf-8",
    )
    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code == 0, result.output
    # Obligation 1: preserved in the file on disk.
    assert "sk-proj-REAL_SECRET_HERE" in target.read_text(encoding="utf-8")
    # Obligation 2: never copied into any emitted artifact.
    assert "sk-proj-REAL_SECRET_HERE" not in json.dumps(receipt)
    assert "sk-proj-REAL_SECRET_HERE" not in result.output


def test_merge_denied_without_rollback_snapshot_coverage_leaves_target_untouched(tmp_path: Path) -> None:
    """`merge` gets the same rule as `replace`: no rollback-snapshot coverage, no
    mutation. In this codebase that rule is enforced twice — a universal gate
    (snapshot's covered-path set must equal the overlay's declared-path set
    exactly, for every operation) fires before the per-change loop, and a
    per-operation check inside the loop mirrors it for replace/merge specifically.
    The universal gate is what actually fires here; see the per-operation
    unreachability finding in the PR body."""
    from test_setup_apply import _change

    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("providers:\n  openai:\n    api_key: sk-should-not-move\n", encoding="utf-8")
    original = target.read_text(encoding="utf-8")

    merge_change = _merge_change(target)
    dummy_change = _change(tmp_path / "artifacts" / "setup" / "dummy.txt")
    overlay, snap = _artifacts(tmp_path, [merge_change, dummy_change])

    # Keep the snapshot well-formed (non-empty target_path_states) but drop coverage
    # for the merge target specifically, so the gate must refuse it.
    from builder_ii.core.config_schema import attach_digest

    snap["target_paths_covered"] = [dummy_change["target_path"]]
    snap["target_path_states"] = [
        state for state in snap["target_path_states"] if state["target_path"] == dummy_change["target_path"]
    ]
    snap = attach_digest(snap, digest_key="snapshot_digest")
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code != 0
    assert receipt["operation_result"] == "denied"
    assert str(target) in receipt["denied_paths"]
    assert receipt["operations"] == []  # denied before the per-change loop; see docstring above
    assert target.read_text(encoding="utf-8") == original


def test_merge_denied_when_existing_target_is_not_valid_yaml_and_error_is_not_leaked(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    # Invalid YAML (unbalanced flow mapping) that itself contains a secret-shaped string,
    # so we can prove the denial reason never echoes the parser's offending-line context.
    original = "api_key: [unterminated-flow-map: sk-should-not-appear-in-any-reason\n"
    target.write_text(original, encoding="utf-8")

    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code != 0
    assert receipt["operation_result"] == "denied"
    assert "not valid YAML" in receipt["operations"][0]["reason"]
    assert "sk-should-not-appear-in-any-reason" not in json.dumps(receipt)
    assert target.read_text(encoding="utf-8") == original


def test_merge_atomic_write_failure_leaves_original_file_intact(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    original = "providers:\n  openai:\n    api_key: sk-do-not-corrupt\n"
    target.write_text(original, encoding="utf-8")

    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    import os

    def _boom(*_args, **_kwargs):
        raise OSError("simulated disk failure mid-write")

    monkeypatch.setattr(os, "fsync", _boom)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code != 0
    assert receipt["operation_result"] == "failed"
    assert target.read_text(encoding="utf-8") == original
    # The temp file must not survive either.
    leftovers = list(target.parent.glob(".config.yaml.*.tmp"))
    assert leftovers == []


def test_merge_is_idempotent_second_identical_apply_is_noop(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("providers:\n  openai:\n    api_key: sk-stable\n", encoding="utf-8")

    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    first_result, first_receipt = _apply(tmp_path, op, sp, overlay, name="receipt1.json")
    assert first_result.exit_code == 0, first_result.output
    assert first_receipt["changed_paths"] == [str(target)]
    after_first = target.read_text(encoding="utf-8")

    second_result, second_receipt = _apply(tmp_path, op, sp, overlay, name="receipt2.json")
    assert second_result.exit_code == 0, second_result.output
    assert second_receipt["changed_paths"] == []
    assert str(target) in second_receipt["skipped_paths"]
    assert target.read_text(encoding="utf-8") == after_first


def test_merge_into_missing_target_creates_fresh_file(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code == 0, result.output
    assert receipt["changed_paths"] == [str(target)]
    written = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert written["recipes"]["builder_ii"]["path"] == "/recipes/builder_ii.yaml"


def test_merge_requires_structured_merge_fragment_metadata(tmp_path: Path) -> None:
    """A change claiming operation_type=merge without a merge_fragment/overlay_keys
    payload must be denied, not crash the applier."""
    target = tmp_path / "config" / "goose" / "config.yaml"
    change = _merge_change(target)
    change["metadata"] = "plain string, not merge instructions"
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, receipt = _apply(tmp_path, op, sp, overlay)

    assert result.exit_code != 0
    assert receipt["operation_result"] == "denied"
    assert "merge_fragment" in receipt["operations"][0]["reason"]
    assert not target.exists()


def test_merge_comment_and_key_order_decision_is_pinned(tmp_path: Path) -> None:
    """Deliberate, declared loss: pyyaml's safe_load/safe_dump round-trip drops
    comments and anchors. Key insertion order is preserved (sort_keys=False plus
    Python dict insertion order), so pre-existing top-level keys keep their
    relative order and only the new builder_ii keys are appended."""
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(
        "# operator hand-authored comment: do not remove my extensions!\n"
        "zzz_last_provider:\n"
        "  enabled: true\n"
        "aaa_first_provider:\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)

    result, _receipt = _apply(tmp_path, op, sp, overlay)
    assert result.exit_code == 0, result.output

    written_text = target.read_text(encoding="utf-8")
    assert "operator hand-authored comment" not in written_text  # declared loss

    top_level_keys = list(yaml.safe_load(written_text).keys())
    assert top_level_keys.index("zzz_last_provider") < top_level_keys.index("aaa_first_provider")
    assert top_level_keys[-3:] == ["extensions", "recipes", "slash_commands"]


# --- a preview of a credential file is not evidence; it is a copy ------------------------------
#
# Redaction recognises key NAMES, not credentials. `_SECRET_MARKERS` knows seven words, so a
# credential under `openai_key` or `session_cookie` survives it untouched. Proven by running the
# code. That is tolerable for content builder-II authored and intolerable for content the operator
# authored -- and a merge exists precisely to PRESERVE the operator's credentials in the target,
# so the merged document contains every one of them. Neither the receipt nor the rollback snapshot
# may reproduce it. The before/after digests identify the file without copying it.

_UNMARKED_CREDENTIAL_CONFIG = (
    "providers:\n"
    "  openai:\n"
    "    openai_key: sk-proj-UNMARKED-KEY\n"
    "    session_cookie: sk-proj-UNMARKED-COOKIE\n"
    "    api_key: sk-proj-MARKED-KEY\n"
)


def test_marker_redaction_cannot_see_a_credential_under_an_unrecognised_key() -> None:
    """The honest limit that forces the withholding below. If this ever stops being true, say so."""
    redacted = _redact(_UNMARKED_CREDENTIAL_CONFIG)
    assert "sk-proj-MARKED-KEY" not in redacted
    assert "sk-proj-UNMARKED-KEY" in redacted, "marker redaction is name-based; this is its limit"


def test_merge_receipt_never_previews_the_merged_document(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(_UNMARKED_CREDENTIAL_CONFIG, encoding="utf-8")

    change = _merge_change(target)
    overlay, snap = _artifacts(tmp_path, [change])
    op, sp = _write(tmp_path, overlay, snap)
    result, receipt = _apply(tmp_path, op, sp, overlay)
    assert result.exit_code == 0, result.output

    blob = json.dumps(receipt)
    for credential in ("sk-proj-UNMARKED-KEY", "sk-proj-UNMARKED-COOKIE", "sk-proj-MARKED-KEY"):
        assert credential not in blob, f"{credential} was copied into the setup receipt"

    merge_op = next(op_record for op_record in receipt["operations"] if op_record["operation_type"] == "merge")
    assert merge_op["redacted_preview"] == _MERGE_PREVIEW_WITHHELD
    assert merge_op["merge_keys_written"], "the receipt must still say what we wrote"
    assert merge_op["before_digest"] != merge_op["after_digest"]

    # And the credentials really are still in the file -- withholding the preview loses no data.
    written = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert written["providers"]["openai"]["openai_key"] == "sk-proj-UNMARKED-KEY"


def test_rollback_snapshot_never_previews_a_merge_target(tmp_path: Path) -> None:
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(_UNMARKED_CREDENTIAL_CONFIG, encoding="utf-8")

    change = _merge_change(target)
    overlay, _snapshot = _artifacts(tmp_path, [change])
    snapshot = create_setup_rollback_snapshot(overlay)

    blob = json.dumps(snapshot)
    for credential in ("sk-proj-UNMARKED-KEY", "sk-proj-UNMARKED-COOKIE"):
        assert credential not in blob, f"{credential} was copied into the rollback snapshot"

    state = snapshot["target_path_states"][0]
    assert state["prior_redacted_preview"] == _SNAPSHOT_PREVIEW_WITHHELD
    assert len(state["prior_content_digest"]) == 64, "the digest identifies the file without copying it"
    assert state["prior_content_size_bytes"] > 0
    assert validate_setup_rollback_snapshot_artifact(snapshot) == []


def test_a_validating_rollback_snapshot_can_never_restore_file_content(tmp_path: Path) -> None:
    """The structural contradiction underneath `restore_prior_file_from_snapshot`.

    `setup_rollback` validates a snapshot only if `raw_content_included` is **false**;
    `setup_rollback_execute._preflight_state` restores a file only if it is **true**. So every file
    rollback -- including a rollback of this Goose config merge -- degrades to manual restoration.

    This is not an oversight to route around. Storing the prior content would put the operator's API
    keys into a JSON artifact, which `secret_policy.raw_prior_content_stored_in_json = false`
    forbids on purpose. You cannot both refuse to store credentials and promise to restore a
    credential file. The promise is the part that is wrong, and until a secure content store exists
    the honest behaviour is exactly this refusal. This test exists so the contradiction cannot be
    silently "fixed" by weakening either side.
    """
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(_UNMARKED_CREDENTIAL_CONFIG, encoding="utf-8")

    change = _merge_change(target)
    overlay, _snapshot = _artifacts(tmp_path, [change])
    snapshot = create_setup_rollback_snapshot(overlay)
    assert validate_setup_rollback_snapshot_artifact(snapshot) == []

    state = snapshot["target_path_states"][0]
    assert state["prior_existence_state"] == "file"
    assert state["raw_content_included"] is False, "the validator forbids anything else"

    blocker = _preflight_state(target, state)
    assert blocker == "manual_restore_required: raw prior content is unavailable"


def test_the_validator_itself_refuses_a_snapshot_that_claims_raw_content(tmp_path: Path) -> None:
    """The half of the contradiction pin the test above cannot hold.

    The pin above drives only the honest builder, so it keeps failing if the *builder* starts
    embedding raw content -- but the cross-author audit proved by mutation that weakening the
    *validator* to accept `raw_content_included: true` left it (and the whole suite) green. That
    is exactly the quiet route around the contradiction: keep the builder honest today, loosen
    the validator, and let a later "fix" start emitting snapshots that promise restoration.

    So this test hands the validator a forged snapshot whose digest is recomputed -- the only
    thing wrong with it is the claim itself -- and requires the refusal to come from the
    validator. Forging the promise must require lying in the validator, not merely omitting a
    builder path.
    """
    from builder_ii.core.config_schema import attach_digest

    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(_UNMARKED_CREDENTIAL_CONFIG, encoding="utf-8")

    overlay, _snapshot = _artifacts(tmp_path, [_merge_change(target)])
    snapshot = create_setup_rollback_snapshot(overlay)
    assert validate_setup_rollback_snapshot_artifact(snapshot) == []

    forged = json.loads(json.dumps(snapshot))
    state = forged["target_path_states"][0]
    state["raw_content_included"] = True
    state["raw_prior_content"] = "operator_key: sk-proj-FORGED\n"
    forged = attach_digest(forged, digest_key="snapshot_digest")

    errors = validate_setup_rollback_snapshot_artifact(forged)
    assert any("raw_content_included" in error for error in errors), (
        "the validator accepted a snapshot claiming raw prior content; the rollback "
        "contradiction can now be 'fixed' by weakening exactly this check"
    )


def test_replace_of_an_operator_owned_file_also_withholds_the_preview(tmp_path: Path) -> None:
    """The hole the first cut of this guard left open, proven and closed.

    The withholding fired only on `operation == "merge"`, so a `replace` of the very same Goose
    config previewed it and marker redaction let `openai_key` straight through. What decides the
    question is *whose file it is*, not what we are about to do to it.
    """
    target = tmp_path / "config" / "goose" / "config.yaml"
    target.parent.mkdir(parents=True)
    target.write_text(_UNMARKED_CREDENTIAL_CONFIG, encoding="utf-8")

    change = _merge_change(target)
    change["operation_type"] = "replace"
    overlay, _snapshot = _artifacts(tmp_path, [change])
    snapshot = create_setup_rollback_snapshot(overlay)

    blob = json.dumps(snapshot)
    assert "sk-proj-UNMARKED-KEY" not in blob, "a replace of an operator-owned file leaked a credential"
    state = snapshot["target_path_states"][0]
    assert state["prior_redacted_preview"] == _SNAPSHOT_PREVIEW_WITHHELD
    assert len(state["prior_content_digest"]) == 64
    assert validate_setup_rollback_snapshot_artifact(snapshot) == []


def test_builder_owned_files_keep_their_line_redacted_preview(tmp_path: Path) -> None:
    """The withholding must not swallow previews of files builder-II itself authored.

    `tests/test_setup_rollback.py` pins that a prior `.env` inside the target repo still shows
    `BUILDER_MODEL_API_TOKEN=<redacted>`. That preview is useful and safe; only operator-owned config
    is withheld. If this ever starts withholding, the discriminator has gone too wide.
    """
    from builder_ii.lifecycle.setup.setup_rollback import _is_operator_owned

    operator_change = {"inside_user_config_dir": True}
    builder_change = {"inside_user_config_dir": False}
    assert _is_operator_owned(operator_change, "replace") is True
    assert _is_operator_owned(operator_change, "merge") is True
    assert _is_operator_owned(builder_change, "merge") is True, "merge targets are operator-owned by construction"
    assert _is_operator_owned(builder_change, "replace") is False
    assert _is_operator_owned(builder_change, "create") is False
