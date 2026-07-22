from __future__ import annotations

from pathlib import Path

from builder_ii.core.config_schema import attach_digest
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    REQUIRED_DISABLED_AUTHORITY,
    VERIFICATION_EXECUTION_PLAN_KIND,
    finalize_verification_execution_plan,
    validate_verification_execution_plan_artifact,
    validate_verification_execution_plan_file,
    write_verification_execution_plan,
)


def _sample_plan() -> dict:
    return finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )


def _resign(plan: dict) -> dict:
    return attach_digest(plan, digest_key="verification_execution_plan_digest")


def test_valid_plan_validates() -> None:
    plan = _sample_plan()
    assert plan["kind"] == VERIFICATION_EXECUTION_PLAN_KIND
    assert plan["valid"] is True
    assert plan["errors"] == []
    assert plan["plan_mode"] == "planned_only"
    assert plan["approval_required"] is True
    assert plan["execution_enabled"] is False
    assert plan["artifact_is_authority"] is False
    assert plan["disabled_authority"] == REQUIRED_DISABLED_AUTHORITY
    assert validate_verification_execution_plan_artifact(plan) == []


def test_builder_full_is_the_supported_b1_1_pair() -> None:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    assert validate_verification_execution_plan_artifact(plan) == []


def test_compatible_target_verification_pairs_validate() -> None:
    # B4.2 (plan 1.3): the lane now plans against generic/core targets, not builder-only.
    cases = [
        ("generic", "generic_basic"),
        ("core", "core_smoke"),
        ("core", "core_focused"),
        ("builder", "builder_fast"),
    ]
    for target_profile, verification_profile in cases:
        plan = finalize_verification_execution_plan(
            target_profile=target_profile,
            verification_profile=verification_profile,
            target_repo=".",
            artifact_root=".builder/verification",
            generated_at="2026-06-30T00:00:00+00:00",
        )
        assert plan["valid"] is True, (target_profile, verification_profile, plan["errors"])
        assert validate_verification_execution_plan_artifact(plan) == []


