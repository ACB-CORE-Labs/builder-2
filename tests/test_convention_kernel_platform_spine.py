from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_index_records import _VALIDATORS
from builder_ii.config import load_settings
from builder_ii.convention_kernel import (
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    ConventionKernel,
    ConventionKernelPlatformBundle,
    check_artifact_governance_safety,
    validate_convention_kernel_platform_bundle,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    return repo


def test_prepare_platform_spine_happy_path(tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    bundle = kernel.prepare_platform_spine(
        settings,
        "builder",
        repo_path=str(repo),
        task="run builder-ii local developer check",
        include_deepagents_readiness=True,
    )

    assert isinstance(bundle, ConventionKernelPlatformBundle)
    bundle_dict = bundle.to_dict()

    # Validate that it passes validation
    errors = validate_convention_kernel_platform_bundle(bundle_dict)
    assert not errors, f"Validation errors: {errors}"

    # Verify composition targets
    assert bundle_dict["kind"] == CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND
    assert bundle_dict["bundle_state"] == "PLANNED_ONLY"
    assert bundle_dict["executes_now"] is False
    assert bundle_dict["operator_review_required"] is True
    assert bundle_dict["verification_status"] == "planned-only"

    # Verify the structure has all components
    assert "target_profile" in bundle_dict
    assert "command_authority_check" in bundle_dict
    assert "session_configuration" in bundle_dict
    assert "repo_map" in bundle_dict
    assert "context_pack" in bundle_dict
    assert "prepare_package" in bundle_dict
    assert "goose_projection" in bundle_dict
    assert "goose_wrapper_plan" in bundle_dict
    assert "verification_profile_report" in bundle_dict
    assert "handoff_note" in bundle_dict
    assert "deepagents_readiness" in bundle_dict
    assert "governance" in bundle_dict


    # Governance checks (fail-closed denials)
    gov = bundle_dict["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["source_writes"] == "DISABLED"
    assert gov["target_repo_writes"] == "DISABLED"
    assert gov["memory_mutation"] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"

    # Assert that no platform-spine artifact refs use "f" * 64
    for ref in bundle_dict["prepare_package"]["artifact_refs"]:
        sha = ref["sha256"]
        assert sha != "f" * 64, f"Placeholder hash found in ref: {ref}"
        assert len(sha) == 64
        # Assert it only contains hex characters
        int(sha, 16)

    # Check references inside handoff note too
    for key in ("session_ref", "goose_readonly_session_ref", "verification_report_ref"):
        ref = bundle_dict["handoff_note"][key]
        sha = ref["sha256"]
        assert sha != "f" * 64, f"Placeholder hash found in handoff ref: {ref}"
        assert len(sha) == 64
        int(sha, 16)


def test_prepare_platform_spine_omits_code_vault_when_disabled(tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    bundle = kernel.prepare_platform_spine(
        settings,
        "builder",
        repo_path=str(repo),
        task="run builder-ii local developer check",
        include_code_vault=False,
    )
    bundle_dict = bundle.to_dict()

    assert "hierarchical_frame" not in bundle_dict
    assert "code_vault_enrichment" not in bundle_dict["context_pack"]
    assert not any(
        ref["path"] == "hierarchical-frame.json" for ref in bundle_dict["prepare_package"]["artifact_refs"]
    )


@patch("builder_ii.convention_kernel.create_session_workflow_plan")
def test_prepare_platform_spine_rejects_unsafe_governance(mock_create, tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to return an unsafe governance block
    from builder_ii.session_workflow import create_session_workflow_plan as orig_create_session

    def unsafe_create_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        res["governance"]["runtime_execution"] = "AUTHORIZED"  # Unsafe!
        return res

    mock_create.side_effect = unsafe_create_session

    with pytest.raises(ValueError, match="unsafe governance block"):
        kernel.prepare_platform_spine(
            settings,
            "builder",
            repo_path=str(repo),
        )


@patch("builder_ii.convention_kernel.create_session_workflow_plan")
def test_prepare_platform_spine_rejects_unregistered_command(mock_create, tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to inject an unregistered planned command
    from builder_ii.session_workflow import create_session_workflow_plan as orig_create_session

    def unregistered_cmd_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        res["planned_commands"].append("builder-unknown-dangerous-cmd --execute-all")
        return res

    mock_create.side_effect = unregistered_cmd_session

    with pytest.raises(ValueError, match="unregistered"):
        kernel.prepare_platform_spine(
            settings,
            "builder",
            repo_path=str(repo),
        )


def test_prepare_platform_spine_rejects_unmarked_tier2_command(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to inject a Tier 2 command
    import builder_ii.convention_kernel

    orig_create_session = builder_ii.convention_kernel.create_session_workflow_plan

    def unmarked_tier2_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        # builder start is Tier 2, but let's add it without permitting it in operator_managed_commands
        # We can pass an empty operator_managed_commands list to prepare_platform_spine
        return res

    monkeypatch.setattr(builder_ii.convention_kernel, "create_session_workflow_plan", unmarked_tier2_session)

    # Empty operator_managed_commands list should fail because "builder start" is Tier 2
    with pytest.raises(ValueError, match="classified above permitted tier and lacks explicit"):
        kernel.prepare_platform_spine(
            settings,
            "builder",
            repo_path=str(repo),
            operator_managed_commands=[],
        )


def test_artifact_validation_and_chain_registration():
    # Make sure validators register the new kind
    assert CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND in _VALIDATORS
    assert CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND in CHAIN_VALIDATORS


def test_governance_safety_rejects_missing_keys():
    # Helper base artifact
    art = {
        "kind": CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
        "governance": {
            "runtime_execution": "DISABLED",
            "runtime_activation": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }

    # Verify happy path
    assert check_artifact_governance_safety(art) == []

    # Verify missing critical key fails
    bad_art = json.loads(json.dumps(art))
    del bad_art["governance"]["model_execution"]
    errors = check_artifact_governance_safety(bad_art)
    assert any("missing required critical key: model_execution" in err for err in errors)

    # Verify missing kind-specific key fails
    bad_art2 = json.loads(json.dumps(art))
    del bad_art2["governance"]["target_repo_writes"]
    errors = check_artifact_governance_safety(bad_art2)
    assert any("platform bundle governance block missing key: target_repo_writes" in err for err in errors)


def test_command_match_exact_and_fallback_ambiguity():
    from builder_ii.convention_kernel import find_matching_record

    # 1. Exact match works
    rec = find_matching_record("builder-context pack --target builder")
    assert rec is not None
    assert rec.name == "builder-context pack"

    # 2. Command group prefix fallback works for unregistered subcommands. The record answers for the
    #    command asked about, not for the group it borrowed authority from -- flags are not part of a
    #    command's name, so they are dropped, and `inherited_from` carries the group.
    rec_fallback = find_matching_record("builder-context unregistered-subcommand --arg")
    assert rec_fallback is not None
    assert rec_fallback.name == "builder-context unregistered-subcommand"
    assert rec_fallback.inherited_from == "builder-context"

    # 3. No fallback for non-command-groups
    rec_none = find_matching_record("builder-context pack unregistered-subcommand")
    assert rec_none is None


def test_group_fallback_hands_down_a_tier_ceiling_and_no_capability_flags():
    """`builder-code-vault` declares `allows_artifact_writes`. `builder-code-vault <anything>` must not.

    The fallback stands the group in for a subcommand nobody registered. The group's tier and
    promotion state are a ceiling the subcommand cannot exceed, so those carry down. Its capability
    flags describe the group, and handing them to an unwritten command grants authority by name.
    """
    from builder_ii.command_authority import CAPABILITY_FLAGS, get_command_record
    from builder_ii.convention_kernel import find_matching_record

    group = get_command_record("builder-code-vault")
    assert group is not None and group.allows_artifact_writes, "this pin is vacuous if the group declares nothing"

    resolved = find_matching_record("builder-code-vault nonsense")
    assert resolved is not None
    assert resolved.name == "builder-code-vault nonsense", "the record answers for the command that was asked about"
    assert resolved.tier == group.tier and resolved.promotion_state == group.promotion_state
    assert not any(getattr(resolved, flag) for flag in CAPABILITY_FLAGS), "the group's flags were handed down"
    assert resolved.authority_is_inherited and resolved.inherited_from == "builder-code-vault"


def test_a_stand_in_record_never_inherits_from_itself():
    """The fallback record is a copy, so it names a source, and the source is another record.

    An earlier version left the group's own name on the copy while also marking it inherited, so it
    said `builder-code-vault` inherits from `builder-code-vault`: a copy reported as a declaration,
    wearing the name of a group that really does declare `allows_artifact_writes` while carrying
    none. `inheritance_errors` is the single checker the registry is held to; the stand-in record is
    held to the same one, because `validate_registry_invariants` never sees it.
    """
    from builder_ii.command_authority import inheritance_errors
    from builder_ii.convention_kernel import find_matching_record

    for command in ("builder-code-vault nonsense", "builder-goose frobnicate"):
        resolved = find_matching_record(command)
        assert resolved is not None, command
        assert resolved.authority_is_inherited, command
        assert resolved.inherited_from != resolved.name, f"{command} inherits from itself"
        assert inheritance_errors(resolved) == [], command


def test_a_group_that_declares_runtime_authority_does_not_delegate_it():
    """`builder-runtime` declares `runtime_start`. No unregistered subcommand may resolve to it.

    Note what the group holds versus what its declared subcommand holds: `builder-runtime` declares
    `runtime_start`, and `builder-runtime status` -- which someone wrote down -- declares only
    `readonly_subprocess` and `external_tool_invocation`. That gap is exactly the authority an
    unregistered `builder-runtime <x>` would acquire for free if group-ness implied delegation.
    """
    from builder_ii.command_authority import get_command_record
    from builder_ii.convention_kernel import find_matching_record

    group = get_command_record("builder-runtime")
    assert group is not None and group.allows_runtime_start and group.is_command_group

    assert find_matching_record("builder-runtime frobnicate") is None

    exact = find_matching_record("builder-runtime status")
    assert exact is not None and exact.name == "builder-runtime status"
    assert not exact.authority_is_inherited, "`builder-runtime status` is declared"
    assert not exact.allows_runtime_start, "the declared subcommand claims less than its group"
    assert exact.allows_readonly_subprocess


def test_platform_bundle_validation_checks_child_artifact_governance(tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    bundle = kernel.prepare_platform_spine(
        settings,
        "builder",
        repo_path=str(repo),
    )
    bundle_dict = bundle.to_dict()
    bundle_dict["repo_map"]["governance"]["runtime_execution"] = "AUTHORIZED"

    errors = validate_convention_kernel_platform_bundle(bundle_dict)
    assert any(
        "repo_map: governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in err
        for err in errors
    )


def test_platform_bundle_reference_extraction_handles_missing_handoff_note():
    from builder_ii.artifact_chain_verification import extract_references

    refs = extract_references(
        {
            "kind": CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
            "handoff_note": None,
        }
    )
    assert refs == []
