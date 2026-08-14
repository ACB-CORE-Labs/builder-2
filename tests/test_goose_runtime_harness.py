from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.core.config import Settings


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


def test_goose_launch_fails_without_goose_binary(mock_settings: Settings, tmp_path: Path) -> None:
    with patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary", return_value=None):
        plan = MockSessionPlan()
        harness = GooseRuntimeHarness(mock_settings, plan, tmp_path)
        with pytest.raises(FileNotFoundError):
            harness.launch_readonly()