def test_generic_plan_defaults_to_pytest_full_only() -> None:
    plan = finalize_verification_execution_plan(
        target_profile="generic",
        verification_profile="generic_basic",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    # A non-builder target only runs its own suite; no builder-II self profiles are offered.
    assert [p["profile"] for p in plan["allowed_command_profiles"]] == ["pytest_full"]
    assert plan["allowed_command_profiles"][0]["command_profile_ref"] == "verification_profiles.generic_basic.pytest_full"
    assert [s["step_id"] for s in plan["planned_steps"]] == ["pytest_full"]


def test_incompatible_target_verification_pair_fails() -> None:
    for target_profile, verification_profile in [
        ("generic", "builder_full"),
        ("core", "generic_basic"),
        ("builder", "core_smoke"),
    ]:
        plan = finalize_verification_execution_plan(
            target_profile=target_profile,
            verification_profile=verification_profile,
            target_repo=".",
            artifact_root=".builder/verification",
            generated_at="2026-06-30T00:00:00+00:00",
        )
        errors = validate_verification_execution_plan_artifact(plan)
        assert any("is not compatible with" in error for error in errors), (target_profile, verification_profile)
        assert plan["valid"] is False


def test_mismatched_verification_profile_refs_fail() -> None:
    plan = _sample_plan()
    plan["verification_profile"] = "generic_basic"  # builder target + builder_full refs, generic_basic label
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("is not compatible with" in error for error in errors)
    assert any("command_profile_ref must begin with verification_profiles.generic_basic." in error for error in errors)


def test_digest_drift_fails() -> None:
    plan = _sample_plan()
    plan["target_repo"] = "/tmp/other"
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("digest" in error and "drift" in error for error in errors)


def test_execution_enabled_true_fails() -> None:
    plan = _sample_plan()
    plan["execution_enabled"] = True
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("execution_enabled must be false or NOT_AUTHORIZED" in error for error in errors)


def test_approval_required_false_fails() -> None:
    plan = _sample_plan()
    plan["approval_required"] = False
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("approval_required must be true" in error for error in errors)


def test_artifact_is_authority_true_fails() -> None:
    plan = _sample_plan()
    plan["artifact_is_authority"] = True
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("artifact_is_authority must be false or NOT_AUTHORIZED" in error for error in errors)


def test_missing_disabled_authority_fails() -> None:
    plan = _sample_plan()
    del plan["disabled_authority"]["arbitrary_shell"]
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("disabled_authority.arbitrary_shell" in error for error in errors)


def test_raw_shell_string_in_planned_step_fails() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["command"] = "pytest"
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("raw shell" in error for error in errors)


def test_raw_shell_string_in_description_fails() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["description"] = "uv run pytest"
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("raw shell string" in error for error in errors)


def test_shell_separator_in_step_field_fails() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["description"] = "Run tests && collect output"
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("forbidden shell separator" in error for error in errors)


def test_model_mcp_goose_deepagents_patch_overclaim_fails() -> None:
    cases = [
        "claim patch authority",
        "perform model execution",
        "invoke MCP tool",
        "start Goose runtime",
        "construct deepagents runtime",
    ]
    for text in cases:
        plan = _sample_plan()
        plan["planned_steps"][0]["description"] = text
        plan = _resign(plan)
        errors = validate_verification_execution_plan_artifact(plan)
        assert any("forbidden authority" in error for error in errors), text


def test_nested_list_execution_enabled_true_fails() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["metadata"] = {"execution_enabled": [True]}
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("execution_enabled[0] must not enable" in error for error in errors)


def test_nested_list_model_or_patch_authority_true_fails() -> None:
    for field in ("model_execution", "patch_authority"):
        plan = _sample_plan()
        plan["planned_steps"][0]["metadata"] = {field: [True]}
        plan = _resign(plan)
        errors = validate_verification_execution_plan_artifact(plan)
        assert any(f"{field}[0] must not enable" in error for error in errors)


def test_pytest_full_naming_invariant_holds() -> None:
    # The pytest lane must satisfy the runner's profile==step_id==ref-leaf invariant.
    plan = _sample_plan()
    step = next(step for step in plan["planned_steps"] if step["step_id"] == "pytest_full")
    assert step["profile"] == "pytest_full"
    assert step["command_profile_ref"] == "verification_profiles.builder_full.pytest_full"
    profile = next(p for p in plan["allowed_command_profiles"] if p["profile"] == "pytest_full")
    assert profile["command_profile_ref"] == "verification_profiles.builder_full.pytest_full"


def test_builder_full_command_profile_is_present() -> None:
    plan = _sample_plan()
    assert any(p["profile"] == "builder_full" for p in plan["allowed_command_profiles"])
    assert any(step["step_id"] == "builder_full" for step in plan["planned_steps"])


def test_every_profile_and_step_declares_a_bounded_timeout() -> None:
    plan = _sample_plan()
    for profile in plan["allowed_command_profiles"]:
        assert isinstance(profile["timeout_seconds"], int)
        assert 1 <= profile["timeout_seconds"] <= 1800
    for step in plan["planned_steps"]:
        assert 1 <= step["timeout_seconds"] <= 1800


def test_out_of_range_timeout_fails() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["timeout_seconds"] = 5000
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("timeout_seconds must be within" in error for error in errors)


def test_missing_timeout_fails() -> None:
    plan = _sample_plan()
    del plan["allowed_command_profiles"][0]["timeout_seconds"]
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("timeout_seconds must be an integer" in error for error in errors)


def test_boolean_timeout_is_rejected() -> None:
    plan = _sample_plan()
    plan["planned_steps"][0]["timeout_seconds"] = True
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("timeout_seconds must be an integer" in error for error in errors)


def test_file_validation_round_trip(tmp_path: Path) -> None:
    plan = _sample_plan()
    output = tmp_path / "verification-execution-plan.json"
    write_verification_execution_plan(plan, output)
    assert validate_verification_execution_plan_file(output) == []


def test_file_validation_directory_path_returns_clean_read_error(tmp_path: Path) -> None:
    errors = validate_verification_execution_plan_file(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("verification execution plan file could not be read:")


def test_isolation_policy_injection_is_rejected() -> None:
    plan = _sample_plan()
    plan["isolation_policy"] = {
        "kind": "builder_ii.verification_isolation_policy",
        "schema_version": 1,
        "backend": "docker",
        "image_ref": "python:3.12-slim",
        "mounts": [
            {"source": "/foo", "target": "/bar; sh -c 'echo pwn'"}
        ]
    }
    plan = _resign(plan)
    errors = validate_verification_execution_plan_artifact(plan)
    assert any("sh -c" in error for error in errors)

