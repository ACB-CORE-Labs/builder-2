import re
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from builder_ii.command_authority import (
    _EFFECT_FLAGS,
    _EXTRA_COMMAND_NAMES,
    _SYNTHESIZED_PARENTS,
    ASSURANCE_DERIVING_FLAGS,
    ASSURANCE_INERT_FLAGS,
    AUTHORITY_DELEGATING_GROUPS,
    CAPABILITY_FLAGS,
    COMMAND_AUTHORITY_REGISTRY,
    MODE_NONE,
    NO_CAPABILITIES,
    READONLY_TUI_COMMAND_GROUPS,
    READONLY_TUI_COMMANDS,
    REQUIRED_SUBCOMMANDS,
    TIER_0,
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_4,
    CommandAuthorityError,
    CommandAuthorityRecord,
    _assurance_probe,
    _registry_row,
    assurance_state_for_record,
    check_command_authority,
    enforce_command_authority,
    explain_assurance_for_record,
    get_command_record,
    inheritance_errors,
    is_token_prefix,
    render_command_authority_doc,
    render_registry_markdown_table,
    structural_command_groups,
    validate_registry_invariants,
)


def _get_project_root() -> Path:
    return Path(__file__).parent.parent


def test_registry_internal_invariants():
    """Verify registry conforms to all specified safety constraints."""
    errors = validate_registry_invariants()
    assert not errors, f"Registry invariants violated: {errors}"


def test_pyproject_scripts_fully_covered():
    """Ensure every script in pyproject.toml is represented in the registry."""
    root = _get_project_root()
    pyproject_path = root / "pyproject.toml"
    assert pyproject_path.exists(), f"Could not find pyproject.toml at {pyproject_path}"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert scripts, "No scripts found in pyproject.toml project.scripts"

    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    for script_name in scripts.keys():
        # Verify that either the exact script name is registered,
        # or there is at least one subcommand record starting with it.
        has_match = any(name == script_name or name.startswith(f"{script_name} ") for name in registered_names)
        assert has_match, f"Script '{script_name}' from pyproject.toml is missing from registry"


def test_root_builder_subcommands_fully_covered():
    """Ensure every root builder CLI command decorator has an explicit registry row."""
    root = _get_project_root()
    path = root / "builder_ii" / "cli" / "main.py"
    if not path.exists():
        path = root / "builder_ii" / "cli.py"
    cli_source = path.read_text(encoding="utf-8")
    root_commands = {f"builder {match.group(1)}" for match in re.finditer(r"@app\.command\(\"([^\"]+)\"\)", cli_source)}
    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    assert root_commands
    assert root_commands <= registered_names


def test_required_subcommands_fully_covered():
    """Ensure all required subcommands are explicitly present in the registry."""
    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}
    for sub in REQUIRED_SUBCOMMANDS:
        assert sub in registered_names, f"Required subcommand '{sub}' is missing from registry"


def test_all_cli_commands_fully_covered():
    """Dynamically discover and walk all Typer CLI command trees from pyproject.toml
    and assert they are explicitly registered in COMMAND_AUTHORITY_REGISTRY.
    """
    import importlib

    import click
    import typer

    root = _get_project_root()
    pyproject_path = root / "pyproject.toml"
    assert pyproject_path.exists()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert scripts

    def get_click_command(app_obj):
        if isinstance(app_obj, typer.Typer):
            return typer.main.get_command(app_obj)
        return app_obj

    def walk_commands(click_cmd, prefix):
        results = []
        if isinstance(click_cmd, click.Group):
            if click_cmd.invoke_without_command:
                results.append(prefix)
            ctx = click.Context(click_cmd)
            for name in click_cmd.list_commands(ctx):
                sub_cmd = click_cmd.get_command(ctx, name)
                if sub_cmd:
                    results.extend(walk_commands(sub_cmd, f"{prefix} {name}"))
        else:
            results.append(prefix)
        return results

    all_discovered = []
    for script_name, entry_point in scripts.items():
        mod_name, attr_name = entry_point.split(":")
        mod = importlib.import_module(mod_name)
        app_obj = getattr(mod, attr_name)
        click_cmd = get_click_command(app_obj)
        discovered = walk_commands(click_cmd, script_name)
        all_discovered.extend(discovered)

    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    # Tiny explicit allowlist for help-only or non-authority delegated cases
    # e.g., if a sub-typer app is registered as a group but has no standalone behavior
    allowlist = {
        "builder",  # Root group wrapper, delegates to subcommands
        "builder-targets",  # Group wrapper, delegates to subcommands
        "builder-session",  # Group wrapper, delegates to subcommands
        "builder-goose",  # Group wrapper, delegates to subcommands
        "builder-mcp",  # Group wrapper, delegates to subcommands
        "builder-tools",  # Group wrapper, delegates to subcommands
        "builder-deepagents",  # Group wrapper, delegates to subcommands
        "builder-readonly",  # Group wrapper, delegates to subcommands
        "builder-verify",  # Group wrapper, delegates to subcommands
        "builder-research",  # Group wrapper, delegates to subcommands
        "builder-agent",  # Group wrapper, delegates to subcommands
        "builder-bridge",  # Group wrapper, delegates to subcommands
        "builder-bundle",  # Group wrapper, delegates to subcommands
        "builder-records",  # Group wrapper, delegates to subcommands
        "builder-preflight",  # Group wrapper, delegates to subcommands
        "builder-receipt",  # Group wrapper, delegates to subcommands
        "builder-chain",  # Group wrapper, delegates to subcommands
        "builder-handoff",  # Group wrapper, delegates to subcommands
        "builder-intake",  # Group wrapper, delegates to subcommands
        "builder-index",  # Group wrapper, delegates to subcommands
        "builder-promotion",  # Group wrapper, delegates to subcommands
        "builder-promotion-decision",  # Group wrapper, delegates to subcommands
        "builder-state-index",  # Group wrapper, delegates to subcommands
        "builder-snapshot",  # Group wrapper, delegates to subcommands
        "builder-notes",  # Group wrapper, delegates to subcommands
        "builder-quality",  # Group wrapper, delegates to subcommands
        "builder-performance",  # Group wrapper, delegates to subcommands
        "builder-verification",  # Group wrapper, delegates to subcommands
        "builder-hitl",  # Group wrapper, delegates to subcommands
        "builder-orchestration",  # Group wrapper, delegates to subcommands
        "builder-profile-pack",  # Group wrapper, delegates to subcommands
        "builder-model-policy",  # Group wrapper, delegates to subcommands
        "builder-model",  # Group wrapper, delegates to subcommands
        "builder-workflow",  # Group wrapper, delegates to subcommands
        "builder-ledger",  # Group wrapper, delegates to subcommands
        "builder-platform",  # Group wrapper, delegates to subcommands
        "builder-memory",  # Group wrapper, delegates to subcommands
        "builder-config",  # Group wrapper, delegates to subcommands
        "builder-setup",  # Group wrapper, delegates to subcommands
        "builder-git-state",  # Group wrapper, delegates to subcommands
        "builder-runtime",  # Group wrapper, delegates to subcommands
    }

    normalized_discovered = []
    for cmd in all_discovered:
        parts = cmd.split()
        if len(parts) >= 2 and parts[0] == "builder":
            candidate = f"builder-{parts[1]}"
            if candidate in scripts:
                subparts = parts[2:]
                normalized_discovered.append(f"{candidate} " + " ".join(subparts) if subparts else candidate)
                continue
        normalized_discovered.append(cmd)

    missing = []
    for cmd in normalized_discovered:
        if cmd in allowlist:
            continue
        space_version = cmd.replace("builder-", "builder ", 1)
        if cmd in registered_names or space_version in registered_names:
            continue
        missing.append(cmd)

    assert not missing, "Discovered CLI commands missing from COMMAND_AUTHORITY_REGISTRY:\n" + "\n".join(missing)


