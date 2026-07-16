import os
from unittest import mock

import pytest

from builder_ii.tui.app import HeaderBanner, StratumApp
from builder_ii.tui_theme import (
    active_theme_name,
    theme_extras,
    theme_palette,
    theme_panel_border,
)


def test_default_theme_palette_matches_stratum_css_defaults():
    # Set default theme explicitly
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "default"}):
        p = theme_palette()
        assert p["pass"] == "#3fb950"
        assert p["warn"] == "#ffa657"
        assert p["fail"] == "#f85149"
        assert p["hint"] == "#6e7681"
        assert p["active"] == "#79c0ff"
        assert p["dim"] == "#21262d"
        assert p["bold"] == "#c9d1d9"
        assert p["accent"] == "#d2a8ff"


def test_active_theme_name_chargers():
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        assert active_theme_name() == "chargers"
        p = theme_palette()
        assert p["active"] == "#FFFFFF"
        assert p["warn"] == "#FFC20E"


def test_chargers_theme_extras_match_tui_surface_contract():
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        e = theme_extras()
        assert e["_bg"] == "#0080C6"
        assert e["_panel"] == "#002244"
        assert e["_panel_light"] == "#003366"
        assert e["_border"] == "#0080C6"
        assert e["_selected"] == "#0080C6"
        assert e["_hover"] == "#004080"
        assert theme_panel_border() == "#0080C6"


def test_header_banner_colors():
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        banner = HeaderBanner()
        banner.target = "tgt"
        banner.model = "mdl"
        banner.tier = "tr"
        banner.session = "sess"
        res = banner.render()
        assert "#FFFFFF" in res
        assert "#FFC20E" in res


@pytest.mark.asyncio
@pytest.mark.skip(reason="flaky under xdist load")
async def test_stratum_app_theme_default():
    # test default theme preserves original palette and registers builder_default
    with mock.patch.dict(os.environ, clear=True):
        app = StratumApp()
        async with app.run_test():
            assert app.theme == "builder_default"
            # Assert default mode still resolves to existing default palette
            assert app.theme_variables["stratum-bg"] == "#0a0e14"
            assert app.theme_variables["stratum-panel"] == "#0d1117"

            # Assert resolved styles for structural widgets match default values
            center_widget = app.query_one("#stratum-center")
            header_widget = app.query_one("#stratum-header")
            assert center_widget.styles.background.hex.lower() == "#0a0e14"
            assert header_widget.styles.background.hex.lower() == "#0d1117"

            # Assert theme_variables and actual resolved widget style agree
            assert app.theme_variables["stratum-bg"].lower() == center_widget.styles.background.hex.lower()
            assert app.theme_variables["stratum-panel"].lower() == header_widget.styles.background.hex.lower()


@pytest.mark.asyncio
async def test_stratum_app_theme_invalid():
    # test invalid BUILDER_THEME falls back safely to builder_default
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "invalid_theme_name"}):
        app_invalid = StratumApp()
        async with app_invalid.run_test():
            assert app_invalid.theme == "builder_default"
            assert "builder_custom" not in app_invalid.available_themes


@pytest.mark.asyncio
async def test_stratum_app_theme_chargers():
    # test Chargers registers and drives theme variables
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        app_chargers = StratumApp()
        async with app_chargers.run_test():
            assert app_chargers.theme == "builder_custom"
            assert "builder_custom" in app_chargers.available_themes
            t = app_chargers.get_theme("builder_custom")
            assert t.variables["stratum-pass"] == "#FFC20E"
            assert t.variables["stratum-border"] == "#0080C6"

            # Assert the theme_variables contains custom colors
            assert app_chargers.theme_variables["stratum-bg"] == "#0080C6"
            assert app_chargers.theme_variables["stratum-panel"] == "#002244"
            assert app_chargers.theme_variables["stratum-border"] == "#0080C6"

            # Assert resolved style for structural widgets uses Chargers values
            center_widget = app_chargers.query_one("#stratum-center")
            header_widget = app_chargers.query_one("#stratum-header")
            assert center_widget.styles.background.hex.lower() == "#0080c6"
            assert header_widget.styles.background.hex.lower() == "#002244"

            # Assert theme_variables and actual resolved widget style agree
            assert app_chargers.theme_variables["stratum-bg"].lower() == center_widget.styles.background.hex.lower()
            assert app_chargers.theme_variables["stratum-panel"].lower() == header_widget.styles.background.hex.lower()

