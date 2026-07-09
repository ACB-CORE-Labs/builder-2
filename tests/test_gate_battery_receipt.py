from __future__ import annotations

import json
from pathlib import Path

from builder_ii.gate_battery_receipt import (
    GATE_BATTERY_RECEIPT_KIND,
    build_gate_battery_receipt,
    dumps_gate_battery_receipt,
    find_absolute_paths,
    gate_record_for_run,
    gate_record_for_skip,
    main,
    validate_gate_battery_receipt,
    validate_gate_battery_receipt_file,
    write_gate_battery_receipt,
)

_SHA_A = "a" * 40
_SHA_B = "b" * 40


def _passed_gate(name: str = "gate one") -> dict:
    return gate_record_for_run(name, ["cmd", "--flag"], 0, 3)


def _failed_gate(name: str = "gate two") -> dict:
    return gate_record_for_run(name, ["cmd", "--flag"], 7, 1)


def _skipped_gate(name: str = "gate three") -> dict:
    return gate_record_for_skip(name, "tool not found on PATH")


def _receipt(**overrides) -> dict:
    kwargs = dict(
        gates=[_passed_gate()],
        head_sha_before=_SHA_A,
        head_sha_after=_SHA_A,
        working_tree_clean=True,
        cargo_present=True,
        generated_at="2026-07-09T00:00:00+00:00",
    )
    kwargs.update(overrides)
    return build_gate_battery_receipt(**kwargs)


# --- round-trip: build(...) always produces a receipt validate(...) accepts -------------------


def test_round_trip_passed_battery() -> None:
    receipt = _receipt(gates=[_passed_gate("a"), _passed_gate("b")])
    assert receipt["kind"] == GATE_BATTERY_RECEIPT_KIND
    assert receipt["overall_state"] == "PASSED"
    assert receipt["valid"] is True
    assert receipt["errors"] == []
    assert validate_gate_battery_receipt(receipt) == []


def test_round_trip_failed_battery() -> None:
    receipt = _receipt(gates=[_passed_gate("a"), _failed_gate("b")])
    assert receipt["overall_state"] == "FAILED"
    assert receipt["valid"] is True
    assert validate_gate_battery_receipt(receipt) == []


def test_round_trip_battery_with_skips() -> None:
    receipt = _receipt(gates=[_passed_gate("a"), _skipped_gate("b")])
    assert receipt["overall_state"] == "PASSED"
    assert receipt["skipped"] == ["b"]
    assert validate_gate_battery_receipt(receipt) == []


# --- Ladder 8 lesson: absent is null, never 0/""/[] ---------------------------------------------


def test_skipped_gate_has_null_not_zero_or_empty() -> None:
    record = gate_record_for_skip("cargo build", "cargo not found on PATH")
    assert record["exit_code"] is None
    assert record["duration_seconds"] is None
    assert record["argv"] is None
    assert record["skip_reason"] == "cargo not found on PATH"
    assert record["status"] == "SKIPPED"


def test_executed_gate_never_has_null_argv_or_duration() -> None:
    record = gate_record_for_run("pytest", ["pytest"], 0, 12)
    assert record["argv"] == ["pytest"]
    assert record["duration_seconds"] == 12
    assert record["skip_reason"] is None


# --- cross-field rules: status <-> exit_code/skip_reason/argv/duration, both directions --------


