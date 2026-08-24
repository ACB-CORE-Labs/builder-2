from __future__ import annotations

from pathlib import Path

from builder_ii.core.release_manifest import (
    RELEASE_PROOF_BUNDLE_KIND,
    REQUIRED_RELEASE_LANES,
    V0_RELEASE_MANIFEST_KIND,
    create_artifact_ref,
    create_release_evidence,
    create_release_proof_bundle,
    create_v0_release_manifest,
    validate_release_evidence,
    validate_release_proof_bundle,
    validate_release_proof_bundle_file,
    validate_v0_release_manifest,
    validate_v0_release_manifest_file,
    write_release_proof_bundle,
    write_v0_release_manifest,
)


def _sample_release_bundle() -> dict:
    evidence = {
        lane: {
            "result": "PASS",
            "ref": create_artifact_ref(
                kind=f"builder_ii.release_evidence.{lane}", path=f"evidence/{lane}.json", sha256="a" * 64
            ),
        }
        for lane in REQUIRED_RELEASE_LANES
    }
    return create_release_proof_bundle(
        source={
            "commit": "1" * 40,
            "parents": ["2" * 40],
            "tree": "3" * 40,
            "clean": True,
            "uv_lock_sha256": "4" * 64,
            "source_archive_sha256": "5" * 64,
        },
        distributions=[
            {"type": "sdist", "filename": "builder_ii-1.0.0.tar.gz", "size": 10, "sha256": "6" * 64},
            {
                "type": "wheel",
                "filename": "builder_ii-1.0.0-py3-none-any.whl",
                "size": 20,
                "sha256": "7" * 64,
                "record_inventory": ["builder_ii/__init__.py", "builder_ii/tui/stratum.tcss"],
            },
        ],
        supported_runtime={
            "python": ">=3.12.13,<3.13",
            "macos_apple_silicon": "SUPPORTED_MLX_PRIMARY",
            "linux": "SUPPORTED_NO_MLX_PARITY",
            "windows": "UNSUPPORTED_V1",
            "wsl2": "UNSUPPORTED_V1",
        },
        evidence=evidence,
        artifact_index_ref=create_artifact_ref(
            kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256="8" * 64
        ),
        payload_custody=[{"path": "source.tar", "size": 1, "sha256": "9" * 64}],
    )


def test_release_proof_bundle_is_exact_candidate_evidence_not_authority(tmp_path: Path) -> None:
    bundle = _sample_release_bundle()
    assert bundle["kind"] == RELEASE_PROOF_BUNDLE_KIND
    assert bundle["release_identity"]["package_version"] == "1.0.0"
    assert bundle["authority"]["tag_creation"] == "NOT_AUTHORIZED"
    assert bundle["governance"]["artifact_is_authority"] is False
    assert validate_release_proof_bundle(bundle) == []

    path = tmp_path / "release-proof-bundle.json"
    write_release_proof_bundle(bundle, path)
    assert validate_release_proof_bundle_file(path) == []


def test_release_proof_bundle_rejects_missing_failed_or_authorizing_evidence() -> None:
    bundle = _sample_release_bundle()
    missing = dict(bundle)
    missing["evidence"] = dict(bundle["evidence"])
    missing["evidence"].pop("linux_golden_path")
    assert any("evidence.linux_golden_path" in error for error in validate_release_proof_bundle(missing))

    failed = dict(bundle)
    failed["evidence"] = dict(bundle["evidence"])
    failed["evidence"]["local_ci"] = dict(failed["evidence"]["local_ci"], result="FAIL")
    assert any("evidence.local_ci.result" in error for error in validate_release_proof_bundle(failed))

    promoted = dict(bundle)
    promoted["authority"] = dict(bundle["authority"], capability_promotion="AUTHORIZED")
    assert any("authority.capability_promotion" in error for error in validate_release_proof_bundle(promoted))


def test_release_proof_bundle_rejects_wrong_candidate_and_incomplete_distributions() -> None:
    bundle = _sample_release_bundle()
    wrong_source = dict(bundle)
    wrong_source["source"] = dict(bundle["source"], clean=False)
    assert "source.clean must be true" in validate_release_proof_bundle(wrong_source)

    wheel_only = dict(bundle)
    wheel_only["distributions"] = [bundle["distributions"][1]]
    assert any("missing required types: sdist" in error for error in validate_release_proof_bundle(wheel_only))

    duplicate_wheel = dict(bundle)
    duplicate_wheel["distributions"] = [*bundle["distributions"], dict(bundle["distributions"][1])]
    assert any("exactly one wheel" in error for error in validate_release_proof_bundle(duplicate_wheel))

    duplicate_sdist = dict(bundle)
    duplicate_sdist["distributions"] = [*bundle["distributions"], dict(bundle["distributions"][0])]
    assert any("exactly one sdist" in error for error in validate_release_proof_bundle(duplicate_sdist))


