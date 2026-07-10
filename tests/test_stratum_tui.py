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
            with patch("builder_ii.tui.app.COMMAND_AUTHORITY_REGISTRY") as mock_registry, patch("builder_ii.command_authority.check_command_authority") as mock_check:
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
            with patch.object(app, "notify") as mock_notify:
                app.action_approve_hitl()
                mock_notify.assert_called_with(
                    "TUI cannot harvest confirmation for a digest it renders; run `builder-hitl approve-patch` in your terminal instead.",
                    severity="warning"
                )

                app.action_reject_hitl()
                mock_notify.assert_called_with(
                    "STRATUM is display-only and cannot mutate approval state; run `builder-hitl rejection-record` in your terminal instead.",
                    severity="warning"
                )


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


@pytest.mark.asyncio
async def test_launch_goose_refuses_and_never_spawns() -> None:
    import builder_ii.goose_launcher as launcher

    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"

        app = StratumApp()
        async with app.run_test():
            with patch.object(launcher, "launch_goose_session") as spawn, patch.object(app, "notify") as notify:
                app.action_launch_goose()
                spawn.assert_not_called()

            message = notify.call_args[0][0]
            assert "cannot start a Goose runtime" in message
            assert "builder-goose start-readonly" in message


def test_tui_sources_never_fabricate_an_artifact_kind() -> None:
    """Every `kind:` literal under `builder_ii/tui/` must be a kind the registry actually knows.

    STRATUM wrote `builder_ii.orchestration_assignment` (the governed kind is
    `..._assignment_plan`) and `builder_ii.session_config` (the governed kind is
    `builder_ii.session_configuration`). Inventing a kind to record a fabricated success under is
    the artifact grammar's exact inverse.
    """
    import re

    from builder_ii.artifact_index_records import _VALIDATORS

    known = set(_VALIDATORS)
    for source in _TUI_DIR.rglob("*.py"):
        for kind in re.findall(r'"(builder_ii\.[a-z_]+)"', source.read_text(encoding="utf-8")):
            assert kind in known, f"{source.name} names unregistered artifact kind {kind!r}"
