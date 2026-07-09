from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY, get_command_record
from builder_ii.orchestration_lane_policy import (
    LANE_POLICY_KIND,
    LANE_POLICY_ROWS,
    LANE_POLICY_SCHEMA_VERSION,
    OBLIGATION_KINDS,
    LanePolicyViolation,
    check_command_discharge_mechanism_registered,
    create_orchestration_lane_policy_artifact,
    discharge_mechanisms_for_obligation_kind,
    dumps_orchestration_lane_policy_artifact,
    lane_for_obligation_kind,
    require_lane_match,
    validate_discharge_mechanisms_against_registry,
    validate_orchestration_lane_policy_artifact,
    validate_orchestration_lane_policy_artifact_file,
    write_orchestration_lane_policy_artifact,
)

EXPECTED_TABLE = {
    "planning_step": "deepagents",
    "interactive_ops": "goose",
    "model_call": "gateway",
    "mutation": "hitl_patch",
    "verification": "verify",
}


# --- Totality -----------------------------------------------------------------------------


def test_totality_every_obligation_kind_has_exactly_one_row() -> None:
    kinds = [row["obligation_kind"] for row in LANE_POLICY_ROWS]
    assert set(kinds) == set(EXPECTED_TABLE)
    assert len(kinds) == len(set(kinds)), "no obligation_kind may appear in more than one row"
    assert tuple(kinds) == OBLIGATION_KINDS


def test_totality_matches_plan_table_exactly() -> None:
    rendered = {row["obligation_kind"]: row["lane"] for row in LANE_POLICY_ROWS}
    assert rendered == EXPECTED_TABLE


@pytest.mark.parametrize("obligation_kind,expected_lane", list(EXPECTED_TABLE.items()))
def test_lane_for_obligation_kind_matches_plan(obligation_kind: str, expected_lane: str) -> None:
    assert lane_for_obligation_kind(obligation_kind) == expected_lane


def test_lane_for_unknown_obligation_kind_raises_named_error() -> None:
    with pytest.raises(LanePolicyViolation) as excinfo:
        lane_for_obligation_kind("not_a_real_kind")
    assert "not_a_real_kind" in str(excinfo.value)


def test_discharge_mechanisms_for_obligation_kind_non_empty_for_all_kinds() -> None:
    for obligation_kind in OBLIGATION_KINDS:
        mechanisms = discharge_mechanisms_for_obligation_kind(obligation_kind)
        assert mechanisms, f"{obligation_kind} must have at least one discharge mechanism"
        for mechanism in mechanisms:
            assert mechanism["mechanism_kind"] in ("command", "artifact")
            assert mechanism["mechanism"]


# --- Collision refusal ----------------------------------------------------------------------


def test_collision_refusal_yields_named_error_not_first_adapter_wins() -> None:
    # interactive_ops belongs to lane "goose"; attempting to resolve/mint it under lane
    # "deepagents" (a lane != policy pairing) must be refused with a NAMED error identifying
    # both the offending and the expected lane -- never silently resolved.
    with pytest.raises(LanePolicyViolation) as excinfo:
        require_lane_match("interactive_ops", "deepagents")
    message = str(excinfo.value)
    assert "interactive_ops" in message
    assert "goose" in message  # the expected lane
    assert "deepagents" in message  # the refused, mismatched lane


def test_collision_refusal_error_type_is_specific() -> None:
    # The error must be a specifically named LanePolicyViolation, not a generic
    # KeyError/ValueError/Exception that would blur "policy refusal" with "programming bug".
    with pytest.raises(LanePolicyViolation):
        require_lane_match("mutation", "goose")


def test_require_lane_match_passes_for_correct_pairing() -> None:
    for obligation_kind, lane in EXPECTED_TABLE.items():
        require_lane_match(obligation_kind, lane)  # must not raise


# --- Registry linkage -----------------------------------------------------------------------


def test_command_form_discharge_mechanisms_resolve_in_registry() -> None:
    errors = validate_discharge_mechanisms_against_registry()
    assert errors == []


def test_planning_step_and_mutation_command_mechanisms_are_registered() -> None:
    assert get_command_record("builder-deepagents run-approved") is not None
    assert get_command_record("builder-hitl apply-patch") is not None


def test_bogus_command_name_is_reported_as_unregistered() -> None:
    error = check_command_discharge_mechanism_registered("builder-totally-bogus not-a-command")
    assert error is not None
    assert "unregistered" in error
    assert "builder-totally-bogus not-a-command" in error


