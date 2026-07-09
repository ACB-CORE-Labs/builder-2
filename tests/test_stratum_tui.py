from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.tui.app import CHAIN_DIGEST_ABSENT, StratumApp
from builder_ii.tui.widgets.stratum import StratumMode

_TUI_DIR = Path(__file__).resolve().parents[1] / "builder_ii" / "tui"


def test_no_chain_digest_is_reachable_so_none_may_be_displayed() -> None:
    """STRATUM shows an absence marker because there is genuinely nothing to bind.

    If `verify_artifact_chain` ever grows a digest, this fails -- and it should: at that moment
    the TUI must bind the real digest, and `builder stratum`'s runtime_boundary must stop saying
    that none is available. The test fails in the direction that forces truth to be restored.
    """
    report = verify_artifact_chain([])
    digest_keys = [key for key in report if "digest" in key.lower()]
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