def _release_evidence(lane: str, *, system: str = "Darwin", machine: str = "arm64", wheel_sha: str = "7" * 64) -> dict:
    claims: dict = {}
    if lane == "macos_apple_silicon_golden_path":
        claims = {"installed_extras": ["apple", "deepagents"], "golden_path_steps_passed": True, "mlx_ready": True}
    elif lane == "linux_golden_path":
        claims = {"installed_extras": ["deepagents"], "golden_path_steps_passed": True, "mlx_installed": False}
    return create_release_evidence(
        lane=lane,
        result="PASS",
        platform={"system": system, "machine": machine, "python": "3.12.13", "implementation": "CPython"},
        candidate={"wheel": "builder_ii-1.0.0-py3-none-any.whl", "wheel_sha256": wheel_sha},
        commands=[{"name": "golden path", "result": "PASS"}],
        source={"commit": "1" * 40, "tree": "3" * 40},
        runtime_versions={
            "python": "3.12.13",
            "uv": "uv 0.8",
            "git": "git 2.50",
            "goose": "goose 1.46",
            "container_runtime": "NOT_APPLICABLE",
        },
        elapsed_seconds=1,
        skips=[],
        log_refs=[
            create_artifact_ref(kind="builder_ii.release_log", path="evidence/constituents/run.log", sha256="a" * 64)
        ],
        claims=claims,
    )


def test_release_evidence_rejects_wrong_host_and_cross_candidate_wheel() -> None:
    mac = _release_evidence("macos_apple_silicon_golden_path")
    wrong_machine = dict(mac, platform=dict(mac["platform"], machine="x86_64"))
    assert any("platform.machine" in error for error in validate_release_evidence(wrong_machine))

    linux = _release_evidence("linux_golden_path", system="Linux", machine="aarch64")
    wrong_system = dict(linux, platform=dict(linux["platform"], system="Darwin"))
    assert any("platform.system" in error for error in validate_release_evidence(wrong_system))
    assert any("bundle wheel" in error for error in validate_release_evidence(linux, expected_wheel_sha256="b" * 64))


def test_release_evidence_rejects_forged_ci_benchmark_and_chain_claims() -> None:
    base = {
        "result": "PASS",
        "platform": {"system": "Darwin", "machine": "arm64", "python": "3.12.13", "implementation": "CPython"},
        "candidate": {"wheel": "builder_ii-1.0.0-py3-none-any.whl", "wheel_sha256": "7" * 64},
        "commands": [{"name": "proof", "result": "PASS"}],
        "source": {"commit": "1" * 40, "tree": "3" * 40},
        "runtime_versions": {
            "python": "3.12.13",
            "uv": "uv",
            "git": "git",
            "goose": "goose",
            "container_runtime": "docker",
        },
        "elapsed_seconds": 1,
        "skips": [],
        "log_refs": [
            create_artifact_ref(kind="builder_ii.release_log", path="evidence/constituents/run.log", sha256="a" * 64)
        ],
    }
    ci_ref = create_artifact_ref(
        kind="builder_ii.gate_battery_receipt", path="evidence/constituents/ci.json", sha256="b" * 64
    )
    ci = create_release_evidence(
        lane="local_ci",
        claims={"ci_receipt_ref": ci_ref, "blocking_gate_skips": 0, "blocking_gate_failures": 0},
        **base,
    )
    forged_ci = dict(ci, claims=dict(ci["claims"], blocking_gate_skips=1))
    assert any("blocking_gate_skips" in error for error in validate_release_evidence(forged_ci))

    benchmark_refs = {
        "benchmark_manifest_ref": create_artifact_ref(
            kind="builder_ii.model_runtime_benchmark_manifest",
            path="evidence/constituents/benchmark-manifest.json",
            sha256="c" * 64,
        ),
        "benchmark_report_ref": create_artifact_ref(
            kind="builder_ii.model_runtime_benchmark_report",
            path="evidence/constituents/benchmark-report.json",
            sha256="d" * 64,
        ),
        "methodology_sha256": "e" * 64,
        "physical_evidence_sha256": "f" * 64,
        "current_validation_passed": True,
    }
    benchmark = create_release_evidence(lane="plan_set_5_benchmark", claims=benchmark_refs, **base)
    stale = dict(benchmark, claims=dict(benchmark["claims"], current_validation_passed=False))
    assert any("current_validation_passed" in error for error in validate_release_evidence(stale))

    chain_ref = create_artifact_ref(
        kind="builder_ii.artifact_chain_verification_report", path="evidence/constituents/chain.json", sha256="1" * 64
    )
    chain = create_release_evidence(
        lane="artifact_chain",
        claims={"chain_report_ref": chain_ref, "valid": True, "broken_links": 0, "native_invalid": 0},
        **base,
    )
    forged_chain = dict(chain, claims=dict(chain["claims"], broken_links=1))
    assert any("broken_links" in error for error in validate_release_evidence(forged_chain))


