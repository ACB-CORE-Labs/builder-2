"""Theme palette markup helpers for STRATUM instruments.

All colours come from ``theme_palette()`` — no hardcoded hex in call sites.
"""

from __future__ import annotations

from typing import Literal

from builder_ii.core.tui_theme import theme_palette

StatusKind = Literal["pass", "warn", "fail", "hint", "active", "dim", "bold", "accent", "pending", "gate", "disabled"]

_STATUS_GLYPHS: dict[str, tuple[str, str]] = {
    # "present" is the honest spine status for file-on-disk (not cryptographic proof).
    # "verified" retained as alias so older CSS/tests do not blank-glyph.
    "present": ("█", "pass"),
    "verified": ("█", "pass"),
    "pass": ("✓", "pass"),
    "gate": ("▒", "warn"),
    "warn": ("●", "warn"),
    "pending": ("░", "dim"),
    "failed": ("✗", "fail"),
    "fail": ("✗", "fail"),
    "disabled": ("⊘", "dim"),
    "active": ("▶", "active"),
    "unevaluated": ("—", "hint"),
}


def themed(role: str, text: str) -> str:
    """Wrap ``text`` in Rich markup using a semantic palette role."""
    p = theme_palette()
    colour = p.get(role, p["hint"])
    return f"[{colour}]{text}[/]"


def bold_themed(role: str, text: str) -> str:
    p = theme_palette()
    colour = p.get(role, p["bold"])
    return f"[bold {colour}]{text}[/]"


def section_title(text: str, role: str = "active") -> str:
    """Section header using a palette role (not a secret token)."""
    return bold_themed(role, text)


def rule(width: int = 46) -> str:
    return themed("dim", "─" * width)


def kv(label: str, value: str, *, value_role: str = "bold", label_width: int = 14) -> str:
    pad = max(0, label_width - len(label))
    return f"  {themed('hint', label + ' ' * pad)}  {themed(value_role, value)}"


def status_glyph(status: str) -> str:
    """Return a themed density glyph for a spine / gate status string."""
    glyph, role = _STATUS_GLYPHS.get(status, ("?", "hint"))
    return themed(role, glyph)


def epistemic_node(label: str, state: str, digest: str) -> tuple[str, str]:
    """Return (label_markup, digest_markup) for one epistemic stage."""
    d = digest if digest else "—"
    if state == "completed":
        return bold_themed("pass", f"✓ {label:<9}"), themed("dim", f"{d:<11}")
    if state == "active":
        return bold_themed("active", f"▶ {label:<9}"), themed("bold", f"{d:<11}")
    if state == "failed":
        return bold_themed("fail", f"✗ {label:<9}"), themed("fail", f"{'MISMATCH':<11}")
    return themed("dim", f"○ {label:<9}"), themed("dim", f"{'—':<11}")
