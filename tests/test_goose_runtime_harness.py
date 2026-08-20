import hashlib
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt

from builder_ii.adapters.goose.goose_compatibility import GooseCompatibility
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.adapters.mcp import governed_services as mcp_services
from builder_ii.core.config import Settings
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal


class MockSessionPlan:
    def __init__(self):
        self.target_name = "builder"
        self.agent_profile = "patch_planner"
        self.recipe_name = "core-platform.yaml"
        self.model_tier = "3"
        self.mode = "read_only"


@pytest.fixture
def mock_settings(tmp_path: Path) -> MagicMock:
    m = MagicMock(spec=Settings)
    m.project_root = tmp_path
    m.target_repo = tmp_path
    m.backend = "openai"
    m.api_key = "mock"
    m.base_url = "https://mock.com"
    m.model_primary = "gpt-4o"
    m.temperature = 0.0
    return m


@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run")
@patch("builder_ii.adapters.goose.goose_runtime_harness.goose_env", return_value={})
@patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary")
@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen")
def test_goose_launch_enforces_read_only_env(
    mock_popen: MagicMock,
    mock_find_goose: MagicMock,
    mock_goose_env: MagicMock,
    mock_subprocess_run: MagicMock,
    mock_settings: MagicMock,
    tmp_path: Path,
) -> None:
    mock_find_goose.return_value = "/mock/bin/goose"
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.__enter__.return_value = mock_proc
    mock_proc.poll.return_value = 0
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.__enter__.return_value = mock_proc
    mock_proc.__exit__.return_value = None
    mock_popen.return_value = mock_proc

    plan = MockSessionPlan()
    harness = GooseRuntimeHarness(mock_settings, plan, tmp_path)

    # Touch a file to simulate repo content
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    launch_receipt = harness.launch_readonly()
    assert launch_receipt["kind"] == "builder_ii.goose_launch_receipt"
    assert launch_receipt["pid"] == 12345

    # Verify environment restrictions and args
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0][:4] == ["/mock/bin/goose", "session", "--with-builtin", ""]
    assert kwargs["env"]["GOOSE_MODE"] == "auto"

    close_receipt, postflight = harness.close(launch_receipt["digest"])
    assert close_receipt["kind"] == "builder_ii.goose_close_receipt"
    assert close_receipt["launch_receipt_digest"] == launch_receipt["digest"]
    assert postflight["kind"] == "builder_ii.no_mutation_postflight"
    assert postflight["valid"] is True
    assert postflight["files_checked"] == 1


@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run")
@patch("builder_ii.adapters.goose.goose_runtime_harness.goose_env", return_value={})
@patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary")
@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen")
def test_goose_mutation_detected_fails_postflight(
    mock_popen: MagicMock,
    mock_find_goose: MagicMock,
    mock_goose_env: MagicMock,
    mock_subprocess_run: MagicMock,
    mock_settings: MagicMock,
    tmp_path: Path,
) -> None:
    mock_find_goose.return_value = "/mock/bin/goose"
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.__enter__.return_value = mock_proc
    mock_proc.poll.return_value = 0
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.__enter__.return_value = mock_proc
    mock_proc.__exit__.return_value = None
    mock_popen.return_value = mock_proc

    plan = MockSessionPlan()
    harness = GooseRuntimeHarness(mock_settings, plan, tmp_path)

    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    launch_receipt = harness.launch_readonly()

    # Simulate a mutation (Goose edited the file)
    (tmp_path / "README.md").write_text("hello world", encoding="utf-8")

    close_receipt, postflight = harness.close(launch_receipt["digest"])
    assert postflight["valid"] is False
    assert len(postflight["mutations_detected"]) == 1