def _sample_session_proof() -> dict:
    return {
        "prepare_package_ref": create_artifact_ref(
            kind="builder_ii.governed_prepare_package", path="prepare-package.json", sha256="a" * 64
        ),
        "session_workflow_ref": create_artifact_ref(
            kind="builder_ii.session_workflow_plan", path="session-workflow.json", sha256="b" * 64
        ),
        "goose_readonly_session_ref": create_artifact_ref(
            kind="builder_ii.goose_readonly_session_plan", path="goose-readonly-session.json", sha256="c" * 64
        ),
        "verification_report_ref": create_artifact_ref(
            kind="builder_ii.verification_profile_report", path="verification-profile-report.json", sha256="d" * 64
        ),
        "repo_map_ref": create_artifact_ref(kind="builder_ii.repo_map", path="repo-map.json", sha256="e" * 64),
        "context_pack_ref": create_artifact_ref(
            kind="builder_ii.context_pack", path="context-pack.json", sha256="f" * 64
        ),
        "handoff_note_ref": create_artifact_ref(
            kind="builder_ii.handoff_note", path="handoff-note.json", sha256="1" * 64
        ),
        "deepagents_readiness_ref": create_artifact_ref(
            kind="builder_ii.deepagents_bridge_readiness_report",
            path="deepagents-bridge-readiness.json",
            sha256="2" * 64,
        ),
    }


def _sample_spine_proof() -> dict:
    return {
        "platform_spine_ref": create_artifact_ref(
            kind="builder_ii.convention_kernel_platform_bundle", path="platform-spine.json", sha256="3" * 64
        ),
    }


def _sample_audit_refs() -> dict:
    return {
        "artifact_index_ref": create_artifact_ref(
            kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256=""
        ),
        "chain_verification_report_ref": create_artifact_ref(
            kind="builder_ii.artifact_chain_verification_report", path="chain-verification-report.json", sha256="4" * 64
        ),
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
        prepare_package_ref=create_artifact_ref(
            kind="builder_ii.governed_prepare_package", path="prepare-package.json", sha256=""
        ),
    )
    assert any("governed_session_proof.prepare_package_ref.sha256" in e for e in validate_v0_release_manifest(m8))

    # Test empty sha256 on artifact_index_ref -> should succeed
    m9 = dict(manifest)
    m9["audit_references"] = dict(
        m9["audit_references"],
        artifact_index_ref=create_artifact_ref(
            kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256=""
        ),
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
        "platform_spine_proof.platform_spine_ref is required" in e for e in validate_v0_release_manifest(missing_spine)
    )

    missing_index = dict(manifest)
    audit_refs = dict(missing_index["audit_references"])
    audit_refs.pop("artifact_index_ref")
    missing_index["audit_references"] = audit_refs
    assert any(
        "audit_references.artifact_index_ref is required" in e for e in validate_v0_release_manifest(missing_index)
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
            f"release_identity.{field} must be a non-empty string" in e for e in validate_v0_release_manifest(mutated)
        )


def test_validate_v0_release_manifest_file_edge_cases(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.json"
    errors = validate_v0_release_manifest_file(non_existent)
    assert len(errors) == 1
    assert "file not found" in errors[0]

    invalid_json_file = tmp_path / "invalid.json"
    invalid_json_file.write_text("{bad json", encoding="utf-8")
    errors = validate_v0_release_manifest_file(invalid_json_file)
    assert len(errors) == 1
    assert "invalid JSON" in errors[0]

    dir_path = tmp_path / "some_directory"
    dir_path.mkdir()
    errors = validate_v0_release_manifest_file(dir_path)
    assert len(errors) == 1
    assert "failed to read file" in errors[0]
