from __future__ import annotations

import json
from pathlib import Path

from builder_ii.verification_execution_plan_cli import verify_app
from typer.testing import CliRunner

from builder_ii.lifecycle.candidate.verification_execution_plan import validate_verification_execution_plan_artifact
from builder_ii.lifecycle.candidate.verification_isolation_backend import get_backend
from builder_ii.lifecycle.candidate.verification_isolation_policy import validate_verification_isolation_policy_artifact

runner = CliRunner()


def test_builder_verify_plan_writes_artifact_prints_json_and_validates(tmp_path: Path) -> None:
    output = tmp_path / "verification-execution-plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    printed = json.loads(result.output)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert printed == written
    assert validate_verification_execution_plan_artifact(written) == []
    assert written["execution_enabled"] is False
    assert written["plan_mode"] == "planned_only"


def test_builder_verify_validate_plan_reports_valid(tmp_path: Path) -> None:
    output = tmp_path / "verification-execution-plan.json"
    plan_result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output

    validate_result = runner.invoke(verify_app, ["validate-plan", str(output)])
    assert validate_result.exit_code == 0, validate_result.output
    report = json.loads(validate_result.output)
    assert report == {"errors": [], "path": str(output), "valid": True}


def test_builder_verify_plan_generic_target_validates(tmp_path: Path) -> None:
    # B4.2 (plan 1.3): the operator can plan verification for a generic target repo.
    output = tmp_path / "generic-plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "generic",
            "--verification-profile",
            "generic_basic",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    written = json.loads(output.read_text(encoding="utf-8"))
    assert validate_verification_execution_plan_artifact(written) == []
    assert written["target_profile"] == "generic"
    assert [p["profile"] for p in written["allowed_command_profiles"]] == ["pytest_full"]


def test_builder_verify_plan_output_directory_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "Verification execution plan could not be written:" in result.output
    assert "Traceback" not in result.output


def test_builder_verify_plan_default_omits_isolation_policy(tmp_path: Path) -> None:
    """A1: a default plan (no --isolation) stays byte-identical -- no isolation_policy field at all,
    and the runner reads an absent policy as the 'none' backend."""
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        ["plan", "--target-profile", "builder", "--verification-profile", "builder_full", "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    written = json.loads(output.read_text(encoding="utf-8"))
    assert "isolation_policy" not in written
    assert get_backend(written["target_repo"], written.get("isolation_policy")).name == "none"


def test_builder_verify_plan_docker_isolation_attaches_a_valid_policy(tmp_path: Path) -> None:
    """A1: --isolation docker (with an image) attaches a digest-bound policy that the whole plan
    validates -- exactly the dict the runner reads from plan['isolation_policy'] and routes on.

    The runner *executing* that policy instantiates DockerBackend, which needs a live daemon and a
    local image, so it is a docker-gated integration concern, not this CLI's contract. Here we prove
    the CLI's job: a well-formed, valid docker policy embedded in a valid plan.
    """
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
            "--isolation",
            "docker",
            "--isolation-image",
            "python:3.12-slim",
        ],
    )
    assert result.exit_code == 0, result.output
    written = json.loads(output.read_text(encoding="utf-8"))
    # The whole plan -- including the embedded policy and its digest -- validates.
    assert validate_verification_execution_plan_artifact(written) == []
    policy = written["isolation_policy"]
    assert policy["kind"] == "builder_ii.verification_isolation_policy"
    assert policy["backend"] == "docker"
    assert policy["image_ref"] == "python:3.12-slim"
    assert validate_verification_isolation_policy_artifact(policy) == []


def test_builder_verify_plan_docker_isolation_records_the_image_pin(tmp_path: Path) -> None:
    """A1: --isolation-image / --isolation-image-digest are recorded on the docker policy and keep
    it valid (a pinned image digest is the point of isolating in the first place)."""
    digest = "sha256:" + "a" * 64
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
            "--isolation",
            "docker",
            "--isolation-image",
            "python:3.12-slim",
            "--isolation-image-digest",
            digest,
        ],
    )
    assert result.exit_code == 0, result.output
    policy = json.loads(output.read_text(encoding="utf-8"))["isolation_policy"]
    assert policy["image_ref"] == "python:3.12-slim"
    assert policy["image_digest"] == digest
    assert validate_verification_isolation_policy_artifact(policy) == []


def test_builder_verify_plan_docker_requires_an_image(tmp_path: Path) -> None:
    """A1: docker has no usable default image (DockerBackend rejects a policy without image_ref), so
    --isolation docker without --isolation-image fails fast rather than writing a doomed plan."""
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
            "--isolation",
            "docker",
        ],
    )
    assert result.exit_code != 0
    assert not output.exists()
    assert "isolation" in result.output
    assert "Traceback" not in result.output


def test_builder_verify_plan_rejects_an_unknown_isolation_backend(tmp_path: Path) -> None:
    """A1: only 'none'/'docker'. An unknown backend fails fast and writes no unrunnable plan."""
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
            "--isolation",
            "chroot",
        ],
    )
    assert result.exit_code != 0
    assert not output.exists()
    assert "isolation" in result.output
    assert "Traceback" not in result.output


def test_builder_verify_plan_image_flags_require_docker(tmp_path: Path) -> None:
    """A1: image pins are docker-only. Naming one under the default 'none' is a usage error the CLI
    rejects, not a silent no-op that drops the pin an operator thought they set."""
    output = tmp_path / "plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
            "--isolation-image",
            "python:3.12-slim",
        ],
    )
    assert result.exit_code != 0
    assert not output.exists()
    assert "isolation" in result.output
    assert "Traceback" not in result.output