def test_registered_command_returns_no_error() -> None:
    assert check_command_discharge_mechanism_registered("builder-deepagents run-approved") is None


def test_command_authority_registry_is_nonempty_sanity() -> None:
    # Sanity check that we are checking against the live registry, not an empty stand-in.
    assert len(COMMAND_AUTHORITY_REGISTRY) > 0


# --- Artifact create/dumps/write/validate ----------------------------------------------------


def test_create_artifact_shape() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    assert artifact["kind"] == LANE_POLICY_KIND
    assert artifact["schema_version"] == LANE_POLICY_SCHEMA_VERSION
    assert artifact["obligation_kinds"] == list(OBLIGATION_KINDS)
    assert {row["obligation_kind"] for row in artifact["lanes"]} == set(EXPECTED_TABLE)
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_orchestration_lane_policy_artifact(artifact) == []


def test_validate_rejects_non_object() -> None:
    assert validate_orchestration_lane_policy_artifact(None) != []
    assert validate_orchestration_lane_policy_artifact("not a dict") != []
    assert validate_orchestration_lane_policy_artifact([1, 2, 3]) != []


def test_validate_rejects_wrong_kind_and_schema_version() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    bad_kind = dict(artifact)
    bad_kind["kind"] = "builder_ii.something_else"
    assert any("kind must be" in e for e in validate_orchestration_lane_policy_artifact(bad_kind))

    bad_version = dict(artifact)
    bad_version["schema_version"] = 99
    assert any("schema_version" in e for e in validate_orchestration_lane_policy_artifact(bad_version))


def test_validate_rejects_missing_obligation_kind_totality_violation() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    mutated = copy.deepcopy(artifact)
    mutated["lanes"] = [row for row in mutated["lanes"] if row["obligation_kind"] != "mutation"]
    errors = validate_orchestration_lane_policy_artifact(mutated)
    assert any("totality violation" in e for e in errors)


def test_validate_rejects_duplicate_obligation_kind() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    mutated = copy.deepcopy(artifact)
    duplicate_row = copy.deepcopy(mutated["lanes"][0])
    mutated["lanes"].append(duplicate_row)
    errors = validate_orchestration_lane_policy_artifact(mutated)
    assert any("duplicated" in e for e in errors)


def test_validate_rejects_bad_mechanism_kind() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    mutated = copy.deepcopy(artifact)
    mutated["lanes"][0]["discharge_mechanisms"][0]["mechanism_kind"] = "carrier_pigeon"
    errors = validate_orchestration_lane_policy_artifact(mutated)
    assert any("mechanism_kind" in e for e in errors)


def test_dumps_is_stable_json_with_trailing_newline() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    text = dumps_orchestration_lane_policy_artifact(artifact)
    assert text.endswith("\n")
    assert json.loads(text) == artifact


def test_write_and_validate_file_roundtrip(tmp_path: Path) -> None:
    artifact = create_orchestration_lane_policy_artifact()
    output = tmp_path / "lane-policy.json"
    write_orchestration_lane_policy_artifact(artifact, output)
    assert validate_orchestration_lane_policy_artifact_file(output) == []


def test_validate_file_missing_file() -> None:
    errors = validate_orchestration_lane_policy_artifact_file(Path("/nonexistent/lane-policy.json"))
    assert any("file not found" in e for e in errors)


def test_validate_file_invalid_json(tmp_path: Path) -> None:
    output = tmp_path / "bad.json"
    output.write_text("{not valid json", encoding="utf-8")
    errors = validate_orchestration_lane_policy_artifact_file(output)
    assert any("invalid JSON" in e for e in errors)


# --- Digest stability -------------------------------------------------------------------------


def test_digest_stability_across_renders() -> None:
    first = create_orchestration_lane_policy_artifact()
    second = create_orchestration_lane_policy_artifact()
    assert first["lane_policy_digest"] == second["lane_policy_digest"]
    assert len(first["lane_policy_digest"]) == 64


def test_digest_changes_when_table_changes_shape() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    tampered = copy.deepcopy(artifact)
    tampered["lanes"][0]["lane"] = "not-the-real-lane"
    errors = validate_orchestration_lane_policy_artifact(tampered)
    assert any("lane_policy_digest does not match" in e for e in errors)


def test_digest_tamper_detection_on_digest_field_itself() -> None:
    artifact = create_orchestration_lane_policy_artifact()
    tampered = dict(artifact)
    tampered["lane_policy_digest"] = "0" * 64
    errors = validate_orchestration_lane_policy_artifact(tampered)
    assert any("lane_policy_digest does not match" in e for e in errors)