def test_docs_contain_all_commands_and_table():
    """Verify that docs/COMMAND_AUTHORITY.md documents every command and contains the exact table."""
    root = _get_project_root()
    doc_path = root / "docs" / "COMMAND_AUTHORITY.md"
    assert doc_path.exists(), "docs/COMMAND_AUTHORITY.md does not exist"

    doc_content = doc_path.read_text(encoding="utf-8")

    # Verify every registered command name is mentioned in the docs
    from builder_ii.command_authority import _EXTRA_COMMAND_NAMES

    for r in COMMAND_AUTHORITY_REGISTRY:
        if r.name in _EXTRA_COMMAND_NAMES:
            continue
        assert f"`{r.name}`" in doc_content, f"Command '{r.name}' is not documented in docs/COMMAND_AUTHORITY.md"

    # Verify the table exists in the doc
    expected_table = render_registry_markdown_table()
    assert expected_table in doc_content, (
        "The table in docs/COMMAND_AUTHORITY.md does not match the rendered table from registry"
    )


def test_no_forbidden_identity_framing():
    """Ensure no 'CORE builder-II' conflation in pyproject, registry, or docs."""
    root = _get_project_root()
    forbidden_terms = ["CORE builder-II", "CORE Builder-II", "core builder-ii"]

    # Scan python registry file
    registry_file = root / "builder_ii" / "command_authority.py"
    reg_content = registry_file.read_text(encoding="utf-8")
    for term in forbidden_terms:
        occurrences = reg_content.count(term)
        assert occurrences <= 2, f"Registry source file contains forbidden framing '{term}'"

    # Scan doc file
    doc_path = root / "docs" / "COMMAND_AUTHORITY.md"
    doc_content = doc_path.read_text(encoding="utf-8")
    for term in forbidden_terms:
        assert term not in doc_content, f"Doc file contains forbidden framing '{term}'"


def test_adversarial_validation_violations():
    """Test that validate_registry_invariants detects invalid record mutations."""
    # 1. Tier 0 command claiming authority
    bad_record_1 = CommandAuthorityRecord(
        name="builder-test-adversarial-1",
        entrypoint="builder_ii.cli:app",
        tier=TIER_0,
        promotion_state="artifact_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_shell_execution=True,  # Violation!
    )

    # 2. Authority flag without approval mode
    bad_record_2 = CommandAuthorityRecord(
        name="builder-test-adversarial-2",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state="validation_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,  # Violation!
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_runtime_start=True,  # Violates Tier 1 check and needs approval mode
    )

    # 3. Missing documentation fields
    bad_record_3 = CommandAuthorityRecord(
        name="builder-test-adversarial-3",
        entrypoint="builder_ii.cli:app",
        tier=TIER_0,
        promotion_state="artifact_only",
        runtime_boundary="",  # Violation!
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
    )

    # 4. Contradictory write boundary text
    bad_record_4 = CommandAuthorityRecord(
        name="builder-test-adversarial-4",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state="artifact_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",  # Says no changes
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_artifact_writes=True,  # Violation (contradiction)!
    )

    from builder_ii import command_authority

    original_registry = command_authority.COMMAND_AUTHORITY_REGISTRY

    try:
        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_1,)
        errs = validate_registry_invariants()
        assert any("claims forbidden execution/mutation authority" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_2,)
        errs = validate_registry_invariants()
        assert any("claims forbidden execution/mutation authority" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_3,)
        errs = validate_registry_invariants()
        assert any("missing runtime boundary description" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_4,)
        errs = validate_registry_invariants()
        assert any("write flags are enabled but write boundary text claims no writes" in e for e in errs)

    finally:
        command_authority.COMMAND_AUTHORITY_REGISTRY = original_registry


def test_tier_0_and_tier_1_boundaries():
    """Explicitly verify that Tier 0 and Tier 1 commands do not cross runtime/mutation boundaries."""
    for r in COMMAND_AUTHORITY_REGISTRY:
        if r.tier == TIER_0:
            # Cannot write artifacts, cannot write state, cannot claim execution
            assert not r.allows_artifact_writes, f"{r.name} (Tier 0) cannot write artifacts"
            assert not r.allows_state_writes, f"{r.name} (Tier 0) cannot write state"
            assert not r.allows_runtime_start, f"{r.name} (Tier 0) cannot start runtime"
            assert not r.allows_process_control, f"{r.name} (Tier 0) cannot control processes"
            assert not r.allows_model_execution, f"{r.name} (Tier 0) cannot execute models"
            assert not r.allows_shell_execution, f"{r.name} (Tier 0) cannot execute shell"
            assert not r.allows_source_writes, f"{r.name} (Tier 0) cannot write source"
            assert not r.allows_memory_mutation, f"{r.name} (Tier 0) cannot mutate memory"
            assert not r.allows_git_mutation, f"{r.name} (Tier 0) cannot mutate git"
            assert not r.allows_external_tool_invocation, f"{r.name} (Tier 0) cannot invoke external tools"

        elif r.tier == TIER_1:
            # May artifact-write, but absolutely nothing else
            assert not r.allows_state_writes, f"{r.name} (Tier 1) cannot write state"
            assert not r.allows_runtime_start, f"{r.name} (Tier 1) cannot start runtime"
            assert not r.allows_process_control, f"{r.name} (Tier 1) cannot control processes"
            assert not r.allows_model_execution, f"{r.name} (Tier 1) cannot execute models"
            assert not r.allows_shell_execution, f"{r.name} (Tier 1) cannot execute shell"
            assert not r.allows_source_writes, f"{r.name} (Tier 1) cannot write source"
            assert not r.allows_memory_mutation, f"{r.name} (Tier 1) cannot mutate memory"
            assert not r.allows_git_mutation, f"{r.name} (Tier 1) cannot mutate git"
            assert not r.allows_external_tool_invocation, f"{r.name} (Tier 1) cannot invoke external tools"


