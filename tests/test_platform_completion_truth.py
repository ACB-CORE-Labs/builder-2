import json
from pathlib import Path

import pytest
from builder_ii.platform_status_cli import platform_app
from typer.testing import CliRunner

from builder_ii.core.platform_completion_audit import (
    ALLOWED_STATE_LABELS,
    MERGED_BUT_NOT_OPERATIONAL,
    OPERATIONALLY_VERIFIED,
    PASSIVE_FOUNDATION,
    R1_CONFIG_ONBOARDING_CAPABILITIES,
    R1_OPERATOR_FLIPPED_CAPABILITIES,
    REQUIRED_CAPABILITIES,
    REQUIRED_CAPABILITY_ROWS,
    STALE_TRUTH_PHRASES,
    CapabilityRow,
    UnclassifiedCapabilityError,
    assurance_state_for_row,
    matrix_blocker_violations,
    render_human_summary,
    render_matrix_jsonable,
    validate_assurance_classification,
    validate_command_surfaces,
    validate_completion_matrix,
    validate_r1_config_onboarding_mapping,
)
from builder_ii.governance.authority import (
    COMMAND_AUTHORITY_REGISTRY,
    MODE_NONE,
    STATE_ENABLED,
    TIER_1,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import TARGET_CODE_EXECUTING_PROFILES

runner = CliRunner()


def test_matrix_blockers_are_truthful() -> None:
    assert not matrix_blocker_violations()
    truth_report = Path("docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md").read_text(encoding="utf-8")
    for phrase in STALE_TRUTH_PHRASES:
        assert phrase not in truth_report, f"stale phrase in truth report: {phrase}"

    # The hardening line's version of this test also pinned both setup rows at
    # OPERATIONALLY_VERIFIED -- a promotion this lineage has not taken. The registry enabling
    # `builder-setup apply`/`rollback` (true on both lineages, pinned below) does not promote the
    # capability rows: a command being invocable is not the capability being operationally
    # verified. Flipping these rows requires an R1 closure audit through
    # R1_OPERATOR_FLIPPED_CAPABILITIES, never a test edit.
    by_cap = {r.capability: r for r in REQUIRED_CAPABILITY_ROWS}
    assert by_cap["non-interactive setup/apply/validate"].state == MERGED_BUT_NOT_OPERATIONAL
    assert by_cap["setup receipt + rollback artifact"].state == PASSIVE_FOUNDATION

    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    assert by_name["builder-setup apply"].promotion_state == STATE_ENABLED
    assert by_name["builder-setup rollback"].promotion_state == STATE_ENABLED


def test_all_required_capability_rows_exist_once() -> None:
    capabilities = [row.capability for row in REQUIRED_CAPABILITY_ROWS]
    assert set(capabilities) == set(REQUIRED_CAPABILITIES)
    assert len(capabilities) == len(set(capabilities))


def test_all_state_labels_are_valid_and_single_valued() -> None:
    allowed = set(ALLOWED_STATE_LABELS)
    for row in REQUIRED_CAPABILITY_ROWS:
        assert row.state in allowed
        assert isinstance(row.state, str)


def test_rows_have_evidence_tests_blockers_and_next_pr() -> None:
    errors = validate_completion_matrix(Path("."))
    assert not errors


def test_config_onboarding_rows_exist_and_point_to_r1() -> None:
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}
    for capability in R1_CONFIG_ONBOARDING_CAPABILITIES:
        assert capability in by_capability
        if capability in R1_OPERATOR_FLIPPED_CAPABILITIES:
            # 2.6 R1 closure flip (docs/audits/R1_CLOSURE_AUDIT_2_6.md): flipped rows are the
            # audited exception; every other R1 row keeps the fail-closed rule below.
            assert by_capability[capability].state == OPERATIONALLY_VERIFIED
            continue
        assert by_capability[capability].next_pr == "R1"
        assert by_capability[capability].state != OPERATIONALLY_VERIFIED
    assert not validate_r1_config_onboarding_mapping()


