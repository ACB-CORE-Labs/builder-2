import json
import pathlib
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.tui.app import CHAIN_DIGEST_ABSENT, StratumApp
from builder_ii.tui.widgets.stratum import StratumMode

_TUI_DIR = Path(__file__).resolve().parents[1] / "builder_ii" / "tui"


def test_no_chain_digest_is_reachable_so_none_may_be_displayed(tmp_path: Path) -> None:
    """STRATUM shows an absence marker because there is genuinely nothing to bind.

    If `verify_artifact_chain` ever grows a digest, this fails -- and it should: at that moment
    the TUI must bind the real digest, and `builder stratum`'s runtime_boundary must stop saying
    that none is available. The test fails in the direction that forces truth to be restored.

    The cross-author audit proved the first cut of this pin weaker than that promise: it scanned
    only the TOP-LEVEL keys of an EMPTY-input report, so a digest surfacing inside a nested
    structure (a per-file entry, say), or only on a non-empty chain, left it green. The scan is
    now recursive and also runs against a real chain containing a digest-bound artifact -- whose
    own embedded digest fields must NOT leak into the report.
    """
    from builder_ii.gate_battery_receipt import (
        build_gate_battery_receipt,
        dumps_gate_battery_receipt,
        gate_record_for_run,
    )

    receipt = build_gate_battery_receipt(
        gates=[gate_record_for_run("gate", ["true"], 0, 1)],
        head_sha_before="a" * 40,
        head_sha_after="a" * 40,
        working_tree_clean=True,
    )
    digest_bound = tmp_path / "receipt.json"
    digest_bound.write_text(dumps_gate_battery_receipt(receipt), encoding="utf-8")
    unknown = tmp_path / "unknown.json"
    unknown.write_text('{"kind": "unknown.kind"}', encoding="utf-8")

    def digest_keys_at_any_level(value: object, location: str = "$") -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str) and "digest" in key.lower():
                    found.append(f"{location}.{key}")
                found.extend(digest_keys_at_any_level(item, f"{location}.{key}"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found.extend(digest_keys_at_any_level(item, f"{location}[{index}]"))
        return found

    for paths in ([], [digest_bound, unknown]):
        report = verify_artifact_chain(paths)
        digest_keys = digest_keys_at_any_level(report)
        assert not digest_keys, (
            f"verify_artifact_chain now exposes {digest_keys}: STRATUM must render the real digest, "
            "and the `builder stratum` runtime_boundary must stop claiming none is reachable"
        )


def test_tui_never_synthesizes_anything_shaped_like_a_digest() -> None:
    """A digest-shaped literal may not exist anywhere under `builder_ii/tui/`, not even in a comment.

    A previous revision rendered the artifact count and the validity flag into a digest-shaped
    string and labelled it the chain digest. Absence is displayed as absence; the string cannot
    creep back, so it is barred outright.
    """
    for source in _TUI_DIR.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "SHA256:" not in text, f"{source.name} contains a digest-shaped literal"
        assert "fake" not in text.lower(), f"{source.name} still contains a fake"


@pytest.mark.asyncio
async def test_stratum_chain_digest_absence(tmp_path):
    # We must patch load_settings since StratumApp.__init__ calls it
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        app.artifacts_dir = tmp_path

        async with app.run_test():
            # Create a dummy file to ensure _verify_current_chain_async evaluates
            (tmp_path / "test.json").touch()
            with patch("builder_ii.tui.app.verify_artifact_chain") as mock_verify:
                mock_verify.return_value = {"valid": False, "counts": {"files": 0}}
                await app._verify_current_chain_async()

                assert app.stratum is not None
                assert app.stratum._chain_digest == CHAIN_DIGEST_ABSENT
                assert app.stratum._authority_granted is None


@pytest.mark.asyncio
async def test_stratum_palette_authority():
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        async with app.run_test() as pilot:
            with patch("builder_ii.tui.app.COMMAND_AUTHORITY_REGISTRY") as mock_registry, patch("builder_ii.tui.app.check_command_authority") as mock_check:
                from unittest.mock import MagicMock
                mock_record = MagicMock()
                mock_record.name = "test"
                mock_record.tier = "TIER_0"
                mock_record.promotion_state = "VERIFIED"
                mock_registry.__iter__.return_value = [mock_record]
                mock_check_decision = MagicMock()
                mock_check_decision.allowed = False
                mock_check_decision.reasons = ["mock reason"]
                mock_check.return_value = mock_check_decision

                app.action_open_palette()
                await pilot.pause()

                screen = app.screen
                assert screen.__class__.__name__ == "CommandPaletteScreen"
                assert hasattr(screen, "_commands")
                assert len(screen._commands) > 0
                cmd = screen._commands[0]
                assert cmd["allowed"] is False
                assert cmd["reason"] == "mock reason"


@pytest.mark.asyncio
async def test_stratum_hitl_informative_refusal():
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        async with app.run_test():
            app.stratum.mode = StratumMode.HITL_GATE
            with patch.object(app, "notify") as mock_notify, patch.object(app, "push_screen") as mock_push:
                app.action_approve_hitl()
                approve_msg = mock_notify.call_args[0][0]
                assert "cannot harvest confirmation" in approve_msg
                assert "builder-hitl approve-patch" in approve_msg
                assert mock_notify.call_args.kwargs.get("severity") == "warning"
                mock_push.assert_called()

                app.action_reject_hitl()
                reject_msg = mock_notify.call_args[0][0]
                assert "cannot mutate approval state" in reject_msg
                assert "builder-hitl rejection-record" in reject_msg
                assert mock_notify.call_args.kwargs.get("severity") == "warning"


# --- STRATUM originates neither writes nor runtimes ---------------------------------------------
#
# `builder stratum` is TIER_2, operator-managed, and its record declares no write authority. Two
# keybindings contradicted that. `p` wrote `session_config.json` into the artifact root under
# `kind: "builder_ii.session_config"` -- a kind registered nowhere, read by nothing. `g` called
# `goose_launcher.launch_goose_session`, which spawns `goose session --with-builtin
# developer,skills,summon`: file editing and shell, with no read-only policy, no launch receipt and
# no approval. The governed command for that runtime, `builder-goose start-readonly`, is TIER_3 and
# "requires implicit or explicit HITL approval for launch." A keypress in a render surface must not
# launder a higher tier's approval boundary.


def test_tui_sources_never_write_a_file() -> None:
    for source in _TUI_DIR.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert ".write_text(" not in text, f"{source.name} writes a file; STRATUM has no write authority"
        assert ".write_bytes(" not in text, f"{source.name} writes a file; STRATUM has no write authority"


def test_tui_sources_never_start_a_goose_runtime() -> None:
    for source in _TUI_DIR.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
        assert "launch_goose_session(" not in code, (
            f"{source.name} starts a Goose runtime; that is `builder-goose start-readonly`'s "
            "TIER_3 boundary, not a TIER_2 render surface's keypress"
        )


@pytest.mark.asyncio
async def test_prepare_package_refuses_to_write_and_names_the_governed_cli(tmp_path) -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        app.artifacts_dir = tmp_path
        async with app.run_test():
            captured: dict = {}

            def fake_push_screen(screen, callback=None):
                captured["callback"] = callback

            with patch.object(app, "push_screen", fake_push_screen), patch.object(app, "notify") as notify:
                app.action_prepare_package()
                captured["callback"]({"kind": "builder_ii.session_config", "corpus_name": "x"})

            assert list(tmp_path.iterdir()) == [], "STRATUM wrote an artifact"
            message = notify.call_args[0][0]
            assert "does not write artifacts" in message
            assert "builder-session prepare-package" in message


def test_tui_never_reaches_for_the_raw_goose_adapter_or_chooses_builtins() -> None:
    """STRATUM invokes builder-II's governed CLI. It does not locate, configure, or spawn Goose.

    Scoped to what actually matters: the raw adapter module, the binary finder, and any choice of
    Goose builtins. (`"goose"` alone is a false positive -- `.builder/goose` is where the governed
    manifest lives, and a pin that fires on a directory name is a pin nobody will keep.)
    """
    forbidden_symbols = ("launch_goose_session", "find_goose_binary", "derive_goose_environment")
    for source in _TUI_DIR.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
        for symbol in forbidden_symbols:
            assert f"{symbol}(" not in code, f"{source.name} calls {symbol}; that is the ungoverned path"
        for literal in _rendered_string_literals(source):
            assert "--with-builtin" not in literal, f"{source.name} chooses Goose builtins itself"


@pytest.mark.asyncio
async def test_launch_goose_fails_closed_when_the_registry_forbids_the_governed_command() -> None:
    from builder_ii.command_authority import CommandAuthorityError

    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        app = StratumApp()
        async with app.run_test():
            with (
                patch("builder_ii.command_authority.enforce_command_authority", side_effect=CommandAuthorityError("nope")),
                patch("subprocess.run") as run,
                patch.object(app, "notify") as notify,
            ):
                app.action_launch_goose()

            run.assert_not_called()
            assert "not permitted" in notify.call_args[0][0]


@pytest.mark.asyncio
async def test_launch_goose_refuses_without_a_readonly_manifest_and_never_spawns(tmp_path) -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        app = StratumApp()
        app.artifacts_dir = tmp_path / "artifacts"
        async with app.run_test():
            with patch("subprocess.run") as run, patch.object(app, "notify") as notify:
                app.action_launch_goose()

            run.assert_not_called()
            message = notify.call_args[0][0]
            assert "No read-only Goose session manifest found" in message
            assert "builder-goose manifest --mode read_only" in message
            assert "STRATUM does not mint manifests" in message


def test_manifest_discovery_rejects_a_manifest_that_does_not_request_read_only(tmp_path) -> None:
    """A valid manifest asking for `disabled` mode is not a licence to start a runtime."""
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        app = StratumApp()
        app.artifacts_dir = tmp_path / ".builder" / "artifacts"
        goose_dir = tmp_path / ".builder" / "goose"
        goose_dir.mkdir(parents=True)
        (goose_dir / "session.json").write_text(json.dumps({"requested_runtime_mode": "disabled"}), encoding="utf-8")

        with patch("builder_ii.goose_session.validate_goose_session_manifest_file", return_value=[]):
            assert app._governed_readonly_manifest() is None


@pytest.mark.asyncio
async def test_launch_goose_reports_only_the_outcome_the_command_recorded() -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        app = StratumApp()
        async with app.run_test():
            with patch.object(app, "notify") as notify:
                app._render_goose_session_outcome(1)
            message, kwargs = notify.call_args[0][0], notify.call_args.kwargs
            assert "exited 1" in message
            assert kwargs.get("severity") == "error"
            assert "completed" not in message, "a failed session must not be reported as success"


# --- STRATUM claims no action it does not perform ------------------------------------------------
#
# `?` said "Executing: <cmd>" beside a comment reading "Real implementation would trigger the command
# logic here". `~` and `n` said "Raw CLI Exec: builder <cmd>" and appended a `cli_passthrough` event
# to the signal rail -- writing a record of an execution that never occurred into the very panel that
# shows the operator what happened. Fabricated success, twice, in the surface whose whole purpose is
# to report truthfully what the system did.


def _rendered_string_literals(source: pathlib.Path) -> list[str]:
    """Every string literal in the file that is not a docstring.

    Comments and docstrings *describe* the defect and must stay; only what the surface can actually
    render to the operator is in scope. Grepping the raw text conflates the two -- it fired on the
    very comments recording why these phrases are forbidden.
    """
    import ast

    tree = ast.parse(source.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    return [
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docstrings
    ]


def test_tui_renders_no_claim_of_an_execution() -> None:
    """STRATUM runs no command, so no string it can render may say it did."""
    banned = ("Executing:", "Raw CLI Exec", "Exec: builder")
    for source in _TUI_DIR.rglob("*.py"):
        for literal in _rendered_string_literals(source):
            for phrase in banned:
                assert phrase not in literal, f"{source.name} renders an execution claim: {phrase!r}"


def test_tui_never_records_a_command_execution_in_the_signal_rail() -> None:
    """The rail reports what happened. STRATUM executes nothing, so it logs no execution."""
    for source in _TUI_DIR.rglob("*.py"):
        if source.name == "signals.py":
            continue  # defines append_event; the callers must be honest, not the rail
        for literal in _rendered_string_literals(source):
            assert literal != "cli_passthrough", (
                f"{source.name} writes a cli_passthrough event; STRATUM executes no command, so it "
                "must not record one as having run"
            )


@pytest.mark.asyncio
async def test_cli_passthrough_composes_and_says_it_ran_nothing() -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        async with app.run_test():
            app.signals = None
            with patch.object(app, "notify") as notify:
                app._show_composed_command("verify plan")

            message = notify.call_args[0][0]
            assert "Composed: builder verify plan" in message
            assert "STRATUM executes nothing" in message
            for lie in ("Exec", "Executing"):
                assert lie not in message