def test_readonly_tui_surfaces_are_registered_tier0_observers() -> None:
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}
    for name in (*READONLY_TUI_COMMAND_GROUPS, *READONLY_TUI_COMMANDS):
        assert name in registered, f"{name} missing from COMMAND_AUTHORITY_REGISTRY"
        record = registered[name]
        assert record.tier == TIER_0
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_process_control
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_artifact_writes
        assert not record.allows_state_writes
        assert not record.allows_readonly_subprocess
        assert not record.allows_external_tool_invocation

    for name in READONLY_TUI_COMMANDS:
        assert name in REQUIRED_SUBCOMMANDS


def test_standalone_call_registered_in_authority() -> None:
    """builder-model standalone-call must be registered as Tier 3, declare model execution
    and artifact writes, and be in REQUIRED_SUBCOMMANDS."""
    from builder_ii.command_authority import (
        COMMAND_AUTHORITY_REGISTRY,
        REQUIRED_SUBCOMMANDS,
        TIER_3,
    )

    name = "builder-model standalone-call"
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}

    assert name in registered, f"'{name}' is missing from COMMAND_AUTHORITY_REGISTRY"
    record = registered[name]

    assert record.tier == TIER_3, f"Expected Tier 3, got tier={record.tier}"
    assert record.allows_model_execution, f"{name} must declare allows_model_execution=True"
    assert record.allows_artifact_writes, f"{name} must declare allows_artifact_writes=True"
    assert name in REQUIRED_SUBCOMMANDS, f"'{name}' must be in REQUIRED_SUBCOMMANDS"


def test_enforce_command_authority_fails_closed_for_unknown_command() -> None:
    decision = check_command_authority("builder-missing command")
    assert decision.allowed is False
    assert "not registered" in decision.reasons[0]
    with pytest.raises(CommandAuthorityError):
        enforce_command_authority("builder-missing command")


def test_enforce_command_authority_rejects_unclassified_effect() -> None:
    decision = check_command_authority("builder ask", requested_effects=("patch_application",))
    assert decision.allowed is False
    assert any("patch_application" in reason for reason in decision.reasons)


def test_enforce_command_authority_rejects_safety_critical_claim() -> None:
    decision = check_command_authority("builder ask", safety_critical_claim=True)
    assert decision.allowed is False
    assert decision.assurance_state == "SAFETY_CRITICAL_PROHIBITED"


def test_enforce_command_authority_allows_classified_effect() -> None:
    decision = enforce_command_authority("builder ask", requested_effects=("model_execution", "artifact_write"))
    assert decision.allowed is True
    assert decision.assurance_state == "LIVE_PROVIDER_VERIFIED"


def test_process_control_requires_explicit_process_control_flag() -> None:
    denied = check_command_authority("builder-runtime clear-marker", requested_effects=("process_control",))
    assert denied.allowed is False
    assert any("process_control" in reason for reason in denied.reasons)

    allowed = enforce_command_authority(
        "builder-runtime stop",
        requested_effects=("process_control", "state_write", "readonly_subprocess"),
    )
    assert allowed.allowed is True
    assert allowed.assurance_state == "BOUNDED_EXECUTION_VERIFIED"


def test_builder_memory_commands_are_registered_as_tier1_surfaces() -> None:
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}

    root = registered["builder-memory"]
    assert root.tier == TIER_1
    assert not root.allows_artifact_writes
    assert root.approval_mode == MODE_NONE

    for name in (
        "builder-memory atom",
        "builder-memory index",
        "builder-memory search",
        "builder-memory reconstruct",
    ):
        record = registered[name]
        assert record.tier == TIER_1
        assert record.allows_artifact_writes is True
        assert name in REQUIRED_SUBCOMMANDS

    for name in (
        "builder-memory validate-atom",
        "builder-memory validate-index",
        "builder-memory validate-reconstruction",
        "builder-memory validate-search-result",
    ):
        record = registered[name]
        assert record.tier == TIER_1
        assert record.allows_artifact_writes is False
        assert name in REQUIRED_SUBCOMMANDS


def test_runtime_gate_allows_passive_registered_command_without_hitl() -> None:
    from builder_ii.command_authority import enforce_command_authority

    decision = enforce_command_authority("builder-targets list", requested_effects=())

    assert decision.allowed is True
    assert decision.to_evidence()["allowed"] is True
    assert decision.to_evidence()["fail_closed"] is False


def test_runtime_gate_denies_unknown_command_fail_closed() -> None:
    from builder_ii.command_authority import CommandAuthorityError, check_command_authority, enforce_command_authority

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority("builder-unknown mutate", requested_effects=("source_writes",))
    assert "not registered" in str(exc_info.value)

    decision = check_command_authority("builder-unknown mutate", requested_effects=("source_writes",))
    assert decision.allowed is False
    assert "not registered" in decision.reason
    assert decision.to_evidence()["fail_closed"] is True


def test_runtime_gate_denies_over_authority_effect() -> None:
    from builder_ii.command_authority import CommandAuthorityError, check_command_authority, enforce_command_authority

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority("builder-targets list", requested_effects=("source_writes",))
    assert "not classified" in str(exc_info.value)

    decision = check_command_authority("builder-targets list", requested_effects=("source_writes",))
    assert decision.allowed is False
    assert "not classified" in decision.reason


def test_runtime_gate_requires_hitl_for_run_approved() -> None:
    from builder_ii.command_authority import CommandAuthorityError, check_command_authority, enforce_command_authority

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
            hitl_bound=False,
        )
    assert "HITL" in str(exc_info.value)

    decision = check_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        hitl_bound=False,
    )
    assert decision.allowed is False
    assert "HITL" in decision.reason


