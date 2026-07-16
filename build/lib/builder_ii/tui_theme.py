"""tui_theme.py — Theme registry for builder-II TUI.

Usage
-----
    export BUILDER_THEME=chargers   # San Diego Chargers powder-blue scheme
    export BUILDER_THEME=default    # slate/indigo/sky (original)

All themes expose the same 8 semantic token names:

    pass    — affirmative / success
    warn    — caution / needs attention
    fail    — error / blocked
    hint    — secondary / de-emphasised text
    active  — active item / highlight
    dim     — muted / separator
    bold    — primary foreground
    accent  — brand / structural accent

Only add tokens here when a semantic gap genuinely exists.
Do not add purely decorative colours.
"""

from __future__ import annotations

import os
from typing import TypedDict


class Palette(TypedDict):
    """The 8 semantic colour tokens every theme must supply."""

    passX: str  # 'pass' is a reserved keyword; key stored as 'pass' in dict
    warn: str
    fail: str
    hint: str
    active: str
    dim: str
    bold: str
    accent: str


# ---------------------------------------------------------------------------
# Default theme  — Cosmic Void (STRATUM instrument console)
# ---------------------------------------------------------------------------
_DEFAULT: dict[str, str] = {
    "pass": "#3fb950",  # Emerald — verified determinism
    "warn": "#ffa657",  # Amber — gate / needs attention
    "fail": "#f85149",  # Crimson — broken chain / block
    "hint": "#6e7681",  # Slate — de-emphasized context
    "active": "#79c0ff",  # Ice Blue — resonance highlight
    "dim": "#21262d",  # Muted — grid lines, rules
    "bold": "#c9d1d9",  # Frost White — primary text
    "accent": "#d2a8ff",  # Amethyst — deepagents / forge
    # Extended surface tokens (also via theme_extras):
    "_bg": "#0a0e14",
    "_panel": "#0d1117",
    "_panel_light": "#161b22",
    "_border": "#21262d",
    "_selected": "#1f2937",
    "_hover": "#1c2333",
    "_selected_text": "#f0f6fc",
    "_disabled": "#30363d",
}

# ---------------------------------------------------------------------------
# Chargers theme  — San Diego powder-blue
#
# Swatch reference
# ----------------
#   Powder Blue  #0080C6   — app background / selection / border
#   Light Blue   #80CFFF   — secondary text on navy panels
#   Navy         #002244   — panel background / dark base
#   Navy Light   #003366   — lighter navy panel surface
#   Navy Hover   #004080   — hover surface
#   Bolt Gold    #FFC20E   — success glyphs / warnings / accents
#   White        #FFFFFF   — active item / primary foreground
#
# Mapping rationale
# -----------------
#   pass   → Bolt Gold     (verified lightning glyphs read as success)
#   warn   → Bolt Gold     (caution = lightning bolt gold energy)
#   fail   → bright red    (failure stays red; universal danger signal)
#   hint   → Light Blue    (secondary text on navy panels)
#   active → White         (active/highlight foreground contrast)
#   dim    → Powder Blue   (borders, inactive widgets, app field)
#   bold   → White         (primary text on navy background)
#   accent → Bolt Gold     (alerts, key bindings, badges)
#
# Notes
# -----
#   - Extended tokens model the TUI surfaces that do not fit the core 8-token
#     contract: app background, panel background, panel-light, border, selected,
#     and hover.
#   - Navy (#002244) is used for floating panels; Powder Blue (#0080C6) is used
#     for the app field, selected state, and panel borders.
#   - fail is kept at near-standard red (#F85149) because red = danger is a
#     cross-cultural convention we should not override.
# ---------------------------------------------------------------------------
_CHARGERS: dict[str, str] = {
    "pass": "#FFC20E",  # Bolt Gold (success / lightning bolts)
    "warn": "#FFC20E",  # Bolt Gold
    "fail": "#F85149",  # Red
    "hint": "#80CFFF",  # Light Blue (secondary text on navy)
    "active": "#FFFFFF",  # White (active elements)
    "dim": "#0080C6",  # Powder Blue (borders / inactive surfaces)
    "bold": "#FFFFFF",  # White (primary text)
    "accent": "#FFC20E",  # Bolt Gold
    # Extended tokens available via theme_extras() only:
    "_bg": "#0080C6",  # Powder Blue app background
    "_panel": "#002244",  # Navy panels
    "_panel_light": "#003366",  # Lighter navy headers/footers
    "_border": "#0080C6",  # Powder Blue panel border
    "_selected": "#0080C6",  # Powder Blue selection highlight
    "_hover": "#004080",  # Navy hover state
}

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, dict[str, str]] = {
    "default": _DEFAULT,
    "chargers": _CHARGERS,
}


def active_theme_name() -> str:
    """Return the active theme name from BUILDER_THEME env var (default: 'default')."""
    return os.environ.get("BUILDER_THEME", "default").lower().strip()


def theme_palette() -> dict[str, str]:
    """Return the active 8-token palette dict.

    Always returns a dict with keys:
        pass, warn, fail, hint, active, dim, bold, accent
    Falls back to default for unknown theme names.
    """
    name = active_theme_name()
    return dict(_REGISTRY.get(name, _DEFAULT))


def theme_extras() -> dict[str, str]:
    """Return extended theme tokens (e.g. _bg, _panel, _border) for the active theme.
    Returns empty dict for themes with no extras.
    """
    name = active_theme_name()
    palette = _REGISTRY.get(name, _DEFAULT)
    return {k: v for k, v in palette.items() if k.startswith("_")}


def theme_panel_border() -> str:
    """Return the recommended panel border colour for the active theme."""
    extras = theme_extras()
    if "_border" in extras:
        return extras["_border"]
    return theme_palette()["dim"]


def theme_section_rule() -> str:
    """Return the recommended section rule colour for the active theme."""
    return theme_palette()["accent"]


def list_themes() -> list[str]:
    """Return sorted list of available theme names."""
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Rich Console factory
# ---------------------------------------------------------------------------


def make_console(**kwargs):
    """Return a Rich Console instance. Theme is ambient (applied via _C tokens)."""
    try:
        from rich.console import Console

        return Console(highlight=False, **kwargs)
    except ImportError as exc:
        raise ImportError("rich is required for builder-II TUI") from exc
