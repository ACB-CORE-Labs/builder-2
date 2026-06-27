from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    create_governed_prepare_package,
    validate_governed_prepare_package,
    validate_governed_prepare_package_file,
)
from builder_ii.session_cli import session_app


ROOT = Path(__file__).resolve().parents[1]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    return repo


def test_create_governed_prepare_package_writes_expected_artifacts(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    package = create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
        task="prepare generic session",
    )

    assert package["kind"] == GOVERNED_PREPARE_PACKAGE_KIND
    assert validate_governed_prepare_package(package) == []

    expected_files = [
        "session-workflow.json",
        "goose-readonly-session.json",
        "verification-profile-report.json",
        "handoff-note.json",
        "deepagents-bridge-readiness.json",
        "prepare-package.json",
    ]

    for name in expected_files:
        assert (output_dir / name).exists(), name

    assert validate_governed_prepare_package_file(output_dir / "prepare-package.json") == []


def test_prepare_package_manifest_is_prepared_only_and_non_authoritative(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    package = create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    assert package["package_state"] == "PREPARED_ONLY"
    assert package["runtime_execution_performed"] is False
    assert package["target_repo_writes_performed"] is False

    governance = package["governance"]
    assert governance["runtime_execution"] == "DISABLED"
    assert governance["shell_execution"] == "DISABLED"
    assert governance["target_repo_writes"] == "DISABLED"
    assert governance["goose_activation"] == "DISABLED"
    assert governance["deepagents_delegation"] == "DISABLED"
    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"


def test_prepare_package_artifact_refs_have_hashes_and_relative_paths(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    package = create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    refs = package["artifact_refs"]
    assert len(refs) == 5

    for ref in refs:
        assert ref["path"]
        assert not Path(ref["path"]).is_absolute()
        assert len(ref["sha256"]) == 64
        assert (output_dir / ref["path"]).exists()


def test_prepare_package_handoff_does_not_claim_completed_verification(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    handoff = json.loads((output_dir / "handoff-note.json").read_text(encoding="utf-8"))
    assert handoff["verification_claim"] == "NOT_CLAIMED"
    assert handoff["governance"]["claims_verification_passed"] is False


def test_prepare_package_can_omit_deepagents_readiness(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    package = create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
        include_deepagents_readiness=False,
    )

    assert len(package["artifact_refs"]) == 4
    assert not (output_dir / "deepagents-bridge-readiness.json").exists()


def test_prepare_package_cli_writes_package(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"
    runner = CliRunner()

    result = runner.invoke(
        session_app,
        [
            "prepare-package",
            "generic",
            "--repo-path",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--task",
            "prepare generic session",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "prepare-package.json").exists()
    assert "Governed prepare package written" in result.output


def test_prepare_package_source_does_not_import_execution_primitives():
    source = (ROOT / "builder_ii" / "governed_prepare_package.py").read_text(encoding="utf-8")

    forbidden = [
        "subprocess",
        "os.system",
        "Popen",
        "import deepagents",
        "from deepagents",
    ]

    for token in forbidden:
        assert token not in source


def test_validate_prepare_package_directory_accepts_valid_package(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    from builder_ii.governed_prepare_package import validate_governed_prepare_package_directory

    assert validate_governed_prepare_package_directory(output_dir) == []
    assert validate_governed_prepare_package_directory(output_dir / "prepare-package.json") == []


def test_validate_prepare_package_directory_rejects_missing_artifact(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    (output_dir / "handoff-note.json").unlink()

    from builder_ii.governed_prepare_package import validate_governed_prepare_package_directory

    errors = validate_governed_prepare_package_directory(output_dir)
    assert any("does not exist" in error for error in errors)


def test_validate_prepare_package_directory_rejects_hash_mismatch(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    (output_dir / "handoff-note.json").write_text('{"tampered": true}\n', encoding="utf-8")

    from builder_ii.governed_prepare_package import validate_governed_prepare_package_directory

    errors = validate_governed_prepare_package_directory(output_dir)
    assert any("sha256 mismatch" in error for error in errors)


def test_validate_prepare_package_directory_rejects_path_escape(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    manifest_path = output_dir / "prepare-package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_refs"][0]["path"] = "../escaped.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    from builder_ii.governed_prepare_package import validate_governed_prepare_package_directory

    errors = validate_governed_prepare_package_directory(output_dir)
    assert any("escapes the prepare package directory" in error for error in errors)


def test_validate_prepare_package_cli_accepts_valid_package(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"
    runner = CliRunner()

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    result = runner.invoke(
        session_app,
        [
            "validate-prepare-package",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "is valid" in result.output


def test_validate_prepare_package_cli_rejects_invalid_package(tmp_path):
    repo = _make_repo(tmp_path)
    output_dir = tmp_path / "prepare"
    runner = CliRunner()

    create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
    )

    (output_dir / "session-workflow.json").unlink()

    result = runner.invoke(
        session_app,
        [
            "validate-prepare-package",
            str(output_dir),
        ],
    )

    assert result.exit_code == 1
    assert "Validation error" in result.output


def test_validate_prepare_package_docs_state_runtime_boundary():
    doc = (ROOT / "docs" / "VALIDATE_PREPARE_PACKAGE.md").read_text(encoding="utf-8")

    required = [
        "does not prove that planned verification commands have been run",
        "execute shell commands",
        "activate Goose",
        "activate or delegate to deepagents",
        "execute model/runtime work",
        "write to the target repository",
        "touch Deephaven",
        "couple builder-II to CORE Workbench/UI",
    ]

    for phrase in required:
        assert phrase in doc