def test_command_authority_compatibility_hitl_bound() -> None:
    from builder_ii.command_authority import CommandAuthorityError, enforce_command_authority

    # 1. Denied with no approval_ref and no hitl_bound
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
        )
    assert "HITL" in str(exc.value)

    # 2. Denied with hitl_bound=False
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
            hitl_bound=False,
        )
    assert "HITL" in str(exc.value)

    # 3. Allowed with hitl_bound=True
    decision = enforce_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        hitl_bound=True,
    )
    assert decision.allowed is True

    # 4. Allowed with approval_ref
    decision = enforce_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        approval_ref="approval-123",
    )
    assert decision.allowed is True

    # 5. Unknown commands still fail closed
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority("builder-missing-command")
    assert "not registered" in str(exc.value)


def test_command_authority_doc_mirrors_the_registry_verbatim() -> None:
    """`docs/COMMAND_AUTHORITY.md` is a generated mirror of the registry, never a hand-edited doc.

    Ladder 6 hand-edited this doc's `builder stratum` row *ahead of* the source it mirrors, so
    within one commit the doc claimed the surface was wired while `command_authority.py` still
    called it a fabricated mockup. Nothing caught it: `builder-platform audit-docs` detects docs
    that overstate a capability, never docs that disagree with the registry, and the doc is
    digest-referenced as a policy snapshot by `workflow_orchestrator` -- so a hand edit silently
    changes a digest that governed events bind.

    The table `render_registry_markdown_table()` produces must appear in the doc **verbatim**. Two
    earlier cuts of this pin were weaker than they were claimed to be, and both are worth recording:

    - Searching the whole document for each record's `runtime_boundary` passes when a hand-edited row
      merely *shares text* with some other row -- 215 of the 386 boundaries are a substring of another
      record's. A hand edit could be "found" inside the wrong row.
    - Requiring one row per record is simply false: the renderer emits 287 rows for 386 records, and
      that filtering is deliberate. Asserting otherwise fails on a doc that is perfectly in sync.

    Comparing against the generator's own output has neither failure mode: it is exact, it needs no
    theory about which records get rows, and it says the true thing -- edit the registry, regenerate,
    never the other way round.

    A third weakness outlived both: `table in doc` constrains only the table. Any prose could be
    hand-added around it and would inherit the generated table's authority while being subject to no
    check at all -- in a file hashed into every governed workflow event. The comparison is now against
    the *whole* rendered document, so there is no unchecked region left to write a lie into.
    """
    doc = (Path(__file__).resolve().parents[1] / "docs" / "COMMAND_AUTHORITY.md").read_text(encoding="utf-8")
    assert doc == render_command_authority_doc(), (
        "docs/COMMAND_AUTHORITY.md has drifted from builder_ii/command_authority.py. Regenerate it: "
        "uv run python -m builder_ii.command_authority > docs/COMMAND_AUTHORITY.md"
    )


def test_a_hand_written_paragraph_outside_the_table_cannot_hide_in_the_policy_snapshot() -> None:
    """Holds open the weakness whole-document equality closes.

    The previous `table in doc` pin passes on a document that appends an unchecked claim after the
    generated table. This asserts that it did, and that the current pin does not.
    """
    doc = (Path(__file__).resolve().parents[1] / "docs" / "COMMAND_AUTHORITY.md").read_text(encoding="utf-8")
    forged = doc + "\n\n`builder capabilities` performs no model execution.\n"

    assert render_registry_markdown_table().strip() in forged, "the old table-substring pin would still pass"
    assert forged != render_command_authority_doc(), "whole-document equality must catch the appended claim"


def test_no_row_hides_a_capability_the_record_holds() -> None:
    """The defect this file exists to prevent, stated as the smallest true sentence.

    `render_registry_markdown_table` printed five boolean columns against a record carrying eleven
    capability flags. The five were not the risky five: two of them (`allows_artifact_writes`,
    `allows_state_writes`) move no assurance state, while five flags that *do* had no column. Fourteen
    rows therefore printed five `No`s while holding real authority -- among them `builder capabilities`,
    which reaches a live model provider.

    Nothing failed. `builder-platform audit-docs` catches a doc that overstates a capability; this doc
    understated one. The doc-parity pin passed because the document faithfully mirrored a generator
    that omitted. Truth is symmetric; neither check was.
    """
    for record in COMMAND_AUTHORITY_REGISTRY:
        if record.name in _EXTRA_COMMAND_NAMES:
            continue
        row = _registry_row(record)
        for flag in CAPABILITY_FLAGS:
            if getattr(record, flag):
                assert f"`{flag.removeprefix('allows_')}`" in row, (
                    f"`{record.name}` sets {flag} and the policy snapshot does not say so"
                )
        if not any(getattr(record, flag) for flag in CAPABILITY_FLAGS):
            assert NO_CAPABILITIES in row, f"`{record.name}` claims no capability and must render as {NO_CAPABILITIES}"


def test_every_flag_that_can_move_the_assurance_state_is_named_in_the_policy_snapshot() -> None:
    """Discover the risk-bearing flags by perturbation, not by transcribing the derivation chain.

    A hand-kept list of "the flags that matter" is a second place for the truth to live, and it goes
    stale the first time the lattice changes. Flipping each flag on an otherwise-identical record and
    watching the derived state is the same question asked of the code itself.
    """
    baseline = assurance_state_for_record(_assurance_probe())
    deriving = {flag for flag in CAPABILITY_FLAGS if assurance_state_for_record(_assurance_probe(**{flag: True})) != baseline}

    assert deriving == set(ASSURANCE_DERIVING_FLAGS), "the module's perturbation and this test's disagree"

    # Not a hardcoded count. The risk-bearing flags are exactly the ones the chain branches on, so
    # the inert set is exactly those it does not -- and a transcribed number here would go stale the
    # first time the lattice grew, which it just did.
    assert deriving == set(CAPABILITY_FLAGS) - set(ASSURANCE_INERT_FLAGS)
    assert deriving, "if no flag moves the state, the perturbation baseline is not the lattice bottom"

    header = render_registry_markdown_table().splitlines()[0]
    assert "Assurance" in header and "Assurance Derived From" in header

    rendered = {
        flag
        for flag in CAPABILITY_FLAGS
        for record in [_assurance_probe(**{flag: True})]
        if f"`{flag.removeprefix('allows_')}`" in _registry_row(record)
    }
    assert deriving <= rendered, f"flags decide the assurance state and are invisible: {sorted(deriving - rendered)}"


