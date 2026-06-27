from __future__ import annotations

import pytest
from pathlib import Path

from builder_ii.release_manifest import (
    V0_RELEASE_MANIFEST_KIND,
    create_artifact_ref,
    create_v0_release_manifest,
    validate_v0_release_manifest,
    validate_v0_release_manifest_file,
    write_v0_release_manifest,
)


def _sample_session_proof() -> dict:
    return {
        "prepare_package_ref": create_artifact_ref(kind="builder_ii.governed_prepare_package", path="prepare-package.json", sha256="a" * 64),
        "session_workflow_ref": create_artifact_ref(kind="builder_ii.session_workflow_plan", path="session-workflow.json", sha256="b" * 64),
        "goose_readonly_session_ref": create_artifact_ref(kind="builder_ii.goose_readonly_session_plan", path="goose-readonly-session.json", sha256="c" * 64),
        "verification_report_ref": create_artifact_ref(kind="builder_ii.verification_profile_report", path="verification-profile-report.json", sha256="d" * 64),
        "repo_map_ref": create_artifact_ref(kind="builder_ii.repo_map", path="repo-map.json", sha256="e" * 64),
        "context_pack_ref": create_artifact_ref(kind="builder_ii.context_pack", path="context-pack.json", sha256="f" * 64),
        "handoff_note_ref": create_artifact_ref(kind="builder_ii.handoff_note", path="handoff-note.json", sha256="1" * 64),
        "deepagents_readiness_ref": create_artifact_ref(kind="builder_ii.deepagents_bridge_readiness_report", path="deepagents-bridge-readiness.json", sha256="2" * 64),
    }


def _sample_spine_proof() -> dict:
    return {
        "platform_spine_ref": create_artifact_ref(kind="builder_ii.convention_kernel_platform_bundle", path="platform-spine.json", sha256="3" * 64),
    }


def _sample_audit_refs() -> dict:
    return {
        "artifact_index_ref": create_artifact_ref(kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256=""),
        "chain_verification_report_ref": create_artifact_ref(kind="builder_ii.artifact_chain_verification_report", path="chain-verification-report.json", sha256="4" * 64),
    }


def test_create_v0_release_manifest_happy_path(tmp_path: Path) -> None:
    manifest = create_v0_release_manifest(
        governed_session_proof=_sample_session_proof(),
        platform_spine_proof=_sample_spine_proof(),
        audit_references=_sample_audit_refs(),
    )
    assert manifest["kind"] == V0_RELEASE_MANIFEST_KIND
    assert manifest["schema_version"] == 1
    assert manifest["governance"]["runtime_execution"] == "DISABLED"
    assert manifest["governance"]["model_execution_loops"] == "DISABLED"
    assert manifest["governance"]["shell_execution"] == "DISABLED"
    assert manifest["governance"]["source_patches_applied"] == "DISABLED"
    assert manifest["governance"]["autonomous_agent_authority"] == "DISABLED"
    assert manifest["governance"]["deephaven_touch"] == "DISABLED"
    assert manifest["governance"]["proof_of_capability_only"] is True
    assert manifest["governance"]["runtime_executor"] is False

    errors = validate_v0_release_manifest(manifest)
    assert errors == []

    out_path = tmp_path / "release-manifest.json"
    write_v0_release_manifest(manifest, out_path)
    file_errors = validate_v0_release_manifest_file(out_path)
    assert file_errors == []


