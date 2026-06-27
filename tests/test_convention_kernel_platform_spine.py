from __future__ import annotations

import json
from pathlib import Path
import pytest

from builder_ii.config import load_settings
from builder_ii.convention_kernel import (
    ConventionKernel,
    ConventionKernelPlatformBundle,
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    validate_convention_kernel_platform_bundle,
    check_artifact_governance_safety,
)
from builder_ii.artifact_index_records import _VALIDATORS
from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS

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


def test_prepare_platform_spine_rejects_unsafe_governance(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to return an unsafe governance block
    from builder_ii import convention_kernel
    import builder_ii.convention_kernel

    orig_create_session = builder_ii.convention_kernel.create_session_workflow_plan

    def unsafe_create_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        res["governance"]["runtime_execution"] = "AUTHORIZED"  # Unsafe!
        return res

    monkeypatch.setattr(builder_ii.convention_kernel, "create_session_workflow_plan", unsafe_create_session)

    with pytest.raises(ValueError, match="unsafe governance block"):
        kernel.prepare_platform_spine(
            settings,
            "builder",
            repo_path=str(repo),
        )


def test_prepare_platform_spine_rejects_unregistered_command(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to inject an unregistered planned command
    from builder_ii import convention_kernel
    import builder_ii.convention_kernel

    orig_create_session = builder_ii.convention_kernel.create_session_workflow_plan

    def unregistered_cmd_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        res["planned_commands"].append("builder-unknown-dangerous-cmd --execute-all")
        return res

    monkeypatch.setattr(builder_ii.convention_kernel, "create_session_workflow_plan", unregistered_cmd_session)

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
    from builder_ii import convention_kernel
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
        }
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

    # 2. Command group prefix fallback works for unregistered subcommands
    rec_fallback = find_matching_record("builder-context unregistered-subcommand --arg")
    assert rec_fallback is not None
    assert rec_fallback.name == "builder-context"

    # 3. No fallback for non-command-groups
    rec_none = find_matching_record("builder-context pack unregistered-subcommand")
    assert rec_none is None

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
        "repo_map: governance.runtime_execution must be DISABLED" in err
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