def test_exactly_one_flag_carries_no_risk_signal_and_that_is_correct() -> None:
    """`allows_artifact_writes` is inert *by definition*, not by oversight.

    `PASSIVE_ARTIFACT_VERIFIED` reads "writes nothing outside the artifact store". A command that
    writes only artifacts therefore satisfies it exactly, and raising its state would contradict the
    definition. This is the one flag for which inertness is the right answer, and this pin ties that
    answer to the sentence that justifies it -- so that rewording the sentence breaks the pin.

    The predecessor of this test named three inert flags and said: "if the lattice later gives one of
    these a consequence, this pin fails and says so." It did, and it did.
    """
    from builder_ii.assurance import ASSURANCE_STATE_DEFINITIONS, PASSIVE_ARTIFACT_VERIFIED

    assert ASSURANCE_INERT_FLAGS == ("allows_artifact_writes",)
    assert "writes nothing outside the artifact store" in ASSURANCE_STATE_DEFINITIONS[PASSIVE_ARTIFACT_VERIFIED]

    old_columns = {"allows_shell_execution", "allows_process_control", "allows_source_writes",
                   "allows_artifact_writes", "allows_state_writes"}
    assert len(set(ASSURANCE_DERIVING_FLAGS) - old_columns) == 6, "six risk-bearing flags had no column"

    doc = render_command_authority_doc()
    for flag in ASSURANCE_INERT_FLAGS:
        assert f"`{flag}`" in doc, f"the doc must name {flag} as carrying no risk signal"


def test_a_command_that_writes_local_state_is_not_passive() -> None:
    """`builder-runtime clear-marker` derived `PASSIVE_ARTIFACT_VERIFIED` while deleting a file.

    Its own `write_boundary` says it "deletes or rewrites the builder runtime marker under configured
    local state paths". `PASSIVE_ARTIFACT_VERIFIED` promises the command "writes nothing outside the
    artifact store". Both could not be true. It derived passive because passive was the chain's
    fall-through -- absence read as a safe classification.

    Its siblings `builder-runtime stop` and `reset` perform the *same* filesystem write and derive
    `BOUNDED_EXECUTION_VERIFIED`, but only because they also kill a process. That is the accident
    that kept the gap hidden.
    """
    from builder_ii.assurance import LOCAL_STATE_MUTATION_VERIFIED

    record = get_command_record("builder-runtime clear-marker")
    assert record is not None and record.allows_state_writes
    assert not any(getattr(record, f) for f in ("allows_process_control", "allows_runtime_start"))

    derivation = explain_assurance_for_record(record)
    assert derivation.state == LOCAL_STATE_MUTATION_VERIFIED
    assert derivation.because == "`allows_state_writes` is set"

    for sibling in ("builder-runtime stop", "builder-runtime reset"):
        other = get_command_record(sibling)
        assert other is not None and other.allows_state_writes
        assert assurance_state_for_record(other) == "BOUNDED_EXECUTION_VERIFIED", (
            f"`{sibling}` kills a process; that is the larger claim and must still win"
        )


def test_memory_mutation_is_a_prohibition_no_record_may_claim() -> None:
    """Not an inert flag -- an unclaimed one. No record has ever set it.

    The doc used to say the inert flags "are recorded because they describe the command". This one
    describes no command. What it records is a refusal: every governed platform bundle asserts
    `memory_mutation: DISABLED`, and the B8 memory lane writes memory *artifacts*, claiming
    `allows_artifact_writes` instead. So the flag names an authority builder-II declines to grant.

    It derives `SAFETY_CRITICAL_PROHIBITED`, whose definition says exactly that: a capability whose
    promotion is refused regardless of the evidence offered for it.
    """
    from builder_ii.assurance import SAFETY_CRITICAL_PROHIBITED

    holders = [r.name for r in COMMAND_AUTHORITY_REGISTRY if r.allows_memory_mutation]
    assert holders == [], f"memory mutation is prohibited; these records claim it: {holders}"

    assert "allows_memory_mutation" in ASSURANCE_DERIVING_FLAGS, "a prohibited flag must not read as harmless"
    probe = explain_assurance_for_record(_assurance_probe(allows_memory_mutation=True))
    assert probe.state == SAFETY_CRITICAL_PROHIBITED

    memory_writers = [r for r in COMMAND_AUTHORITY_REGISTRY if r.name.startswith("builder-memory ")]
    assert memory_writers, "the B8 memory lane must exist for this pin to mean anything"
    assert any(r.allows_artifact_writes for r in memory_writers), "the memory lane writes artifacts, not memory"