def _approved_goose_patch(tmp_path: Path) -> tuple[GooseRuntimeHarness, dict[str, object], Path]:
    target = init_target_repo(tmp_path)
    builder_root = tmp_path / "builder"
    builder_root.mkdir()
    verification_source = real_verification_receipt(tmp_path, target)
    verification = builder_root / "verification.json"
    shutil.copyfile(verification_source, verification)
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, check=True, capture_output=True, text=True
    ).stdout.strip()
    proposal = create_hitl_patch_proposal(
        generic_repo=target,
        patch_digest=patch_digest,
        unified_diff=PATCH_DIFF,
        target_head_sha=head,
        verification_receipt_file_sha256=hashlib.sha256(verification.read_bytes()).hexdigest(),
    )
    proposal_path = builder_root / "proposal.json"
    write_hitl_patch_proposal(proposal, proposal_path)
    approval_path = builder_root / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )
    service_receipt, _, _ = mcp_services.run_service(
        tool_name="patch_apply",
        arguments={
            "proposal_path": str(proposal_path),
            "approval_path": str(approval_path),
            "verification_receipt_path": str(verification),
        },
        session_id="goose_close_session",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )
    assert service_receipt["status"] == "succeeded"
    settings = MagicMock(spec=Settings)
    settings.project_root = tmp_path
    harness = GooseRuntimeHarness(settings, MockSessionPlan(), target)
    harness.session_plan.target_name = "generic"
    harness.session_id = "goose_close_session"
    harness._admitted_artifact_root = builder_root
    harness._preflight_snapshot = {
        str(target / "file.txt"): hashlib.sha256(b"Line 1\nLine 2\n").hexdigest(),
        str(target / "test_smoke.py"): hashlib.sha256(b"def test_smoke():\n    assert True\n").hexdigest(),
    }
    return harness, service_receipt["result"], target


def test_governed_close_accepts_exact_approved_patch_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness, evidence, _ = _approved_goose_patch(tmp_path)
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run", MagicMock())
    _, postflight = harness.close("launch-digest", approved_patch_evidence=evidence)
    assert postflight["valid"] is True
    assert postflight["mutation_mode"] == "approved_hitl_patch"
    assert postflight["approved_mutations"]
    assert postflight["unexplained_mutations"] == []


def test_governed_close_rejects_unexplained_drift_even_with_approved_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness, evidence, target = _approved_goose_patch(tmp_path)
    (target / "unexplained.txt").write_text("drift\n", encoding="utf-8")
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run", MagicMock())
    _, postflight = harness.close("launch-digest", approved_patch_evidence=evidence)
    assert postflight["valid"] is False
    assert any("unexplained.txt" in item for item in postflight["unexplained_mutations"])


def test_goose_launch_fails_without_goose_binary(mock_settings: Settings, tmp_path: Path) -> None:
    with patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary", return_value=None):
        plan = MockSessionPlan()
        harness = GooseRuntimeHarness(mock_settings, plan, tmp_path)
        with pytest.raises(FileNotFoundError):
            harness.launch_readonly()


@pytest.mark.parametrize("failure", ["missing", "probe", "unsupported", "recipe", "tool", "target", "session"])
def test_governed_admission_failures_never_spawn_goose(
    mock_settings: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    harness = GooseRuntimeHarness(mock_settings, MockSessionPlan(), tmp_path)
    recipe = tmp_path / "recipes" / "governed-readonly.yaml"
    recipe.parent.mkdir()
    recipe.write_text("extensions: []\n", encoding="utf-8")
    popen = MagicMock()
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen", popen)
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary", lambda: "/mock/goose")
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe", lambda _: "a" * 64)
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.probe_goose",
        lambda *_: GooseCompatibility("/mock/goose", "1.46.0", ">=1.45.0,<1.47.0"),
    )
    if failure == "missing":
        monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary", lambda: None)
    elif failure == "probe":
        monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.probe_goose", lambda *_: (_ for _ in ()).throw(RuntimeError("probe failed")))
    elif failure == "unsupported":
        monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.probe_goose", lambda *_: (_ for _ in ()).throw(RuntimeError("unsupported")))
    elif failure == "recipe":
        monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe", lambda _: (_ for _ in ()).throw(ValueError("recipe")))
    elif failure == "tool":
        monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe", lambda _: (_ for _ in ()).throw(FileNotFoundError("builder-mcp")))
    elif failure == "target":
        harness.target_root = tmp_path / "missing-target"
    elif failure == "session":
        harness.session_id = "../unsafe"
    with pytest.raises((FileNotFoundError, RuntimeError, ValueError)):
        harness.admit_governed()
    popen.assert_not_called()
