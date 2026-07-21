from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from builder_ii.core.config_schema import digest_jsonable
from builder_ii.core.orchestration_obligation import (
    BUDGET_FIELDS,
    DEFAULT_ROOT_MAX_HUMAN_GATES,
    OBLIGATION_KIND,
    OBLIGATION_SCHEMA_VERSION,
    create_orchestration_obligation,
    dumps_orchestration_obligation,
    fits_within,
    remaining,
    validate_orchestration_obligation,
    validate_orchestration_obligation_file,
    write_orchestration_obligation,
)

_SEAL_DIGEST = "a" * 64
_LANE_POLICY_DIGEST = "b" * 64
_PARENT_BUDGET: dict[str, int] = {
    "max_subagents": 4,
    "max_events": 100,
    "max_output_bytes": 10_000,
    "max_human_gates": DEFAULT_ROOT_MAX_HUMAN_GATES,
}


def _valid_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "lane": "deepagents",
        "obligation_kind": "planning_step",
        "task": "Draft the tree-profile plan for module X.",
        "output_contract_expected_kind": "builder_ii.deepagents_execution_receipt",
        "output_contract_required_evidence_kinds": ["builder_ii.verification_execution_receipt"],
        "denied_actions": ["execute_shell"],
        "refused_lanes": ["goose"],
        "file_refs": [{"path": "builder_ii/core/orchestration_obligation.py", "sha256": "c" * 64}],
        "briefing_bytes": 128,
        "budget_partition": {
            "max_subagents": 1,
            "max_events": 10,
            "max_output_bytes": 1_000,
            "max_human_gates": 1,
        },
        "parent_ref": {"seal_digest": _SEAL_DIGEST},
        "lane_policy_digest": _LANE_POLICY_DIGEST,
        "subagent_profile": "planner",
    }
    kwargs.update(overrides)
    return kwargs


def _valid_obligation(**overrides: Any) -> dict[str, Any]:
    return create_orchestration_obligation(**_valid_kwargs(**overrides))


def test_valid_obligation_round_trips_clean() -> None:
    obligation = _valid_obligation()
    assert obligation["kind"] == OBLIGATION_KIND
    assert obligation["schema_version"] == OBLIGATION_SCHEMA_VERSION
    assert validate_orchestration_obligation(obligation) == []


def test_dumps_and_write_round_trip(tmp_path: Path) -> None:
    obligation = _valid_obligation()
    text = dumps_orchestration_obligation(obligation)
    assert text.endswith("\n")
    assert json.loads(text) == obligation

    output = tmp_path / "obligation.json"
    write_orchestration_obligation(obligation, output)
    assert validate_orchestration_obligation_file(output) == []


def test_validate_file_missing() -> None:
    errors = validate_orchestration_obligation_file(Path("/nonexistent/does-not-exist.json"))
    assert any("file not found" in error for error in errors)


def test_validate_file_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    errors = validate_orchestration_obligation_file(bad)
    assert any("invalid JSON" in error for error in errors)


# --- anti-dump validation -----------------------------------------------------------------