def test_the_memory_mutation_prohibition_is_a_registry_invariant_at_every_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty-holders assertion says the flag is unclaimed today. It does not stop tomorrow.

    `validate_registry_invariants` forbade the flag at Tier 0 and Tier 1 only -- the tiers that
    forbid every execution flag anyway. Tier 2 (`operator_managed`) and Tier 3
    (`hitl_runtime_candidate`) are exactly the tiers a record claiming it would plausibly sit at, and
    they were unguarded. The claim rested on a test in another file, which is not an invariant.
    """
    import builder_ii.command_authority as module

    assert validate_registry_invariants() == [], "baseline: no record claims it"

    for tier in (TIER_0, TIER_1, TIER_2, TIER_3, TIER_4):
        claimant = replace(_assurance_probe(allows_memory_mutation=True), tier=tier)
        monkeypatch.setattr(module, "COMMAND_AUTHORITY_REGISTRY", (claimant,))
        errors = " ".join(validate_registry_invariants())
        assert "no record may claim at any tier" in errors, f"tier {tier} left the prohibition unenforced"


def test_every_capability_flag_is_requestable_as_an_effect() -> None:
    """A flag no caller can ask about is a permission that can never be enforced.

    `check_command_authority` answers questions phrased as effect names. If a twelfth flag is added to
    the record and not to `_EFFECT_FLAGS`, no command can ever be denied for it.
    """
    requestable = {flag for flags in _EFFECT_FLAGS.values() for flag in flags}
    assert requestable == set(CAPABILITY_FLAGS), (
        f"unrequestable flags: {sorted(set(CAPABILITY_FLAGS) - requestable)}; "
        f"effects naming no flag: {sorted(requestable - set(CAPABILITY_FLAGS))}"
    )


def test_a_record_can_carry_authority_with_no_capability_flag_set() -> None:
    """Why the snapshot prints the derived state, and not merely the flags that feed it.

    `builder-goose start-readonly` hands the operator's terminal to a Goose runtime. It sets no
    capability flag; its assurance comes from its promotion state. A table of flags -- even all eleven
    -- can therefore never explain it, and a reader given only flags would call the state wrong.

    If every non-passive record one day derives from a flag, this pin has lost its point -- re-derive it.
    """
    flagless = [
        record
        for record in COMMAND_AUTHORITY_REGISTRY
        if not any(getattr(record, flag) for flag in CAPABILITY_FLAGS)
        and assurance_state_for_record(record) != "PASSIVE_ARTIFACT_VERIFIED"
    ]
    assert flagless, "no record derives authority without a flag -- re-derive this pin"

    for record in flagless:
        derivation = explain_assurance_for_record(record)
        assert "is set" not in derivation.because, f"`{record.name}` has no flag set but blames one"
        assert derivation.because in _registry_row(record) or record.name in _EXTRA_COMMAND_NAMES

    start_readonly = get_command_record("builder-goose start-readonly")
    assert start_readonly is not None
    derivation = explain_assurance_for_record(start_readonly)
    assert derivation.state == "READ_ONLY_RUNTIME_VERIFIED"
    assert derivation.because == "promotion state is `read_only_runtime_candidate`"


def test_explaining_the_assurance_state_never_changes_it() -> None:
    """`assurance_state_for_record` is now a projection of `explain_assurance_for_record`.

    Two functions with the same if-chain would be two places for the answer to drift. There is one
    chain; this pins that the projection is total over every record the registry holds.
    """
    for record in COMMAND_AUTHORITY_REGISTRY:
        assert assurance_state_for_record(record) == explain_assurance_for_record(record).state


def test_each_capability_flag_derives_the_state_the_lattice_promises() -> None:
    """The flag-to-state map, written out, so a silent change to the chain is a loud test failure."""
    expected = {
        "allows_source_writes": "MUTATION_WITH_ROLLBACK_VERIFIED",
        "allows_git_mutation": "MUTATION_WITH_ROLLBACK_VERIFIED",
        "allows_model_execution": "LIVE_PROVIDER_VERIFIED",
        "allows_runtime_start": "READ_ONLY_RUNTIME_VERIFIED",
        "allows_process_control": "BOUNDED_EXECUTION_VERIFIED",
        "allows_shell_execution": "BOUNDED_EXECUTION_VERIFIED",
        "allows_external_tool_invocation": "BOUNDED_EXECUTION_VERIFIED",
        "allows_readonly_subprocess": "BOUNDED_EXECUTION_VERIFIED",
        "allows_state_writes": "LOCAL_STATE_MUTATION_VERIFIED",
        # Not LOCAL_STATE_MUTATION_VERIFIED, though it too mutates a store outside the artifact
        # store: that state ends "calls no provider", and this flag is the one capability whose
        # promotion is refused on any evidence. The refused capability does not get the safe label.
        "allows_memory_mutation": "SAFETY_CRITICAL_PROHIBITED",
    }
    assert set(expected) == set(ASSURANCE_DERIVING_FLAGS)
    for flag, state in expected.items():
        derivation = explain_assurance_for_record(_assurance_probe(**{flag: True}))
        assert (derivation.state, derivation.because) == (state, f"`{flag}` is set")


def test_the_policy_snapshot_documents_every_command_including_the_ones_nobody_declared() -> None:
    """99 of the 386 records were absent from the doc entirely. They are clones."""
    doc = render_command_authority_doc()
    # 98, down from 99: the github/main reconciliation declared `builder-hitl run-command` as a
    # real Tier 4 fail-closed record (and declared `builder-readonly content-read` and
    # `builder-platform operator-lane` outright), so those names are no longer prefix-clones.
    # 100, up from 98: CodeVault G1 PR-1 added `builder-code-vault extractor-manifest` and
    # `builder-code-vault validate-extractor-manifest` as undeclared prefix-clones of the
    # `builder-code-vault` group.
    assert len(_SYNTHESIZED_PARENTS) == 100
    for record in COMMAND_AUTHORITY_REGISTRY:
        assert f"`{record.name}`" in doc, f"`{record.name}` is in the registry and absent from the policy snapshot"

    assert "(command group)" in doc, "the doc must say when a clone inherits a group's classification"


def test_a_clone_inherits_on_a_word_boundary_not_a_string_prefix() -> None:
    """`builder-goose validate-command-proposal` is not a subcommand of `builder-goose validate`.

    Parentage used to be `name.startswith(record.name)`. Under that rule the clone inherited from the
    leaf validator whose name is a *substring* of its own, rather than from the `builder-goose` group.
    The two happen to be classified identically, so nothing broke -- which is precisely why nobody
    noticed that authority was being assigned on a substring match.
    """
    for name, parent in _SYNTHESIZED_PARENTS.items():
        assert is_token_prefix(parent, name), f"`{name}` inherits from `{parent}`, which is not a word-prefix of it"

    assert _SYNTHESIZED_PARENTS["builder-goose validate-command-proposal"] == "builder-goose"
    assert get_command_record("builder-goose validate") is not None, "the substring parent still exists as a record"


def test_a_command_group_is_discovered_from_the_registry_not_transcribed_beside_it() -> None:
    """The transcribed predicate listed `builder-tui`. No record has ever borne that name.

    The CLI group is `builder tui`, with a space. So one of the twenty hand-written names matched
    nothing, while thirty-two records that demonstrably have subcommands went unmarked. This is the
    same failure `render_registry_markdown_table` had: a second place for the truth to live.
    """
    groups = structural_command_groups()
    names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    assert "builder tui" in groups, "`builder tui` has six subcommands and is a group"
    assert "builder-tui" not in names, "the transcribed list's `builder-tui` never named a record"
    assert "builder-runtime" in groups, "`builder-runtime` has subcommands"

    for parent in groups:
        assert any(is_token_prefix(parent, n) for n in names), f"`{parent}` is a group with no subcommand"


def test_delegating_a_groups_authority_downward_stays_a_curated_decision() -> None:
    """`is_command_group` is a fact. `authority_delegates_to_subcommands` is a policy.

    Conflating them would silently widen a permission: `builder-runtime` is structurally a group and
    declares `runtime_start`, `state_writes`, `readonly_subprocess` and `external_tool_invocation`.
    Deriving delegation from group-ness would let `builder-runtime <anything>` resolve to it.
    """
    names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}
    for name in AUTHORITY_DELEGATING_GROUPS:
        assert name in names, f"`{name}` may absorb unregistered subcommands and is not a record"
        assert name in structural_command_groups(), f"`{name}` delegates authority and has no subcommands"

    runtime = get_command_record("builder-runtime")
    assert runtime is not None and runtime.is_command_group
    assert not runtime.authority_delegates_to_subcommands, "a group that declares runtime_start must not delegate it"


def test_every_synthesized_record_inherits_from_a_command_group() -> None:
    """Necessarily so: a record becomes a group by acquiring subcommands.

    The earlier count of 34 came from the transcribed list, not from the registry. Every clone states
    a classification that describes its parent and was never checked against the clone itself.
    """
    for name, parent in _SYNTHESIZED_PARENTS.items():
        record = get_command_record(name)
        parent_record = get_command_record(parent)
        assert record is not None and parent_record is not None
        assert parent_record.is_command_group, f"`{name}` inherits from `{parent}`, which has no subcommands"
        assert record.authority_is_inherited and record.inherited_from == parent


def test_no_record_inherits_from_itself() -> None:
    """A copy names the record it was copied from, and that is never the copy.

    `check_command_authority` refuses to certify an effect for an inherited record. A record naming
    itself as its own source would be a copy presenting as a declaration -- the exact confusion the
    two fields exist to break -- and the deny reason would render as "inherited from `X`" on the
    record named `X`, which reads as a bug in `X` rather than in the copy.
    """
    for record in COMMAND_AUTHORITY_REGISTRY:
        assert inheritance_errors(record) == [], record.name


def test_the_three_ways_inheritance_can_be_incoherent_are_each_named() -> None:
    """The checker itself, exercised on the three records the registry must never contain."""
    probe = _assurance_probe()

    self_inheriting = replace(probe, authority_is_inherited=True, inherited_from="probe")
    assert inheritance_errors(self_inheriting) == ["Record 'probe' inherits from itself; a copy is not a declaration"]

    sourceless = replace(probe, authority_is_inherited=True, inherited_from="")
    assert inheritance_errors(sourceless) == ["Record 'probe' is marked inherited but names no source record"]

    unmarked = replace(probe, authority_is_inherited=False, inherited_from="builder")
    assert inheritance_errors(unmarked) == [
        "Record 'probe' names inheritance source 'builder' but is not inherited",
    ]


def test_the_inheritance_invariant_is_enforced_not_merely_asserted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`validate_registry_invariants` must *run* the checker, not merely coexist with it.

    Asserting `validate_registry_invariants() == []` against the real registry proves nothing: it
    passes whether or not the checker is wired in, because the real registry is already coherent. So
    put a self-inheriting record in the registry and require the validator to find it.
    """
    import builder_ii.command_authority as module

    assert validate_registry_invariants() == [], "baseline: the real registry is coherent"

    self_inheriting = replace(_assurance_probe(), authority_is_inherited=True, inherited_from="probe")
    monkeypatch.setattr(module, "COMMAND_AUTHORITY_REGISTRY", (self_inheriting,))
    assert "inherits from itself" in " ".join(validate_registry_invariants())

    for record in COMMAND_AUTHORITY_REGISTRY:
        if record.name not in _EXTRA_COMMAND_NAMES:
            assert not record.authority_is_inherited, f"`{record.name}` is declared and marked inherited"