def test_v0_release_manifest_adversarial_mutations() -> None:
    manifest = create_v0_release_manifest(
        governed_session_proof=_sample_session_proof(),
        platform_spine_proof=_sample_spine_proof(),
        audit_references=_sample_audit_refs(),
    )

    # Test runtime execution enabled
    m1 = dict(manifest)
    m1["governance"] = dict(m1["governance"], runtime_execution="ENABLED")
    assert any("governance.runtime_execution" in e for e in validate_v0_release_manifest(m1))

    # Test model loop enabled
    m2 = dict(manifest)
    m2["governance"] = dict(m2["governance"], model_execution_loops="ENABLED")
    assert any("governance.model_execution_loops" in e for e in validate_v0_release_manifest(m2))

    # Test shell execution enabled
    m3 = dict(manifest)
    m3["governance"] = dict(m3["governance"], shell_execution="ENABLED")
    assert any("governance.shell_execution" in e for e in validate_v0_release_manifest(m3))

    # Test source patches applied
    m4 = dict(manifest)
    m4["governance"] = dict(m4["governance"], source_patches_applied="ENABLED")
    assert any("governance.source_patches_applied" in e for e in validate_v0_release_manifest(m4))

    # Test autonomous agent authority
    m5 = dict(manifest)
    m5["governance"] = dict(m5["governance"], autonomous_agent_authority="ENABLED")
    assert any("governance.autonomous_agent_authority" in e for e in validate_v0_release_manifest(m5))

    # Test deephaven touch
    m6 = dict(manifest)
    m6["governance"] = dict(m6["governance"], deephaven_touch="ENABLED")
    assert any("governance.deephaven_touch" in e for e in validate_v0_release_manifest(m6))

    # Test invalid repo
    m7 = dict(manifest)
    m7["release_identity"] = dict(m7["release_identity"], repository="BadRepo/Other")
    assert any("release_identity.repository" in e for e in validate_v0_release_manifest(m7))

    # Test empty sha256 on a regular reference (e.g. prepare_package_ref) -> should fail
    m8 = dict(manifest)
    m8["governed_session_proof"] = dict(
        m8["governed_session_proof"],
        prepare_package_ref=create_artifact_ref(kind="builder_ii.governed_prepare_package", path="prepare-package.json", sha256="")
    )
    assert any("governed_session_proof.prepare_package_ref.sha256" in e for e in validate_v0_release_manifest(m8))

    # Test empty sha256 on artifact_index_ref -> should succeed
    m9 = dict(manifest)
    m9["audit_references"] = dict(
        m9["audit_references"],
        artifact_index_ref=create_artifact_ref(kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256="")
    )
    assert validate_v0_release_manifest(m9) == []

def test_v0_release_manifest_requires_required_refs() -> None:
    manifest = create_v0_release_manifest(
        governed_session_proof=_sample_session_proof(),
        platform_spine_proof=_sample_spine_proof(),
        audit_references=_sample_audit_refs(),
    )

    missing_session = dict(manifest)
    session_proof = dict(missing_session["governed_session_proof"])
    session_proof.pop("prepare_package_ref")
    missing_session["governed_session_proof"] = session_proof
    assert any(
        "governed_session_proof.prepare_package_ref is required" in e
        for e in validate_v0_release_manifest(missing_session)
    )

    missing_spine = dict(manifest)
    missing_spine["platform_spine_proof"] = {}
    assert any(
        "platform_spine_proof.platform_spine_ref is required" in e
        for e in validate_v0_release_manifest(missing_spine)
    )

    missing_index = dict(manifest)
    audit_refs = dict(missing_index["audit_references"])
    audit_refs.pop("artifact_index_ref")
    missing_index["audit_references"] = audit_refs
    assert any(
        "audit_references.artifact_index_ref is required" in e
        for e in validate_v0_release_manifest(missing_index)
    )

    missing_chain = dict(manifest)
    audit_refs = dict(missing_chain["audit_references"])
    audit_refs.pop("chain_verification_report_ref")
    missing_chain["audit_references"] = audit_refs
    assert any(
        "audit_references.chain_verification_report_ref is required" in e
        for e in validate_v0_release_manifest(missing_chain)
    )


def test_v0_release_manifest_validates_release_identity_fields() -> None:
    manifest = create_v0_release_manifest(
        governed_session_proof=_sample_session_proof(),
        platform_spine_proof=_sample_spine_proof(),
        audit_references=_sample_audit_refs(),
    )

    for field in ("release_version", "target_profile", "task"):
        mutated = dict(manifest)
        mutated["release_identity"] = dict(mutated["release_identity"], **{field: ""})
        assert any(
            f"release_identity.{field} must be a non-empty string" in e
            for e in validate_v0_release_manifest(mutated)
        )
