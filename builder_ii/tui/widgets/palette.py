"""Command Palette — Governed command discovery surface.

Press `?` from anywhere to overlay this modal. Commands are grouped by tier,
blocked commands show their reason, and authority-requiring commands are flagged.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

# ── Tier display info ────────────────────────────────────────────────

TIER_LABELS = {
    "TIER_0": ("T0", "#3fb950", "READ-ONLY"),
    "TIER_1": ("T1", "#58a6ff", "ARTIFACT-ONLY"),
    "TIER_2": ("T2", "#d2a8ff", "OPERATOR"),
    "TIER_3": ("T3", "#ffa657", "HITL-GATED"),
    "TIER_4": ("T4", "#f85149", "FORBIDDEN"),
}


# ── Single Palette Entry ────────────────────────────────────────────

class PaletteEntry(Static):
    """A single command entry in the palette."""

    def __init__(
        self,
        cmd_name: str,
        tier: str,
        promotion_state: str,
        allowed: bool,
        reason: str = "",
        requires_authority: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.cmd_name = cmd_name
        self.cmd_tier = tier
        self.cmd_promotion = promotion_state
        self.cmd_allowed = allowed
        self.cmd_reason = reason
        self.cmd_requires_authority = requires_authority
        self.add_class("palette-item")

    def render(self) -> str:
        tier_short, tier_color, tier_label = TIER_LABELS.get(
            self.cmd_tier, ("??", "#484f58", "UNKNOWN")
        )

        # Authority flag
        auth_glyph = " [bold #ffa657]⚡[/]" if self.cmd_requires_authority else "  "

        if self.cmd_allowed:
            return (
                f"  [{tier_color}]{tier_short}[/]  "
                f"[#79c0ff]{self.cmd_name:<40}[/]"
                f"{auth_glyph}"
                f"  [#484f58]{tier_label}[/]"
            )
        return (
            f"  [{tier_color}]{tier_short}[/]  "
            f"[#484f58]{self.cmd_name:<40}[/]"
            f"  [#484f58]⊘ {self.cmd_reason[:30]}[/]"
        )


# ── Command Palette Modal ───────────────────────────────────────────

class CommandPaletteScreen(ModalScreen[str | None]):
    """Full-screen command palette with fuzzy search and governed display."""

    BINDINGS = [
        Binding("escape", "dismiss_palette", "Close", show=False),
    ]

    def __init__(self, commands: list[dict[str, Any]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._commands = commands or []
        self._entries: list[PaletteEntry] = []
        self._filtered: list[PaletteEntry] = []
        self._search_input: Input | None = None
        self._results_container: ScrollableContainer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Static(
                "[bold #c9d1d9]⌘ COMMAND PALETTE[/]  "
                "[#484f58]type to search · ESC to close[/]",
                id="palette-title",
            )
            with Vertical(id="palette-search"):
                self._search_input = Input(
                    placeholder="Search commands… (e.g., 'goose', 'verify', 'hitl')",
                    id="palette-input",
                )
                yield self._search_input
            self._results_container = ScrollableContainer(id="palette-results")
            with self._results_container:
                self._build_entries()
                for entry in self._entries:
                    yield entry

    def _build_entries(self) -> None:
        """Build palette entries from command records."""
        # Sort by tier, then by name
        sorted_cmds = sorted(
            self._commands,
            key=lambda c: (c.get("tier", "TIER_4"), c.get("name", "")),
        )
        for cmd in sorted_cmds:
            entry = PaletteEntry(
                cmd_name=cmd.get("name", "unknown"),
                tier=cmd.get("tier", "TIER_0"),
                promotion_state=cmd.get("promotion_state", ""),
                allowed=cmd.get("allowed", True),
                reason=cmd.get("reason", ""),
                requires_authority=cmd.get("requires_authority", False),
            )
            self._entries.append(entry)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter entries based on search text."""
        query = event.value.lower().strip()
        if not query:
            for entry in self._entries:
                entry.display = True
            return

        for entry in self._entries:
            entry.display = query in entry.cmd_name.lower()

    def action_dismiss_palette(self) -> None:
        self.dismiss(None)

    def on_static_click(self, event: Static.Click) -> None:
        """Handle clicking on a palette entry."""
        # Walk up to find the PaletteEntry
        widget = event.widget if hasattr(event, 'widget') else None
        if isinstance(widget, PaletteEntry) and widget.cmd_allowed:
            self.dismiss(widget.cmd_name)
