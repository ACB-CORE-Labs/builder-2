from __future__ import annotations

import copy
from pathlib import Path

import pytest

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.artifact_index_records import create_artifact_index_record
from builder_ii.profile_pack import create_profile_pack, dumps_profile_pack, validate_profile_pack
from builder_ii.profile_pack_dry_run import (
    PROFILE_PACK_DRY_RUN_KIND,
    create_profile_pack_dry_run,
    dumps_profile_pack_dry_run,
    validate_profile_pack_dry_run,
)
from builder_ii.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    create_profile_pack_manifest,
    dumps_profile_pack_manifest,
    validate_profile_pack_manifest,
)
from builder_ii.profile_pack_render_plan import (
    PROFILE_PACK_RENDER_PLAN_KIND,
    create_profile_pack_render_plan,
    dumps_profile_pack_render_plan,
    validate_profile_pack_render_plan,
)
from builder_ii.profile_pack_validation_report import (
    PROFILE_PACK_VALIDATION_REPORT_KIND,
    create_profile_pack_validation_report,
    dumps_profile_pack_validation_report,
    validate_profile_pack_validation_report,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest(pack_id: str = "test-profile-pack") -> dict:
    return create_profile_pack_manifest(
        pack_id=pack_id,
        target_profile="builder",
        task="test passive profile pack",
        project_root=ROOT,
    )


def test_profile_pack_lifecycle_happy_path(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(dumps_profile_pack_manifest(manifest), encoding="utf-8")

    render_plan = create_profile_pack_render_plan(manifest, manifest_path=manifest_path)
    render_path = tmp_path / "render-plan.json"
    render_path.write_text(dumps_profile_pack_render_plan(render_plan), encoding="utf-8")

    dry_run = create_profile_pack_dry_run(
        manifest,
        render_plan,
        manifest_path=manifest_path,
        render_plan_path=render_path,
    )
    dry_path = tmp_path / "dry-run.json"
    dry_path.write_text(dumps_profile_pack_dry_run(dry_run), encoding="utf-8")

    validation_report = create_profile_pack_validation_report(manifest, subject_path=manifest_path)
    report_path = tmp_path / "validation-report.json"
    report_path.write_text(dumps_profile_pack_validation_report(validation_report), encoding="utf-8")

    pack = create_profile_pack(
        manifest=manifest,
        render_plan=render_plan,
        dry_run=dry_run,
        validation_report=validation_report,
        manifest_path=manifest_path,
        render_plan_path=render_path,
        dry_run_path=dry_path,
        validation_report_path=report_path,
    )
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(dumps_profile_pack(pack), encoding="utf-8")

    assert manifest["kind"] == PROFILE_PACK_MANIFEST_KIND
    assert render_plan["kind"] == PROFILE_PACK_RENDER_PLAN_KIND
    assert dry_run["kind"] == PROFILE_PACK_DRY_RUN_KIND
    assert validation_report["kind"] == PROFILE_PACK_VALIDATION_REPORT_KIND
    assert validation_report["valid"] is True
    assert pack["lifecycle"]["executed"] is False
    assert pack["lifecycle"]["authorized"] is False
    assert pack["lifecycle"]["promoted"] is False
    assert validate_profile_pack_manifest(manifest) == []
    assert validate_profile_pack_render_plan(render_plan) == []
    assert validate_profile_pack_dry_run(dry_run) == []
    assert validate_profile_pack_validation_report(validation_report) == []
    assert validate_profile_pack(pack) == []

    index = create_artifact_index_record(tmp_path)
    assert index["complete"] is True
    assert index["counts"]["known"] == 5

    chain = verify_artifact_chain([manifest_path, render_path, dry_path, report_path, pack_path])
    assert chain["valid"] is True
    assert chain["counts"]["broken_links"] == 0


def test_manifest_rejects_missing_schema_version() -> None:
    manifest = _manifest()
    del manifest["schema_version"]

    assert "schema_version must be 1" in validate_profile_pack_manifest(manifest)


def test_manifest_rejects_unknown_area_and_profile_kind() -> None:
    manifest = _manifest()
    bad = copy.deepcopy(manifest)
    bad["areas"][0]["area"] = "runtime_factories"

    assert "areas[0].area must be a known pack area" in validate_profile_pack_manifest(bad)

    bad = copy.deepcopy(manifest)
    bad["areas"][0]["entries"][0]["profile_kind"] = "runtime_agent"
    errors = validate_profile_pack_manifest(bad)
    assert "areas[0].entries[0].profile_kind must be a known profile kind" in errors
    assert "areas[0].entries[0].content_hash does not match entry content" in errors


def test_manifest_rejects_duplicate_ids() -> None:
    manifest = _manifest()
    duplicate_id = manifest["areas"][0]["entries"][0]["id"]
    manifest["areas"][1]["entries"][0]["id"] = duplicate_id

    assert f"duplicate profile pack entry id: {duplicate_id}" in validate_profile_pack_manifest(manifest)


def test_manifest_rejects_missing_authority_source_refs_and_content_hash() -> None:
    manifest = _manifest()
    entry = manifest["areas"][0]["entries"][0]
    entry.pop("authority_classification")
    entry["source_refs"] = []
    entry.pop("content_hash")

    errors = validate_profile_pack_manifest(manifest)

    assert "areas[0].entries[0].authority_classification must be known" in errors
    assert "areas[0].entries[0].source_refs must be a non-empty list" in errors
    assert "areas[0].entries[0].content_hash must be a SHA-256 hex digest" in errors


def test_manifest_rejects_authority_leakage_boundaries() -> None:
    manifest = _manifest()
    by_kind = {
        entry["profile_kind"]: entry
        for area in manifest["areas"]
        for entry in area["entries"]
    }
    by_kind["tool_profile"]["payload"]["default_policy"] = "allowed"
    by_kind["mcp_policy_stub"]["payload"]["calls_tools"] = True
    by_kind["goose_projection_stub"]["payload"]["starts_goose"] = True
    by_kind["deepagents_projection_stub"]["payload"]["constructs_agents"] = True
    by_kind["model_policy_stub"]["payload"]["calls_models"] = True
    by_kind["verification_profile"]["payload"]["executes_commands"] = True
    by_kind["handoff_profile"]["payload"]["claims_verification_evidence"] = True
    manifest["governance"]["runtime_execution"] = "ENABLED"

    errors = validate_profile_pack_manifest(manifest)

    assert any("payload.default_policy must be denied" in error for error in errors)
    assert any("payload.calls_tools must be false" in error for error in errors)
    assert any("payload.starts_goose must be false" in error for error in errors)
    assert any("payload.constructs_agents must be false" in error for error in errors)
    assert any("payload.calls_models must be false" in error for error in errors)
    assert any("payload.executes_commands must be false" in error for error in errors)
    assert any("payload.claims_verification_evidence must be false" in error for error in errors)
    assert "governance.runtime_execution must be DISABLED" in errors


def test_render_plan_and_dry_run_reject_execution_claims(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(dumps_profile_pack_manifest(manifest), encoding="utf-8")
    plan = create_profile_pack_render_plan(manifest, manifest_path=manifest_path)
    dry_run = create_profile_pack_dry_run(manifest, plan, manifest_path=manifest_path)

    bad_plan = copy.deepcopy(plan)
    bad_plan["planned_outputs"][0]["executes_now"] = True
    bad_plan["render_boundary"]["starts_goose"] = True
    assert "planned_outputs[0].executes_now must be false" in validate_profile_pack_render_plan(bad_plan)
    assert "render_boundary.starts_goose must be false" in validate_profile_pack_render_plan(bad_plan)

    bad_dry_run = copy.deepcopy(dry_run)
    bad_dry_run["checks"][0]["calls_models"] = True
    bad_dry_run["summary"]["verification_status"] = "PASSED"
    assert "checks[0].calls_models must be false" in validate_profile_pack_dry_run(bad_dry_run)
    assert "summary.verification_status must be NOT_RUN" in validate_profile_pack_dry_run(bad_dry_run)


def test_dry_run_rejects_render_plan_from_another_manifest() -> None:
    manifest = _manifest("primary-profile-pack")
    other_manifest = _manifest("other-profile-pack")
    other_plan = create_profile_pack_render_plan(other_manifest)

    with pytest.raises(ValueError, match="render plan does not match manifest"):
        create_profile_pack_dry_run(manifest, other_plan)


def test_profile_pack_rejects_render_plan_from_another_pack() -> None:
    manifest = _manifest("primary-profile-pack")
    render_plan = create_profile_pack_render_plan(manifest)
    dry_run = create_profile_pack_dry_run(manifest, render_plan)
    validation_report = create_profile_pack_validation_report(manifest)

    other_manifest = _manifest("other-profile-pack")
    other_render_plan = create_profile_pack_render_plan(other_manifest)

    with pytest.raises(ValueError, match="lifecycle artifacts are not bound"):
        create_profile_pack(
            manifest=manifest,
            render_plan=other_render_plan,
            dry_run=dry_run,
            validation_report=validation_report,
        )


def test_profile_pack_rejects_dry_run_from_another_pack() -> None:
    manifest = _manifest("primary-profile-pack")
    render_plan = create_profile_pack_render_plan(manifest)
    validation_report = create_profile_pack_validation_report(manifest)

    other_manifest = _manifest("other-profile-pack")
    other_render_plan = create_profile_pack_render_plan(other_manifest)
    other_dry_run = create_profile_pack_dry_run(other_manifest, other_render_plan)

    with pytest.raises(ValueError, match="lifecycle artifacts are not bound"):
        create_profile_pack(
            manifest=manifest,
            render_plan=render_plan,
            dry_run=other_dry_run,
            validation_report=validation_report,
        )


def test_profile_pack_rejects_invalid_validation_report() -> None:
    manifest = _manifest()
    render_plan = create_profile_pack_render_plan(manifest)
    dry_run = create_profile_pack_dry_run(manifest, render_plan)
    invalid_subject = copy.deepcopy(manifest)
    del invalid_subject["schema_version"]
    invalid_report = create_profile_pack_validation_report(invalid_subject)

    with pytest.raises(ValueError, match="validation_report.valid must be true"):
        create_profile_pack(
            manifest=manifest,
            render_plan=render_plan,
            dry_run=dry_run,
            validation_report=invalid_report,
        )


def test_profile_pack_rejects_validation_report_for_unrelated_subject() -> None:
    manifest = _manifest("primary-profile-pack")
    render_plan = create_profile_pack_render_plan(manifest)
    dry_run = create_profile_pack_dry_run(manifest, render_plan)
    unrelated_report = create_profile_pack_validation_report(_manifest("other-profile-pack"))

    with pytest.raises(ValueError, match="subject_ref.sha256 must match"):
        create_profile_pack(
            manifest=manifest,
            render_plan=render_plan,
            dry_run=dry_run,
            validation_report=unrelated_report,
        )


def test_validation_report_distinguishes_validated_from_promoted() -> None:
    report = create_profile_pack_validation_report(_manifest())

    assert report["claims"]["validated"] is True
    assert report["claims"]["executed"] is False
    assert report["claims"]["authorized"] is False
    assert report["claims"]["promoted"] is False
    assert validate_profile_pack_validation_report(report) == []
