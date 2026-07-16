"""Artifact exchange helpers for Maker ↔ Governor merge ceremony."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.wrp.artifacts import (
    GOVERNOR_CERTIFICATION_KIND,
    MAKER_CANDIDATE_MANIFEST_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
    write_wrp,
)


def create_maker_candidate_manifest(
    *,
    wave: str,
    branch: str,
    summary: str,
    artifact_digests: dict[str, str],
    test_commands: list[str],
    test_exit_code: int | None = None,
) -> dict[str, Any]:
    return base_envelope(
        kind=MAKER_CANDIDATE_MANIFEST_KIND,
        artifact_state="EXCHANGE_ONLY",
        capability_state="wrp_exchange_only",
        extra={
            "wave": wave,
            "branch": branch,
            "summary": summary,
            "artifact_digests": dict(artifact_digests),
            "test_metadata": {
                "commands": list(test_commands),
                "exit_code": test_exit_code,
            },
            "self_certified": False,
            "requires_governor_cert": True,
            "grants_authority": False,
        },
    )


def create_governor_certification(
    *,
    wave: str,
    decision: str,
    findings: list[str],
    maker_manifest_digest: str,
    reviewer_model: str = "gemini-3.1-pro",
) -> dict[str, Any]:
    if decision not in {"PASS", "FAIL", "PASS_WITH_NOTES"}:
        raise ValueError("decision must be PASS, FAIL, or PASS_WITH_NOTES")
    return base_envelope(
        kind=GOVERNOR_CERTIFICATION_KIND,
        artifact_state="EXCHANGE_ONLY",
        capability_state="wrp_exchange_only",
        extra={
            "wave": wave,
            "decision": decision,
            "findings": list(findings),
            "maker_manifest_digest": maker_manifest_digest,
            "reviewer_model": reviewer_model,
            "permits_push": decision in {"PASS", "PASS_WITH_NOTES"},
            "grants_execution_authority": False,
            "grants_authority": False,
        },
    )


def validate_maker_candidate_manifest(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=MAKER_CANDIDATE_MANIFEST_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("self_certified") is not False:
        errors.append("self_certified must be false")
    if record.get("requires_governor_cert") is not True:
        errors.append("requires_governor_cert must be true")
    return errors


def validate_governor_certification(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=GOVERNOR_CERTIFICATION_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("decision") not in {"PASS", "FAIL", "PASS_WITH_NOTES"}:
        errors.append("decision invalid")
    if record.get("grants_execution_authority") is not False:
        errors.append("grants_execution_authority must be false")
    return errors


def write_exchange_package(
    root: Path,
    *,
    wave: str,
    maker_manifest: dict[str, Any],
    extra_artifacts: dict[str, dict[str, Any]] | None = None,
) -> Path:
    wave_dir = root / wave
    wave_dir.mkdir(parents=True, exist_ok=True)
    write_wrp(maker_manifest, wave_dir / "maker_candidate_manifest.json")
    if extra_artifacts:
        for name, art in extra_artifacts.items():
            write_wrp(art, wave_dir / f"{name}.json")
    (wave_dir / "governor").mkdir(exist_ok=True)
    readme = wave_dir / "README.md"
    readme.write_text(
        f"# WRP exchange package — {wave}\n\n"
        "Maker artifacts for Antigravity Governor review.\n\n"
        "Start Gemini-3.1-Pro for certification and Gemini-3.5-Flash for scorecards.\n"
        "Write outputs under `governor/`.\n",
        encoding="utf-8",
    )
    return wave_dir