def test_r1_3a_matrix_state_changes_are_scoped() -> None:
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}

    assert by_capability["config schema"].state == PASSIVE_FOUNDATION
    assert by_capability["config source precedence"].state == PASSIVE_FOUNDATION
    assert by_capability["non-interactive setup/apply/validate"].state == MERGED_BUT_NOT_OPERATIONAL
    assert by_capability["Goose config overlay/rollback"].state == PASSIVE_FOUNDATION
    # 2.6 R1 closure flip: builder init unified orchestrator (plan item 2.2) made the wizard
    # operational — evidence in docs/audits/R1_CLOSURE_AUDIT_2_6.md.
    assert by_capability["interactive setup wizard"].state == ("OPERATIONALLY" + "_VERIFIED")
    assert by_capability["setup receipt + rollback artifact"].state == PASSIVE_FOUNDATION
    assert by_capability["skill generator/installer/validator"].state == MERGED_BUT_NOT_OPERATIONAL
    assert by_capability["artifact memory"].state == PASSIVE_FOUNDATION
    # B2 verifies rollback execution and patch apply
    # assert by_capability["rollback execution"].state != OPERATIONALLY_VERIFIED
    assert by_capability["HITL-approved verification execution"].state == ("OPERATIONALLY" + "_VERIFIED")
    assert any(
        "platform_status and docs_audit" in blocker
        for blocker in by_capability["HITL-approved verification execution"].blockers
    )
    assert by_capability["model registry"].state == OPERATIONALLY_VERIFIED


def test_matrix_command_names_are_registered_where_applicable() -> None:
    registry_names = {record.name for record in COMMAND_AUTHORITY_REGISTRY}
    assert not validate_command_surfaces(registry_names)


def test_builder_platform_commands_are_registered_as_tier1_validation_only() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    for name in (
        "builder-platform",
        "builder-platform matrix",
        "builder-platform status",
        "builder-platform audit-docs",
        "builder-platform validate-r1-closure",
    ):
        record = by_name[name]
        assert record.tier == TIER_1
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_state_writes
        assert not record.allows_external_tool_invocation
        assert not record.allows_artifact_writes

    r1_record = by_name["builder-platform r1-closure"]
    assert r1_record.tier == TIER_1
    assert r1_record.approval_mode == MODE_NONE
    assert not r1_record.allows_runtime_start
    assert not r1_record.allows_model_execution
    assert not r1_record.allows_shell_execution
    assert not r1_record.allows_source_writes
    assert not r1_record.allows_memory_mutation
    assert not r1_record.allows_git_mutation
    assert not r1_record.allows_state_writes
    assert not r1_record.allows_external_tool_invocation
    assert r1_record.allows_artifact_writes


def test_builder_memory_commands_are_registered_as_tier1_artifact_or_validation_only() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    for name in (
        "builder-memory",
        "builder-memory atom",
        "builder-memory index",
        "builder-memory search",
        "builder-memory reconstruct",
        "builder-memory validate-atom",
        "builder-memory validate-index",
        "builder-memory validate-reconstruction",
        "builder-memory validate-search-result",
    ):
        record = by_name[name]
        assert record.tier == TIER_1
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_state_writes
        assert not record.allows_external_tool_invocation

    assert by_name["builder-memory"].allows_artifact_writes is False
    for name in (
        "builder-memory atom",
        "builder-memory index",
        "builder-memory search",
        "builder-memory reconstruct",
    ):
        assert by_name[name].allows_artifact_writes is True


