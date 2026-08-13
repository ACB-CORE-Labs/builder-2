from pathlib import Path
from typing import Any

from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.adapters.goose.goose_inspection import create_readonly_inspection_audit
from builder_ii.adapters.goose.goose_readonly import create_readonly_runtime_audit
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest
from builder_ii.core.config import load_settings

_COMMON_DISABLED_GOVERNANCE_KEYS = (
    "model_execution",
    "agent_construction",
    "shell_execution",
    "command_execution",
    "source_writes",
    "memory_mutation",
)

_COMMON_DENIED_ACTIONS = (
    "execute_commands",
    "execute_shell",
    "write_source_files",
    "apply_patches",
    "mutate_memory",
    "call_models",
)

_DEEPAGENTS_CONSTRUCTION_DENIALS = {"construct_deepagents", "construct_deepagents_agent"}
_RUNTIME_START_DENIALS = {"start_goose_runtime", "start_deepagents_runtime"}


def _artifacts(tmp_path: Path) -> dict[str, dict[str, Any]]:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    settings = load_settings()
    manifest = create_goose_session_manifest(
        settings,
        target_name="generic",
        agent_profile="patch_planner",
        task="cross-artifact governance invariant check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    readonly_audit = create_readonly_runtime_audit(manifest, manifest_path=tmp_path / "goose-session.json")
    inspection_audit, inspection_errors = create_readonly_inspection_audit(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        read_paths=["README.md"],
    )
    assert inspection_errors == []
    assert inspection_audit is not None

    return {
        "goose_session": manifest,
        "goose_readonly_audit": readonly_audit,
        "goose_inspection_audit": inspection_audit,
        "deepagents_policy": create_deepagents_policy_artifact(
            settings,
            target_name="generic",
            task="cross-artifact governance invariant check",
            generic_repo=tmp_path,
        ),
        "deepagents_readiness": create_deepagents_readiness_artifact(),
    }


def test_artifacts_are_not_authority_and_have_no_core_workbench_coupling(tmp_path: Path) -> None:
    for name, artifact in _artifacts(tmp_path).items():
        governance = artifact["governance"]

        assert governance["artifact_is_authority"] is False, name
        assert governance["core_workbench_coupling"] == "NONE", name


def test_common_runtime_authority_remains_disabled_across_artifacts(tmp_path: Path) -> None:
    for name, artifact in _artifacts(tmp_path).items():
        governance = artifact["governance"]

        for key in _COMMON_DISABLED_GOVERNANCE_KEYS:
            assert governance[key] == "DISABLED", f"{name}: governance.{key}"


def test_runtime_execution_labels_do_not_start_runtimes(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)

    assert artifacts["goose_session"]["governance"]["runtime_execution"] == "DISABLED"
    assert artifacts["goose_readonly_audit"]["governance"]["runtime_execution"] == "DISABLED"
    assert artifacts["deepagents_policy"]["governance"]["runtime_execution"] == "DISABLED"
    assert artifacts["deepagents_readiness"]["governance"]["runtime_execution"] == "DISABLED"

    inspection = artifacts["goose_inspection_audit"]
    assert inspection["governance"]["runtime_execution"] == "READ_ONLY_CANDIDATE_INSPECTION"
    assert inspection["runtime_started"] is False
    assert inspection["goose_process_started"] is False


def test_denied_authority_families_are_aligned_across_artifacts(tmp_path: Path) -> None:
    for name, artifact in _artifacts(tmp_path).items():
        denied = set(artifact["denied_actions"])

        for action in _COMMON_DENIED_ACTIONS:
            assert action in denied, f"{name}: missing {action}"
        assert denied & _DEEPAGENTS_CONSTRUCTION_DENIALS, f"{name}: missing deepagents construction denial"
        assert denied & _RUNTIME_START_DENIALS, f"{name}: missing runtime start denial"


def test_deepagents_policy_and_readiness_factory_contract_agree(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    policy_factory = artifacts["deepagents_policy"]["governed_factory"]
    readiness_package = artifacts["deepagents_readiness"]["package"]

    assert policy_factory["package"] == readiness_package["name"] == "deepagents"
    assert readiness_package["module"] == "deepagents"
    assert policy_factory["factory"] == readiness_package["expected_factory"] == "create_deep_agent"
    assert "create_deep_agent" in readiness_package["expected_exports"]


def test_only_bounded_inspection_records_repository_read_metadata(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)

    assert "read_repository_files_as_runtime" in artifacts["goose_session"]["denied_actions"]
    assert artifacts["goose_readonly_audit"]["repository_files_read"] == []
    assert (
        artifacts["goose_readonly_audit"]["governance"]["repository_file_reads"]
        == "DISABLED_IN_THIS_CANDIDATE_ARTIFACT"
    )
    assert "read_repository_files_as_runtime" in artifacts["deepagents_policy"]["denied_actions"]
    assert "read_repository_files_as_runtime" in artifacts["deepagents_readiness"]["denied_actions"]

    inspection = artifacts["goose_inspection_audit"]
    assert inspection["governance"]["repository_file_reads"] == "ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY"
    assert inspection["repository_file_contents_recorded"] is False
    assert inspection["repository_files_read"] == [
        {
            "path": "README.md",
            "bytes_read": 6,
            "sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
            "line_count": 1,
            "content_recorded": False,
        }
    ]


def test_no_artifact_records_repository_file_contents(tmp_path: Path) -> None:
    for name, artifact in _artifacts(tmp_path).items():
        assert artifact.get("repository_file_contents_recorded", False) is False, name
        for entry in artifact.get("repository_files_read", []):
            assert entry["content_recorded"] is False, name
            assert "content" not in entry, name
