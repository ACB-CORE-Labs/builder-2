import os
from unittest import mock
import pytest
from textual.app import App
from builder_ii.tui_theme import active_theme_name, theme_palette
from builder_ii.tui.app import HeaderBanner, StratumApp

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

def test_stratum_app_theme():
    import asyncio
    
    # test default
    with mock.patch.dict(os.environ, clear=True):
        app = StratumApp()
        assert app.theme == "textual-dark"
    
    # test chargers
    with mock.patch.dict(os.environ, {"BUILDER_THEME": "chargers"}):
        app = StratumApp()
        async def run_it():
            async with app.run_test():
                assert app.theme == "builder_custom"
                assert "builder_custom" in app.available_themes
                t = app.get_theme("builder_custom")
                assert t.variables["stratum-pass"] == "#0073CF"
                assert t.variables["stratum-panel"] == "#002244"
        asyncio.run(run_it())