def test_skipped_with_nonnull_exit_code_rejected() -> None:
    receipt = _receipt(gates=[{**_skipped_gate(), "exit_code": 0}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("exit_code" in e and "SKIPPED" in e for e in errors)


def test_skipped_with_empty_skip_reason_rejected() -> None:
    receipt = _receipt(gates=[{**_skipped_gate(), "skip_reason": ""}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("skip_reason" in e for e in errors)


def test_skipped_with_argv_rejected() -> None:
    receipt = _receipt(gates=[{**_skipped_gate(), "argv": ["cargo"]}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("argv" in e and "SKIPPED" in e for e in errors)


def test_passed_with_nonzero_exit_code_rejected() -> None:
    receipt = _receipt(gates=[{**_passed_gate(), "exit_code": 1}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("exit_code" in e and "PASSED" in e for e in errors)


def test_passed_with_skip_reason_rejected() -> None:
    receipt = _receipt(gates=[{**_passed_gate(), "skip_reason": "should not be here"}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("skip_reason" in e for e in errors)


def test_failed_with_zero_exit_code_rejected() -> None:
    receipt = _receipt(gates=[{**_failed_gate(), "exit_code": 0}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("exit_code" in e and "FAILED" in e for e in errors)


def test_executed_gate_missing_argv_rejected() -> None:
    receipt = _receipt(gates=[{**_passed_gate(), "argv": None}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("argv" in e for e in errors)


def test_executed_gate_negative_duration_rejected() -> None:
    receipt = _receipt(gates=[{**_passed_gate(), "duration_seconds": -1}])
    errors = validate_gate_battery_receipt(receipt)
    assert any("duration_seconds" in e for e in errors)


# --- overall_state <-> any gate FAILED, both directions -----------------------------------------


def test_overall_state_passed_with_a_failed_gate_rejected() -> None:
    receipt = _receipt(gates=[_failed_gate()])
    receipt["overall_state"] = "PASSED"
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("overall_state" in e for e in errors)


def test_overall_state_failed_with_no_failed_gate_rejected() -> None:
    receipt = _receipt(gates=[_passed_gate()])
    receipt["overall_state"] = "FAILED"
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("overall_state" in e for e in errors)


def _resign(receipt: dict) -> dict:
    from builder_ii.config_schema import attach_digest

    return attach_digest(receipt, digest_key="gate_battery_receipt_digest")


# --- skipped[] must be exactly {gate.name : status == SKIPPED} ---------------------------------


def test_skipped_list_missing_a_name_rejected() -> None:
    receipt = _receipt(gates=[_skipped_gate("a")])
    receipt["skipped"] = []
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("skipped" in e for e in errors)


def test_skipped_list_with_extra_name_rejected() -> None:
    receipt = _receipt(gates=[_passed_gate("a")])
    receipt["skipped"] = ["a"]
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("skipped" in e for e in errors)


# --- head_sha_stable <-> head_sha_before == head_sha_after, both directions --------------------


def test_head_sha_stable_claimed_true_when_shas_differ_rejected() -> None:
    receipt = _receipt(head_sha_before=_SHA_A, head_sha_after=_SHA_B)
    receipt["head_sha_stable"] = True
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("head_sha_stable" in e for e in errors)


def test_head_sha_stable_claimed_false_when_shas_match_rejected() -> None:
    receipt = _receipt(head_sha_before=_SHA_A, head_sha_after=_SHA_A)
    receipt["head_sha_stable"] = False
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("head_sha_stable" in e for e in errors)


def test_moved_head_yields_unstable() -> None:
    receipt = _receipt(head_sha_before=_SHA_A, head_sha_after=_SHA_B)
    assert receipt["head_sha_stable"] is False
    assert validate_gate_battery_receipt(receipt) == []


def test_unknown_head_sha_before_yields_unstable_not_a_fabricated_true() -> None:
    # Capture failure degrades to None, never to a claim of stability we cannot back.
    receipt = _receipt(head_sha_before=None, head_sha_after=None)
    assert receipt["head_sha_stable"] is False
    assert validate_gate_battery_receipt(receipt) == []


# --- dirty tree does not invalidate a receipt; it is recorded honestly -------------------------


def test_dirty_tree_still_produces_a_valid_receipt() -> None:
    receipt = _receipt(working_tree_clean=False)
    assert receipt["working_tree_clean"] is False
    assert receipt["valid"] is True
    assert validate_gate_battery_receipt(receipt) == []


# --- governance: artifact_is_authority / independent_observer / merge_authority ----------------


def test_governance_block_pinned() -> None:
    receipt = _receipt()
    assert receipt["governance"] == {
        "artifact_is_authority": False,
        "independent_observer": False,
        "merge_authority": "operator",
    }


def test_governance_artifact_is_authority_true_rejected() -> None:
    receipt = _receipt()
    receipt["governance"]["artifact_is_authority"] = True
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("artifact_is_authority" in e for e in errors)


def test_governance_independent_observer_true_rejected() -> None:
    receipt = _receipt()
    receipt["governance"]["independent_observer"] = True
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("independent_observer" in e for e in errors)


def test_governance_merge_authority_not_operator_rejected() -> None:
    receipt = _receipt()
    receipt["governance"]["merge_authority"] = "agent"
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("merge_authority" in e for e in errors)


# --- covered_gates is a fixed literal: gitleaks is advisory and out of scope --------------------


def test_covered_gates_is_blocking() -> None:
    receipt = _receipt()
    assert receipt["covered_gates"] == "blocking"


def test_covered_gates_wrong_value_rejected() -> None:
    receipt = _receipt()
    receipt["covered_gates"] = "all"
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("covered_gates" in e for e in errors)


# --- digest drift ---------------------------------------------------------------------------


def test_digest_drift_detected() -> None:
    receipt = _receipt()
    receipt["overall_state"] = "FAILED"  # mutate without re-signing
    errors = validate_gate_battery_receipt(receipt)
    assert any("digest" in e and "drift" in e for e in errors)


def test_hand_edited_receipt_cannot_flip_failed_gate_to_overall_passed() -> None:
    """A hand-edited receipt claiming PASSED while carrying a FAILED gate must not validate,
    even if someone also recomputes the digest over the forged payload."""
    receipt = _receipt(gates=[_failed_gate()])
    receipt["overall_state"] = "PASSED"
    receipt = _resign(receipt)  # forger recomputes the digest too
    errors = validate_gate_battery_receipt(receipt)
    assert errors  # digest matches, but the cross-field rule still catches the forgery
    assert any("overall_state" in e for e in errors)


# --- no absolute paths anywhere in the emitted JSON --------------------------------------------


def test_clean_receipt_has_no_absolute_paths() -> None:
    receipt = _receipt(gates=[_passed_gate(), _skipped_gate()])
    assert find_absolute_paths(receipt) == []
    assert validate_gate_battery_receipt(receipt) == []


def test_leaked_absolute_path_in_argv_rejected() -> None:
    poisoned = gate_record_for_run("rust validator build", ["cargo", "/Users/dev/.venv/bin/python3"], 0, 1)
    receipt = _receipt(gates=[poisoned])
    errors = validate_gate_battery_receipt(receipt)
    assert any("absolute path" in e for e in errors)


def test_leaked_absolute_path_in_skip_reason_rejected() -> None:
    poisoned = gate_record_for_skip("rust validator build", "/Users/dev/.cargo/bin not on PATH")
    receipt = _receipt(gates=[poisoned])
    errors = validate_gate_battery_receipt(receipt)
    assert any("absolute path" in e for e in errors)


def test_find_absolute_paths_ignores_relative_and_hex_strings() -> None:
    assert find_absolute_paths("builder_ii_validation_rs/Cargo.toml") == []
    assert find_absolute_paths("a" * 64) == []
    assert find_absolute_paths({"a": ["fine", "/nope"]}) == ["$.a[1]"]


# --- file round-trip -------------------------------------------------------------------------


def test_write_and_validate_file_round_trip(tmp_path: Path) -> None:
    receipt = _receipt(gates=[_passed_gate(), _failed_gate(), _skipped_gate()])
    output = tmp_path / "receipt.json"
    write_gate_battery_receipt(receipt, output)
    assert validate_gate_battery_receipt_file(output) == []
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    assert reloaded == receipt


def test_dumps_is_stable_and_ends_with_newline() -> None:
    receipt = _receipt()
    text = dumps_gate_battery_receipt(receipt)
    assert text.endswith("\n")
    assert json.loads(text) == receipt


# --- gates[] structural rules --------------------------------------------------------------


def test_empty_gates_list_rejected() -> None:
    receipt = _receipt()
    receipt["gates"] = []
    receipt = _resign(receipt)
    errors = validate_gate_battery_receipt(receipt)
    assert any("gates" in e for e in errors)


def test_duplicate_gate_names_rejected() -> None:
    receipt = _receipt(gates=[_passed_gate("dup"), _failed_gate("dup")])
    errors = validate_gate_battery_receipt(receipt)
    assert any("unique" in e for e in errors)


def test_not_a_dict_rejected() -> None:
    assert validate_gate_battery_receipt(["not", "a", "dict"]) == [
        "gate battery receipt artifact must be a JSON object"
    ]


# --- CLI: record-gate / build / --validate -----------------------------------------------------


def test_cli_record_gate_and_build_round_trip(tmp_path: Path) -> None:
    log = tmp_path / "gates.jsonl"
    output = tmp_path / "receipt.json"
    assert main(["record-gate", "--log", str(log), "--name", "a", "--exit-code", "0", "--duration", "2", "--", "true"]) == 0
    assert main(["record-gate", "--log", str(log), "--name", "b", "--skip-reason", "no tool"]) == 0
    rc = main(
        [
            "build",
            "--gate-log",
            str(log),
            "--output",
            str(output),
            "--head-sha-before",
            _SHA_A,
            "--head-sha-after",
            _SHA_A,
            "--working-tree-clean",
            "true",
        ]
    )
    assert rc == 0
    assert validate_gate_battery_receipt_file(output) == []
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["overall_state"] == "PASSED"
    assert data["skipped"] == ["b"]

    assert main(["--validate", str(output)]) == 0


def test_cli_build_with_empty_head_shas_becomes_null(tmp_path: Path) -> None:
    log = tmp_path / "gates.jsonl"
    output = tmp_path / "receipt.json"
    main(["record-gate", "--log", str(log), "--name", "a", "--exit-code", "0", "--duration", "1", "--", "true"])
    main(
        [
            "build",
            "--gate-log",
            str(log),
            "--output",
            str(output),
            "--head-sha-before",
            "",
            "--head-sha-after",
            "",
            "--working-tree-clean",
            "false",
        ]
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["head_sha_before"] is None
    assert data["head_sha_after"] is None
    assert data["head_sha_stable"] is False
    assert data["working_tree_clean"] is False


def test_cli_record_gate_rejects_mixing_skip_and_exit_code(tmp_path: Path) -> None:
    log = tmp_path / "gates.jsonl"
    rc = main(
        [
            "record-gate",
            "--log",
            str(log),
            "--name",
            "a",
            "--skip-reason",
            "x",
            "--exit-code",
            "0",
            "--duration",
            "1",
            "--",
            "true",
        ]
    )
    assert rc == 2


def test_cli_validate_reports_errors_for_invalid_file(tmp_path: Path) -> None:
    output = tmp_path / "bad.json"
    output.write_text("{}", encoding="utf-8")
    assert main(["--validate", str(output)]) == 1


def test_cli_unknown_verb_rejected() -> None:
    assert main(["bogus"]) == 2


def test_cli_no_args_rejected() -> None:
    assert main([]) == 2