def test_an_inherited_record_can_never_certify_a_requested_effect() -> None:
    """A copy is indistinguishable from a declaration once the copy is made.

    `builder-git-state artifact` really does run `git`; `builder-session validate` really does not.
    Both inherited their answer from a parent. Rather than guess which is which, no inherited record
    may spend the capability it was handed. Deny-only: it can lose a permission it never earned and
    can never gain one.
    """
    checked = 0
    for name in _EXTRA_COMMAND_NAMES:
        record = get_command_record(name)
        assert record is not None
        for effect, flags in _EFFECT_FLAGS.items():
            if not any(getattr(record, flag) for flag in flags):
                continue  # it would be denied anyway; that proves nothing
            decision = check_command_authority(name, requested_effects=(effect,))
            assert not decision.allowed, f"`{name}` certified `{effect}` on inherited authority"
            assert any("inherited" in r for r in decision.reasons)
            checked += 1

    assert checked > 0, "no inherited record holds a flag: this pin would pass vacuously"


def test_a_declared_record_still_certifies_the_effects_it_declares() -> None:
    """The guard against over-denial. Refusing everything is not a governance win."""
    allowed = check_command_authority("builder-tools list", requested_effects=("readonly_subprocess", "external_tool"))
    assert allowed.allowed, allowed.reasons

    for name, effects in [
        ("builder-runtime status", ("readonly_subprocess", "external_tool")),
        ("builder-verify run-approved", ("artifact_writes", "readonly_subprocess")),
        ("builder-model call", ("model_execution", "artifact_write")),
    ]:
        decision = check_command_authority(name, requested_effects=effects)
        assert not any("inherited" in r for r in decision.reasons), f"`{name}` is declared, not inherited"


def test_the_perturbation_probe_starts_at_the_bottom_of_the_lattice() -> None:
    """The unstated precondition that makes `ASSURANCE_DERIVING_FLAGS` sound.

    Flipping a flag and watching the state move only discovers the risk-bearing flags if the probe's
    unflagged baseline is the *lowest* state. Give the probe `tier=TIER_4` and its baseline becomes
    `BLOCKED_BY_EVIDENCE`; every flag then reads inert, and the doc would print all eleven as
    carrying no risk signal. Nothing said so out loud, and no pin asserted it.
    """
    from builder_ii.assurance import PASSIVE_ARTIFACT_VERIFIED
    from builder_ii.command_authority import _ASSURANCE_BASELINE

    assert _ASSURANCE_BASELINE == PASSIVE_ARTIFACT_VERIFIED, "the probe's baseline is not the bottom of the lattice"
    assert assurance_state_for_record(_assurance_probe()) == PASSIVE_ARTIFACT_VERIFIED

    # A probe that misspells a flag would otherwise perturb nothing and report the flag inert.
    with pytest.raises(ValueError, match="not capability flags"):
        _assurance_probe(allow_source_writes=True)


# --- `builder stratum` must name exactly what is unfinished: no more, no fewer ------------------
#
# `builder-platform audit-docs` catches docs that OVERSTATE a capability. It cannot catch a record
# that UNDERSTATES one. When STRATUM's fabricated chain digest was replaced with an honest absence,
# this registry was updated to claim "tier evaluation and chain digests are real" -- a fresh lie, in
# the opposite direction, in the file whose whole job is truth. Truth is symmetric; the audit is
# not. These pins stand in for it, and they live in this commit because they assert on this record.


def _stratum_record():
    return next(record for record in COMMAND_AUTHORITY_REGISTRY if record.name == "builder stratum")


