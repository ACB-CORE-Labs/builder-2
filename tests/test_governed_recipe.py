"""G2 — recipe interposition + governed launch.

Proves the Goose->builder-II interposition without spawning Goose: the recipe declares the
governed MCP server as Goose's only tool surface, and ``launch_governed`` builds an argv that
strips builtins and points Goose at that recipe. A real Goose launch loading the extension is
a local verify-by-experiment step, not a CI dependency (Goose need not be installed in CI).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from builder_ii.adapters.goose.goose_compatibility import validate_governed_recipe
from builder_ii.adapters.goose.goose_receipts import validate_goose_launch_receipt
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.core.config import Settings
from builder_ii.governance.ledger.event_ledger import load_event_records, validate_event_chain_integrity

_RECIPE_PATH = Path(__file__).resolve().parents[1] / "recipes" / "governed-readonly.yaml"


class _MockSessionPlan:
    def __init__(self) -> None:
        self.target_name = "builder"
        self.agent_profile = "patch_planner"
        self.recipe_name = "governed-readonly.yaml"
        self.model_tier = "3"
        self.mode = "read_only"


@pytest.fixture
def mock_settings(tmp_path: Path) -> MagicMock:
    m = MagicMock(spec=Settings)
    m.project_root = tmp_path
    m.target_repo = tmp_path
    m.backend = "openai"
    m.temperature = 0.0
    return m


def test_governed_recipe_declares_only_the_governed_mcp_server() -> None:
    recipe = yaml.safe_load(_RECIPE_PATH.read_text(encoding="utf-8"))
    extensions = recipe["extensions"]
    assert len(extensions) == 1
    ext = extensions[0]
    assert ext["type"] == "stdio"
    assert ext["cmd"] == "builder-mcp"
    assert ext["args"] == ["serve"]
    # No developer/shell builtins anywhere: the only tools are the governed MCP stubs.
    assert all(e.get("name") != "developer" for e in extensions)
    assert all(e.get("type") != "builtin" for e in extensions)
    assert recipe["settings"]["goose_mode"] == "auto"


def test_real_canonical_recipe_passes_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.adapters.goose.goose_compatibility.shutil.which", lambda name: "/mock/builder-mcp")
    digest = validate_governed_recipe(_RECIPE_PATH)
    assert len(digest) == 64


def test_governed_argv_disables_builtins_and_adds_recipe(mock_settings, tmp_path: Path) -> None:
    recipe = tmp_path / "governed-readonly.yaml"
    recipe.write_text("version: '1.0.0'\n", encoding="utf-8")
    argv = GooseRuntimeHarness(mock_settings, _MockSessionPlan(), tmp_path)._governed_argv("/mock/bin/goose", recipe)
    assert argv[:4] == ["/mock/bin/goose", "session", "--with-builtin", ""]
    assert "--recipe" in argv
    assert str(recipe) in argv


def test_governed_argv_omits_recipe_when_missing(mock_settings, tmp_path: Path) -> None:
    argv = GooseRuntimeHarness(mock_settings, _MockSessionPlan(), tmp_path)._governed_argv("/mock/bin/goose", tmp_path / "nope.yaml")
    assert "--recipe" not in argv


@patch(
    "builder_ii.adapters.goose.goose_launcher.derive_goose_environment",
    return_value=({}, {"real_provider_credentials_exposed": False, "route_bound": True}),
)
@patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary")
@patch("builder_ii.adapters.goose.goose_runtime_harness.probe_goose")
@patch("builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe")
@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen")
def test_launch_governed_points_goose_at_the_governed_recipe(
    mock_popen: MagicMock,
    mock_validate_recipe: MagicMock,
    mock_probe: MagicMock,
    mock_find_goose: MagicMock,
    mock_goose_env: MagicMock,
    mock_settings: MagicMock,
    tmp_path: Path,
    goose_gateway_context_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_find_goose.return_value = "/mock/bin/goose"
    mock_probe.return_value = MagicMock(binary="/mock/bin/goose", version="1.46.0", policy=">=1.45.0,<1.47.0")
    mock_validate_recipe.return_value = "a" * 64
    proc = MagicMock()
    proc.pid = 999
    proc.poll.return_value = 0
    proc.returncode = 0
    mock_popen.return_value = proc

    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "governed-readonly.yaml").write_text("version: '1.0.0'\n", encoding="utf-8")

    harness = GooseRuntimeHarness(
        mock_settings,
        _MockSessionPlan(),
        tmp_path,
        model_gateway_context=goose_gateway_context_factory(mock_settings, tmp_path / "model-calls", "recipe-test"),
    )
    receipt = harness.launch_governed()
    assert receipt["kind"] == "builder_ii.goose_launch_receipt"
    assert receipt["schema_version"] == 2
    assert receipt["pid"] == 999
    assert receipt["evidence"]["goose_compatibility"] == {
        "binary": "/mock/bin/goose",
        "version": "1.46.0",
        "policy": ">=1.45.0,<1.47.0",
    }
    assert receipt["evidence"]["recipe_sha256"] == "a" * 64
    assert receipt["evidence"]["route_digest"] == harness._model_gateway_context.route.route_digest
    assert receipt["evidence"]["model_gateway"]["real_provider_credentials_exposed"] is False
    assert validate_goose_launch_receipt(receipt) == []

    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    argv = args[0]
    assert argv[:4] == ["/mock/bin/goose", "session", "--with-builtin", ""]
    assert "--recipe" in argv
    assert str(tmp_path / "recipes" / "governed-readonly.yaml") in argv
    # The MCP server's ledger is scoped to this run; no shell mode enabled.
    assert kwargs["env"]["BUILDER_MCP_SESSION_ID"] == harness.session_id
    assert kwargs["env"]["GOOSE_MODE"] == "auto"
    artifact_root = harness._admitted_artifact_root
    assert artifact_root is not None
    session_root = artifact_root / "sessions" / harness.session_id
    assert (session_root / "goose" / "launch.json").is_file()

    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.subprocess.run",
        lambda *_args, **_kwargs: MagicMock(returncode=9),
    )
    with pytest.raises(RuntimeError, match="transcript export failed"):
        harness.close(receipt["digest"])
    assert not (session_root / "goose" / "transcript.json").exists()
    assert not (session_root / "goose" / "close.json").exists()
    assert [event[0]["event_type"] for event in load_event_records(session_root / "events")] == [
        "goose_session_started"
    ]

    def export_transcript(argv, **_kwargs):
        output = Path(argv[argv.index("--output") + 1])
        output.write_text('{"messages": []}\n', encoding="utf-8")
        return MagicMock(returncode=0)

    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.run", export_transcript)
    close, postflight = harness.close(receipt["digest"])
    assert close["postflight_digest"] == postflight["digest"]
    assert (session_root / "goose" / "postflight.json").is_file()
    assert (session_root / "goose" / "close.json").is_file()
    events = load_event_records(session_root / "events")
    assert [event[0]["event_type"] for event in events] == [
        "goose_session_started",
        "goose_session_closed",
    ]
    assert validate_event_chain_integrity(session_root / "events")["valid"] is True


@patch("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen")
def test_launch_governed_refuses_recipe_drift_at_spawn_boundary(
    mock_popen: MagicMock, mock_settings: MagicMock, tmp_path: Path, goose_gateway_context_factory
) -> None:
    recipe = tmp_path / "recipes" / "governed-readonly.yaml"
    recipe.parent.mkdir()
    recipe.write_text("version: '1.0.0'\n", encoding="utf-8")
    harness = GooseRuntimeHarness(
        mock_settings,
        _MockSessionPlan(),
        tmp_path,
        model_gateway_context=goose_gateway_context_factory(mock_settings, tmp_path / "model-calls", "drift-test"),
    )
    with patch("builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary", return_value="/mock/bin/goose"), patch(
        "builder_ii.adapters.goose.goose_runtime_harness.probe_goose",
        return_value=MagicMock(binary="/mock/bin/goose", version="1.46.0", policy=">=1.45.0,<1.47.0"),
    ), patch(
        "builder_ii.adapters.goose.goose_launcher.derive_goose_environment",
        return_value=({}, {"real_provider_credentials_exposed": False, "route_bound": True}),
    ), patch(
        "builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe", side_effect=["a" * 64, "b" * 64]
    ):
        with pytest.raises(ValueError, match="changed after admission"):
            harness.launch_governed()
    mock_popen.assert_not_called()
