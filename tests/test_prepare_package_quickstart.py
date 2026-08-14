from __future__ import annotations

import json
from pathlib import Path

from builder_ii.session_cli import session_app
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    return repo


def test_operator_quickstart_prepare_validate_summarize_lane(tmp_path):
    repo = _make_repo(tmp_path)
    package_dir = tmp_path / "prepare-package"
    summary_path = package_dir / "prepare-package-summary.json"
    runner = CliRunner()

    prepare = runner.invoke(
        session_app,
        [
            "prepare-package",
            "generic",
            "--repo-path",
            str(repo),
            "--task",
            "operator quickstart scenario",
            "--output-dir",
            str(package_dir),
        ],
    )
    assert prepare.exit_code == 0, prepare.output
    assert package_dir.exists()

    expected_artifacts = [
        "session-workflow.json",
        "goose-readonly-session.json",
        "verification-profile-report.json",
        "handoff-note.json",
        "deepagents-bridge-readiness.json",
        "prepare-package.json",
    ]

    for artifact_name in expected_artifacts:
        assert (package_dir / artifact_name).exists(), artifact_name

    validate = runner.invoke(
        session_app,
        [
            "validate-prepare-package",
            str(package_dir),
        ],
    )
    assert validate.exit_code == 0, validate.output
    assert "is valid" in validate.output

    summarize = runner.invoke(
        session_app,
        [
            "summarize-prepare-package",
            str(package_dir),
            "--output",
            str(summary_path),
        ],
    )
    assert summarize.exit_code == 0, summarize.output
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["kind"] == "builder_ii.governed_prepare_package_summary"
    assert summary["target_name"] == "generic"
    assert summary["task"] == "operator quickstart scenario"
    assert summary["package_state"] == "PREPARED_ONLY"
    assert summary["validation_state"] == "VALIDATED"
    assert summary["artifact_count"] == 7
    assert summary["runtime_execution_performed"] is False
    assert summary["target_repo_writes_performed"] is False

    governance = summary["governance"]
    assert governance["runtime_execution"] == "DISABLED"
    assert governance["shell_execution"] == "DISABLED"
    assert governance["model_execution"] == "DISABLED"
    assert governance["target_repo_writes"] == "DISABLED"
    assert governance["goose_activation"] == "DISABLED"
    assert governance["deepagents_delegation"] == "DISABLED"
    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"


def test_operator_quickstart_doc_preserves_platform_boundary():
    doc = (ROOT / "docs" / "OPERATOR_QUICKSTART.md").read_text(encoding="utf-8")

    required = [
        "generic governed local agent/developer platform",
        "not CORE Workbench",
        "not CORE UI/UX",
        "not a second CORE runtime",
        "CORE is only a target profile",
    ]

    for phrase in required:
        assert phrase in doc


def test_operator_quickstart_doc_names_complete_lane():
    doc = (ROOT / "docs" / "OPERATOR_QUICKSTART.md").read_text(encoding="utf-8")

    required = [
        "builder-platform status",
        "builder-platform operator-status",
        "builder-platform next",
        "builder-platform golden-path",
        "builder-platform validate-golden-path",
    ]

    for phrase in required:
        assert phrase in doc


def test_operator_quickstart_doc_states_runtime_and_verification_boundaries():
    doc = (ROOT / "docs" / "OPERATOR_QUICKSTART.md").read_text(encoding="utf-8")

    required = [
        "execute shell commands",
        "import or use subprocess",
        "activate Goose",
        "activate or delegate to deepagents",
        "execute model/runtime work",
        "write to the target repository",
        "touch Deephaven",
        "grant runtime authority",
        "claim autonomous writes",
        "invoke MCP or external tools",
        "use hidden memory or vector stores",
        "future execution or source write remains strictly HITL-gated",
    ]

    for phrase in required:
        assert phrase in doc