def test_matrix_rendering_is_json_safe() -> None:
    matrix = render_matrix_jsonable()
    encoded = json.dumps(matrix, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["kind"] == "builder_ii.platform_completion_matrix"
    assert decoded["summary"]["operationally_incomplete"] is True
    assert (
        decoded["summary"]["operationally_verified_count"] == 19
    )  # B4 (plan item 1.7) promoted operator-invoked HITL patch application + rollback execution (docs/audits/B4_CLOSURE_AUDIT.md); 2.6 promoted the interactive setup wizard (docs/audits/R1_CLOSURE_AUDIT_2_6.md); Ladder 4 PR-8 promoted governed obligation delegation, protocol_fake scope (docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md)


def test_matrix_exposes_sharper_assurance_states() -> None:
    matrix = render_matrix_jsonable()
    rows = {row["capability"]: row for row in matrix["capabilities"]}
    assert "SAFETY_CRITICAL_PROHIBITED" in matrix["allowed_assurance_states"]
    assert rows["model/provider execution"]["assurance_state"] == "LIVE_PROVIDER_VERIFIED"
    assert rows["HITL patch application"]["assurance_state"] == "MUTATION_WITH_ROLLBACK_VERIFIED"
    assert rows["rollback execution"]["assurance_state"] == "MUTATION_WITH_ROLLBACK_VERIFIED"
    assert rows["governed read-only runtime"]["assurance_state"] == "READ_ONLY_RUNTIME_VERIFIED"
    assert rows["governed demo loop"]["assurance_state"] == "DEMO_ONLY_VERIFIED"
    # Ladder 4 PR-8 closure flip (docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md): bounded
    # execution over protocol_fake — never LIVE_*, never a native-backend claim.
    assert rows["governed obligation delegation"]["assurance_state"] == "BOUNDED_EXECUTION_VERIFIED"
    # Same trunk, same module, same envelope as the delegation row above. It read PASSIVE only
    # because it rode the old fall-through default.
    assert rows["deepagents runtime/subagents"]["assurance_state"] == "BOUNDED_EXECUTION_VERIFIED"
    # Ladder 9 assurance flip (docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md): the one lane that
    # spawns a subprocess. Bounded describes the envelope of the invocation, never the behaviour of
    # what ran inside it. Scoped to platform_status + docs_audit; the count does not move.
    assert rows["HITL-approved verification execution"]["assurance_state"] == "BOUNDED_EXECUTION_VERIFIED"
    assert rows["interactive setup wizard"]["assurance_state"] == "PASSIVE_ARTIFACT_VERIFIED"
    assert rows["command authority as runtime gate"]["assurance_state"] == "PASSIVE_ARTIFACT_VERIFIED"
    # Reads `receipt["postflight_git_state"]` and compares fingerprints. The `git status` that
    # captured it belongs to run-approved, i.e. to the row promoted just above.
    assert rows["postflight verification"]["assurance_state"] == "PASSIVE_ARTIFACT_VERIFIED"


def test_the_ladder9_flip_is_scoped_to_the_two_profiles_that_never_run_target_code() -> None:
    """Promoting the envelope must not quietly promote pytest_full/builder_full with it.

    Those two execute the target repository's own suite and sit behind the D7 execution-risk
    acknowledgement. The row's blocker sentence names the scope, and the runner's own constant
    names the profiles that are outside it -- both must keep saying the same thing.
    """
    row = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}["HITL-approved verification execution"]

    assert assurance_state_for_row(row) == "BOUNDED_EXECUTION_VERIFIED"
    assert any("platform_status and docs_audit" in blocker for blocker in row.blockers), (
        "the scope sentence this promotion is bounded by has been removed"
    )
    assert set(TARGET_CODE_EXECUTING_PROFILES) == {"pytest_full", "builder_full"}
    assert {"platform_status", "docs_audit"}.isdisjoint(TARGET_CODE_EXECUTING_PROFILES)


def test_the_two_rows_that_describe_the_deepagents_trunk_agree_about_its_risk() -> None:
    """One lane cannot carry two risk labels.

    `governed obligation delegation` and `deepagents runtime/subagents` both cite
    `builder_ii/adapters/deepagents/deepagents_execution.py`, and the second row's own blockers describe the first
    row's trunk (`execution-candidate -> approve-candidate -> run-approved` over protocol_fake) as
    the verified content. Ladder 4 classified the trunk explicitly; this row was left to the
    default and silently read PASSIVE. When two rows describe one lane, the higher-risk label is
    the honest one -- and they must now move together or this fails.
    """
    rows = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}
    trunk = rows["deepagents runtime/subagents"]
    delegation = rows["governed obligation delegation"]

    assert "builder_ii/adapters/deepagents/deepagents_execution.py" in set(trunk.evidence_files) & set(
        delegation.evidence_files
    )
    assert assurance_state_for_row(trunk) == assurance_state_for_row(delegation)


