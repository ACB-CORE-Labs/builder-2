import os
from unittest import mock
import pytest
from builder_ii.tui_theme import active_theme_name, theme_palette, list_themes
from builder_ii.tui.app import HeaderBanner, StratumApp

def test_default_theme_palette_matches_stratum_css_defaults():
    # Set default theme explicitly
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "default"}):
        p = theme_palette()
        assert p["pass"] == "#3fb950"
        assert p["warn"] == "#d29922"
        assert p["fail"] == "#f85149"
        assert p["hint"] == "#8b949e"
        assert p["active"] == "#58a6ff"
        assert p["dim"] == "#484f58"
        assert p["bold"] == "#c9d1d9"
        assert p["accent"] == "#d2a8ff"

def test_active_theme_name_chargers():
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        assert active_theme_name() == "chargers"
        p = theme_palette()
        assert p["active"] == "#0073CF"
        assert p["warn"] == "#FFB612"

def test_header_banner_colors():
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        banner = HeaderBanner()
        banner.target = "tgt"
        banner.model = "mdl"
        banner.tier = "tr"
        banner.session = "sess"
        res = banner.render()
        assert "#0073CF" in res
        assert "#FFB612" in res

@pytest.mark.asyncio
async def test_stratum_app_theme():
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

    # test invalid BUILDER_THEME falls back safely to builder_default
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "invalid_theme_name"}):
        app_invalid = StratumApp()
        async with app_invalid.run_test():
            assert app_invalid.theme == "builder_default"
            assert "builder_custom" not in app_invalid.available_themes

    # test Chargers registers and drives theme variables
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        app_chargers = StratumApp()
        async with app_chargers.run_test():
            assert app_chargers.theme == "builder_custom"
            assert "builder_custom" in app_chargers.available_themes
            t = app_chargers.get_theme("builder_custom")
            assert t.variables["stratum-pass"] == "#0073CF"
            assert t.variables["stratum-border"] == "#6C757D"

            # Assert the theme_variables contains custom colors
            assert app_chargers.theme_variables["stratum-bg"] == "#002244"
            assert app_chargers.theme_variables["stratum-panel"] == "#002244"
            assert app_chargers.theme_variables["stratum-border"] == "#6C757D"

            # Assert resolved style for structural widgets uses Chargers values
            center_widget = app_chargers.query_one("#stratum-center")
            header_widget = app_chargers.query_one("#stratum-header")
            assert center_widget.styles.background.hex.lower() == "#002244"
            assert header_widget.styles.background.hex.lower() == "#002244"

            # Assert theme_variables and actual resolved widget style agree
            assert app_chargers.theme_variables["stratum-bg"].lower() == center_widget.styles.background.hex.lower()
            assert app_chargers.theme_variables["stratum-panel"].lower() == header_widget.styles.background.hex.lower()