def test_rejects_oversized_ref_field_value() -> None:
    obligation = _valid_obligation(
        file_refs=[{"path": "x" * (512 + 1), "sha256": "c" * 64}],
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("anti-dump bound" in error for error in errors)


def test_accepts_ref_field_value_at_exactly_the_bound() -> None:
    obligation = _valid_obligation(
        file_refs=[{"path": "x" * 512, "sha256": "c" * 64}],
    )
    errors = validate_orchestration_obligation(obligation)
    assert not any("anti-dump bound" in error for error in errors)


@pytest.mark.parametrize("forbidden_key", ["content", "body", "text"])
def test_rejects_smuggled_dump_key_at_top_level(forbidden_key: str) -> None:
    obligation = _valid_obligation(
        file_refs=[{"path": "a.py", "sha256": "c" * 64, forbidden_key: "smuggled payload"}],
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("forbidden key" in error for error in errors)


def test_rejects_smuggled_dump_key_nested_inside_a_ref() -> None:
    obligation = _valid_obligation(
        file_refs=[
            {
                "path": "a.py",
                "sha256": "c" * 64,
                "meta": {"nested": {"body": "smuggled payload nested two levels deep"}},
            }
        ],
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("forbidden key" in error and "meta.nested.body" in error for error in errors)


def test_rejects_smuggled_dump_key_inside_a_list() -> None:
    obligation = _valid_obligation(
        file_refs=[
            {
                "path": "a.py",
                "sha256": "c" * 64,
                "extra": [{"text": "smuggled payload inside a list"}],
            }
        ],
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("forbidden key" in error for error in errors)


# --- budget component (subset) failures -----------------------------------------------------


@pytest.mark.parametrize("field", BUDGET_FIELDS)
def test_fits_within_fails_when_a_single_component_exceeds_remaining(field: str) -> None:
    child = dict(_PARENT_BUDGET)
    child[field] = _PARENT_BUDGET[field] + 1
    assert fits_within(child, _PARENT_BUDGET) is False


def test_fits_within_true_when_child_exactly_equals_remaining() -> None:
    child = dict(_PARENT_BUDGET)
    assert fits_within(child, _PARENT_BUDGET) is True


def test_fits_within_fails_closed_on_negative_or_missing_child_component() -> None:
    child = dict(_PARENT_BUDGET)
    child["max_subagents"] = -1
    assert fits_within(child, _PARENT_BUDGET) is False

    incomplete = {k: v for k, v in _PARENT_BUDGET.items() if k != "max_events"}
    assert fits_within(incomplete, _PARENT_BUDGET) is False


# --- conservation: sum of minted children may not exceed the parent grant -------------------


def test_conservation_second_child_refused_once_sum_exceeds_parent() -> None:
    parent = {"max_subagents": 4, "max_events": 100, "max_output_bytes": 10_000, "max_human_gates": 2}
    first_child = {"max_subagents": 2, "max_events": 50, "max_output_bytes": 5_000, "max_human_gates": 1}
    second_child = {"max_subagents": 3, "max_events": 50, "max_output_bytes": 5_000, "max_human_gates": 1}

    assert fits_within(first_child, parent, []) is True
    assert fits_within(second_child, parent, [first_child]) is False

    rem_after_first = remaining(parent, [first_child])
    assert rem_after_first == {"max_subagents": 2, "max_events": 50, "max_output_bytes": 5_000, "max_human_gates": 1}


def test_conservation_no_refunds_unspent_child_grant_stays_committed() -> None:
    parent = {"max_subagents": 2, "max_events": 10, "max_output_bytes": 1_000, "max_human_gates": 1}
    minted_child = {"max_subagents": 2, "max_events": 0, "max_output_bytes": 0, "max_human_gates": 0}

    # even though minted_child spent nothing, its full grant is committed (no refunds in v1).
    rem = remaining(parent, [minted_child])
    assert rem["max_subagents"] == 0
    another_child = {"max_subagents": 1, "max_events": 0, "max_output_bytes": 0, "max_human_gates": 0}
    assert fits_within(another_child, parent, [minted_child]) is False


# --- human-gates check ------------------------------------------------------------------------


def test_human_gates_mint_time_ceiling_respects_root_default() -> None:
    parent = {"max_subagents": 8, "max_events": 256, "max_output_bytes": 65_536, "max_human_gates": DEFAULT_ROOT_MAX_HUMAN_GATES}
    within_budget = {"max_subagents": 1, "max_events": 1, "max_output_bytes": 1, "max_human_gates": DEFAULT_ROOT_MAX_HUMAN_GATES}
    over_budget = {"max_subagents": 1, "max_events": 1, "max_output_bytes": 1, "max_human_gates": DEFAULT_ROOT_MAX_HUMAN_GATES + 1}
    assert fits_within(within_budget, parent) is True
    assert fits_within(over_budget, parent) is False


# --- parent_ref XOR ----------------------------------------------------------------------------


def test_parent_ref_rejects_both_seal_and_obligation_digest() -> None:
    obligation = _valid_obligation(parent_ref={"seal_digest": _SEAL_DIGEST, "obligation_digest": "d" * 64})
    errors = validate_orchestration_obligation(obligation)
    assert any("exactly one of seal_digest or obligation_digest" in error for error in errors)


def test_parent_ref_rejects_neither_seal_nor_obligation_digest() -> None:
    obligation = _valid_obligation(parent_ref={})
    errors = validate_orchestration_obligation(obligation)
    assert any("exactly one of seal_digest or obligation_digest" in error for error in errors)


def test_parent_ref_accepts_seal_digest_only() -> None:
    obligation = _valid_obligation(parent_ref={"seal_digest": _SEAL_DIGEST})
    assert validate_orchestration_obligation(obligation) == []


def test_parent_ref_accepts_obligation_digest_only() -> None:
    obligation = _valid_obligation(parent_ref={"obligation_digest": "d" * 64})
    assert validate_orchestration_obligation(obligation) == []


def test_parent_ref_rejects_extra_keys() -> None:
    obligation = _valid_obligation(parent_ref={"seal_digest": _SEAL_DIGEST, "extra": "nope"})
    errors = validate_orchestration_obligation(obligation)
    assert any("must not contain extra keys" in error for error in errors)


# --- task length bound --------------------------------------------------------------------------


def test_task_at_max_length_is_valid() -> None:
    obligation = _valid_obligation(task="x" * 2000)
    assert validate_orchestration_obligation(obligation) == []


def test_task_over_max_length_is_rejected() -> None:
    obligation = _valid_obligation(task="x" * 2001)
    errors = validate_orchestration_obligation(obligation)
    assert any("task must be at most 2000 chars" in error for error in errors)


def test_task_empty_is_rejected() -> None:
    obligation = _valid_obligation(task="   ")
    errors = validate_orchestration_obligation(obligation)
    assert any("task must be a non-empty string" in error for error in errors)


# --- digest stability --------------------------------------------------------------------------


def test_same_content_produces_same_obligation_id() -> None:
    first = _valid_obligation()
    second = _valid_obligation()
    assert first["obligation_id"] == second["obligation_id"]


def test_obligation_id_is_stable_under_field_reordering() -> None:
    obligation = _valid_obligation()
    content = dict(obligation)
    content.pop("obligation_id")
    reordered = dict(reversed(list(content.items())))

    forward = digest_jsonable(content, digest_key="obligation_id")
    backward = digest_jsonable(reordered, digest_key="obligation_id")
    assert forward == backward == obligation["obligation_id"]


def test_obligation_id_mismatch_is_detected_as_tampered() -> None:
    obligation = _valid_obligation()
    tampered = dict(obligation)
    tampered["task"] = "a different task entirely"  # obligation_id no longer matches
    errors = validate_orchestration_obligation(tampered)
    assert any("does not match the canonical digest" in error for error in errors)


# --- other shape checks --------------------------------------------------------------------------


def test_rejects_unknown_lane() -> None:
    obligation = _valid_obligation(lane="not-a-real-lane")
    errors = validate_orchestration_obligation(obligation)
    assert any("lane must be one of" in error for error in errors)


def test_rejects_unknown_obligation_kind() -> None:
    obligation = _valid_obligation(obligation_kind="not-a-real-kind")
    errors = validate_orchestration_obligation(obligation)
    assert any("obligation_kind must be one of" in error for error in errors)


def test_rejects_negative_budget_component() -> None:
    obligation = _valid_obligation(
        budget_partition={"max_subagents": -1, "max_events": 1, "max_output_bytes": 1, "max_human_gates": 1}
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("budget_partition.max_subagents must be a non-negative integer" in error for error in errors)


def test_rejects_briefing_bytes_over_max_output_bytes() -> None:
    obligation = _valid_obligation(
        briefing_bytes=2_000,
        budget_partition={"max_subagents": 1, "max_events": 1, "max_output_bytes": 1_000, "max_human_gates": 1},
    )
    errors = validate_orchestration_obligation(obligation)
    assert any("briefing_bytes must be <= budget_partition.max_output_bytes" in error for error in errors)


def test_rejects_wrong_kind_and_schema_version() -> None:
    obligation = _valid_obligation()
    obligation["kind"] = "builder_ii.something_else"
    obligation["schema_version"] = 2
    errors = validate_orchestration_obligation(obligation)
    assert any("kind must be" in error for error in errors)
    assert any("schema_version must be" in error for error in errors)


def test_rejects_non_object_input() -> None:
    assert validate_orchestration_obligation(["not", "a", "dict"]) == [
        "orchestration obligation must be a JSON object"
    ]


def test_rejects_tampered_governance_block() -> None:
    obligation = _valid_obligation()
    obligation["governance"]["artifact_is_authority"] = True
    errors = validate_orchestration_obligation(obligation)
    assert any("artifact_is_authority" in error for error in errors)