def test_stratum_record_names_every_surface_that_is_still_a_mockup() -> None:
    from builder_ii.tui.app import STRATUM_UNIMPLEMENTED_SURFACES

    boundary = _stratum_record().runtime_boundary.lower()
    for surface in STRATUM_UNIMPLEMENTED_SURFACES:
        assert surface.lower() in boundary, f"runtime_boundary omits the unfinished {surface!r}"


def test_stratum_record_claims_no_capability_the_code_does_not_have() -> None:
    boundary = _stratum_record().runtime_boundary.lower()
    assert "no chain digest is displayed" in boundary, "the record must say the digest is absent"
    for overclaim in ("chain digests are real", "chain digest are real", "digests are wired"):
        assert overclaim not in boundary, f"runtime_boundary overclaims: {overclaim!r}"
    for stale in ("fake tier evaluation", "fabricated chain digest"):
        assert stale not in boundary, f"runtime_boundary names a mockup that no longer exists: {stale!r}"


def test_stratum_record_files_hitl_refusal_as_design_not_as_a_pending_feature() -> None:
    """The refusal is constitutive, not unfinished.

    A surface that renders a digest must not harvest its confirmation -- the same principle
    `init_decisions` states for `builder init`. Filing that refusal under "pending post-beta
    wiring", as this record once did, mistakes a designed boundary for a missing feature.
    """
    boundary = _stratum_record().runtime_boundary.lower()
    assert "never mutate approval state" in boundary
    assert "not pending features" in boundary


def test_doc_parity_pin_catches_a_hand_edit_a_substring_check_would_miss() -> None:
    """Holds open the exact weakness the generator-exact check closes, so it cannot reopen.

    Most `runtime_boundary` strings are substrings of some other record's. A document-wide membership
    test therefore still passes after a row is hand-edited away from its source, because the original
    text survives *somewhere else* in the table. Comparing against the generator's output does not.
    """
    doc = (Path(__file__).resolve().parents[1] / "docs" / "COMMAND_AUTHORITY.md").read_text(encoding="utf-8")
    boundaries = [record.runtime_boundary for record in COMMAND_AUTHORITY_REGISTRY]
    shadowed = {b for b in boundaries if sum(1 for other in boundaries if b in other) > 1}
    assert shadowed, "if no boundary shadows another, this pin has lost its point -- re-derive it"

    victim = next(r for r in COMMAND_AUTHORITY_REGISTRY if r.runtime_boundary in shadowed and f"| `{r.name}` |" in doc)
    mutated = doc.replace(f"| `{victim.name}` |", f"| `{victim.name}` | HAND EDITED |", 1)

    assert victim.runtime_boundary in mutated, "the naive document-wide check would still pass -- that is the bug"
    assert render_registry_markdown_table().strip() not in mutated, "the generator-exact check must catch it"


def test_stratum_record_names_every_action_that_would_originate_authority() -> None:
    """STRATUM had three keybindings that originated authority the record denied it had.

    `g` spawned a Goose session with the developer builtin -- file editing and shell -- with no
    read-only policy, no launch receipt and no approval, while `builder-goose start-readonly` gates
    exactly that runtime at TIER_3 behind HITL approval. `p` wrote an artifact under an unregistered
    kind. `u` announced a dispatch that never happened and wrote another unregistered kind.

    All three are now constitutive refusals. The record must say so, and must name the governed
    command each one defers to, so that a reader of the registry can tell a designed boundary from
    an unfinished feature.
    """
    record = _stratum_record()
    surface = f"{record.runtime_boundary} {record.write_boundary} {record.approval_boundary}".lower()
    for governed_command in (
        "builder-goose start-readonly",
        "builder-session prepare-package",
        "builder-deepagents assign-subagent",
    ):
        assert governed_command in surface, f"the record does not name {governed_command!r}"
    assert "no keybinding originates authority" in surface
    assert "executes nothing else and claims no execution" in surface
    assert "tier-permission inspector" in surface
    assert "composer" in surface
    # It starts exactly one runtime, and the governed command starts it -- not the render surface.
    assert "starts exactly one runtime, and never itself" in surface
    assert "never spawns goose directly and never selects goose builtins" in surface
    assert "fails closed twice before anything spawns" in surface


def test_stratum_declares_the_runtime_it_starts_and_derives_the_matching_assurance() -> None:
    """The flags must say what the code does; the derived assurance follows from the flags.

    Before this, `builder stratum` set no capability flags at all, so
    `assurance_state_for_record` fell through to PASSIVE_ARTIFACT_VERIFIED for a surface that could
    write files and spawn a shell-capable Goose session -- the same fail-open default that files the
    verification lane as passive in the completion matrix. It now invokes exactly one governed
    command, which starts a read-only runtime, so it declares that and derives the same assurance
    state as the command it invokes.
    """
    from builder_ii.command_authority import assurance_state_for_record

    record = _stratum_record()
    governed = next(r for r in COMMAND_AUTHORITY_REGISTRY if r.name == "builder-goose start-readonly")

    assert record.allows_runtime_start is True
    assert record.allows_external_tool_invocation is True
    assert record.allows_artifact_writes is False, "the receipts are written by the command it invokes"
    assert record.allows_source_writes is False
    assert record.allows_shell_execution is False

    assert assurance_state_for_record(record) == "READ_ONLY_RUNTIME_VERIFIED"
    assert assurance_state_for_record(record) == assurance_state_for_record(governed), (
        "STRATUM's Goose keybinding is a launcher of the governed lane, so it can be no more "
        "assured -- and no less -- than the command it launches"
    )


def test_operator_lane_declares_the_git_subprocess_it_actually_spawns() -> None:
    """`run_operator_lane` shells out to read-only `git rev-parse`/`git status` on every run.

    The record arrived from the github/main reconciliation with only `allows_artifact_writes`, so it
    fell through to PASSIVE_ARTIFACT_VERIFIED -- whose definition says "spawns no process". False:
    it spawns three per invocation. It now declares `allows_readonly_subprocess` like its sibling
    `builder-git-state`, so the assurance state is honest about the process it starts.
    """
    from builder_ii.assurance import BOUNDED_EXECUTION_VERIFIED, PASSIVE_ARTIFACT_VERIFIED

    record = get_command_record("builder-platform operator-lane")
    assert record is not None
    assert record.allows_readonly_subprocess, "the lane spawns read-only git subprocesses"
    state = assurance_state_for_record(record)
    assert state == BOUNDED_EXECUTION_VERIFIED
    assert state != PASSIVE_ARTIFACT_VERIFIED, "a command that spawns a process must not read as passive"