def test_obligation_delegation_truth_separates_structural_and_native_evidence() -> None:
    # Ladder 4 keeps protocol_fake as deterministic structural truth. Plan Set 2 adds a separately
    # bounded native scenario, so the row must name both without treating either as output-quality
    # evidence. The legacy run-plan projection remains non-evidence.
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}

    row = by_capability["governed obligation delegation"]
    assert row.state == OPERATIONALLY_VERIFIED
    assert row.next_pr == "Ladder 4 complete (PR-8)"
    assert any("protocol_fake" in blocker for blocker in row.blockers)
    assert any("Plan Set 2 two-obligation scenario" in blocker for blocker in row.blockers)
    assert any("never implies agent-output quality" in blocker for blocker in row.blockers)
    assert "docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md" in row.evidence_files

    runtime_row = by_capability["deepagents runtime/subagents"]
    assert "builder-deepagents run-plan" not in runtime_row.command_surfaces
    assert "builder-deepagents run-approved" in runtime_row.command_surfaces
    assert any("legacy structural projection" in blocker for blocker in runtime_row.blockers)


def test_human_status_reports_operational_incompleteness() -> None:
    summary = render_human_summary()
    assert "passive-foundation-complete" in summary
    assert "operationally incomplete" in summary
    assert "B8 deferred; B9 complete" in summary
    assert "R1 Config + Onboarding Kernel must precede B1 verification execution" in summary


def test_builder_platform_matrix_cli_outputs_json() -> None:
    result = runner.invoke(platform_app, ["matrix"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == "builder_ii.platform_completion_matrix"
    assert len(data["capabilities"]) == len(REQUIRED_CAPABILITIES)


def test_builder_platform_status_cli_is_honest() -> None:
    result = runner.invoke(platform_app, ["status"])
    assert result.exit_code == 0, result.output
    assert "passive-foundation-complete" in result.output
    assert "operationally incomplete" in result.output
    assert "B8 deferred; B9 complete" in result.output


def test_next_sequence_rejects_r0_b5() -> None:
    # Tests must reject R0 -> B5 and R1 -> B1 as the current next sequence
    summary = render_human_summary()
    assert "R0 -> B5" not in summary
    assert "R1 -> B1" not in summary
    result = runner.invoke(platform_app, ["status"])
    assert "R0 -> B5" not in result.output
    assert "R1 -> B1" not in result.output
    result_matrix = runner.invoke(platform_app, ["matrix"])
    assert "R0 -> B5" not in result_matrix.output
    assert "R1 -> B1" not in result_matrix.output


def _synthetic_row(capability: str, state: str) -> CapabilityRow:
    return CapabilityRow(
        capability=capability,
        state=state,
        evidence_files=(),
        command_surfaces=(),
        tests=(),
        blockers=(),
        next_pr="",
    )


def test_an_operationally_verified_row_without_an_assurance_decision_is_an_error() -> None:
    """No default. The understatement this closes must be unrepresentable, not merely fixed once.

    `assurance_state_for_row` used to end in `return PASSIVE_ARTIFACT_VERIFIED`, so an
    OPERATIONALLY_VERIFIED row nobody classified silently received the lowest-risk label in the
    field the docs call authoritative for risk. A risk field must fail closed.
    """
    unclassified = _synthetic_row("a capability nobody classified", OPERATIONALLY_VERIFIED)

    with pytest.raises(UnclassifiedCapabilityError, match="no assurance classification"):
        assurance_state_for_row(unclassified)

    errors = validate_assurance_classification(REQUIRED_CAPABILITY_ROWS + (unclassified,))
    assert any("a capability nobody classified" in error for error in errors)


def test_a_stale_assurance_classification_is_an_error() -> None:
    """The reverse direction: a decision kept for a capability that no longer holds that state.

    `MCP invocation` sat in the old BOUNDED_EXECUTION_VERIFIED set while its row was
    PASSIVE_FOUNDATION -- a dead branch, unreachable and misleading, for as long as anyone read the
    mapping to learn what the lane does.
    """
    demoted = tuple(
        _synthetic_row(row.capability, PASSIVE_FOUNDATION) if row.capability == "context packs" else row
        for row in REQUIRED_CAPABILITY_ROWS
    )

    errors = validate_assurance_classification(demoted)

    assert any("'context packs' is stale" in error for error in errors)


def test_the_live_matrix_classifies_every_operationally_verified_row_and_nothing_else() -> None:
    assert validate_assurance_classification(REQUIRED_CAPABILITY_ROWS) == []
    assert validate_completion_matrix() == []
