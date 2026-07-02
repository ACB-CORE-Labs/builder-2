import os
from unittest import mock
import pytest
from builder_ii.tui_theme import active_theme_name, theme_palette, list_themes
from builder_ii.tui.app import HeaderBanner, StratumApp

def test_default_theme_palette_matches_stratum_css_defaults():
    # 1. default theme palette matches STRATUM CSS defaults
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
        # 5. HeaderBanner includes Chargers powder blue and bolt gold
        assert "#0073CF" in res
        assert "#FFB612" in res

@pytest.mark.asyncio
async def test_stratum_app_theme():
    # test default
    with mock.patch.dict(os.environ, clear=True):
        app = StratumApp()
        assert app.theme == "textual-dark"
    
    # 2. invalid BUILDER_THEME falls back without registering builder_custom
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "invalid_theme_name"}):
        app_invalid = StratumApp()
        assert app_invalid.theme == "textual-dark"
        assert "builder_custom" not in app_invalid.available_themes

    # 3. Chargers registers builder_custom
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        app_chargers = StratumApp()
        async with app_chargers.run_test():
            assert app_chargers.theme == "builder_custom"
            assert "builder_custom" in app_chargers.available_themes
            t = app_chargers.get_theme("builder_custom")
            assert t.variables["stratum-pass"] == "#0073CF"
            # 4. Chargers stratum-border == #6C757D (which is p["dim"])
            assert t.variables["stratum-border"] == "#6C757D"
