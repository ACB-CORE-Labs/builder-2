"""Command Palette — Governed command discovery surface.

Press `?` from anywhere to overlay this modal. Commands are grouped by tier,
blocked commands show their reason, and authority-requiring commands are flagged.

Keyboard-first: arrows / j/k move selection, Enter confirms an allowed entry,
Escape dismisses. Mouse click remains available as a second path.
"""

from __future__ import annotations

from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from builder_ii.tui.widget_ids import widget_id

# ── Tier display info ────────────────────────────────────────────────

def _tier_labels() -> dict[str, tuple[str, str, str]]:
    from builder_ii.command_authority import TIER_0, TIER_1, TIER_2, TIER_3, TIER_4
    from builder_ii.tui_theme import theme_palette

    p = theme_palette()
    return {
        TIER_0: ("T0", p["pass"], "READ-ONLY"),
        TIER_1: ("T1", p["active"], "ARTIFACT-ONLY"),
        TIER_2: ("T2", p["accent"], "OPERATOR"),
        TIER_3: ("T3", p["warn"], "HITL-GATED"),
        TIER_4: ("T4", p["fail"], "FORBIDDEN"),
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
        # Addressable by the command it stands for, so a driver can click one entry out of 463
        # without tab-cycling to it. `setdefault` leaves an explicitly passed id alone -- which is
        # how `_build_entries` resolves the collision case below.
        kwargs.setdefault("id", widget_id("palette-entry", cmd_name))
        super().__init__(**kwargs)
        self.cmd_name = cmd_name
        self.cmd_tier = tier
        self.cmd_promotion = promotion_state
        self.cmd_allowed = allowed
        self.cmd_reason = reason
        self.cmd_requires_authority = requires_authority
        self.add_class("palette-item")

    def render(self) -> str:
        from builder_ii.tui_theme import theme_palette

        p = theme_palette()
        tier_short, tier_color, tier_label = _tier_labels().get(
            self.cmd_tier, ("??", p["dim"], "UNKNOWN")
        )

        auth_glyph = f" [bold {p['warn']}]⚡[/]" if self.cmd_requires_authority else "  "
        selected = "palette-item-selected" in self.classes
        cursor = f"[{p['active']}]▸[/]" if selected else " "

        if self.cmd_allowed:
            return (
                f"{cursor} [{tier_color}]{tier_short}[/]  "
                f"[{p['active']}]{self.cmd_name:<40}[/]"
                f"{auth_glyph}"
                f"  [{p['dim']}]{tier_label}[/]"
            )
        return (
            f"{cursor} [{tier_color}]{tier_short}[/]  "
            f"[{p['dim']}]{self.cmd_name:<40}[/]  "
            f"[{p['dim']}]⊘ {self.cmd_reason[:30]}[/]"
        )


# ── Command Palette Modal ───────────────────────────────────────────


class CommandPaletteScreen(ModalScreen[str | None]):
    """Full-screen command palette with fuzzy search and governed display."""

    BINDINGS = [
        Binding("escape", "dismiss_palette", "Close", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up (vim)", show=False),
        Binding("j", "move_down", "Down (vim)", show=False),
        Binding("enter", "select_entry", "Select", show=False),
    ]

    def __init__(self, commands: list[dict[str, Any]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._commands = commands or []
        self._entries: list[PaletteEntry] = []
        self._filtered: list[PaletteEntry] = []
        self._selected_index = 0
        self._search_input: Input | None = None
        self._results_container: ScrollableContainer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-container"):
            yield Static(
                "[bold #c9d1d9]⌘ COMMAND PALETTE[/]  "
                "[#484f58]type to search · ↑↓/jk · Enter select · ESC close[/]",
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

    def on_mount(self) -> None:
        self._rebuild_filtered()
        self._apply_selection_highlight()
        if self._search_input is not None:
            self._search_input.focus()

    def _build_entries(self) -> None:
        """Build palette entries from command records."""
        from builder_ii.command_authority import TIER_4
        # Sort by tier, then by name
        sorted_cmds = sorted(
            self._commands,
            key=lambda c: (c.get("tier", TIER_4), c.get("name", "")),
        )
        # Two records carrying one name would claim one id, and Textual answers same-id siblings
        # with `MountError` -- the palette would not open at all. The real registry holds 463
        # distinct names and never reaches the suffix branch, which
        # `test_palette_entry_ids_are_unique_across_the_real_registry` pins. This exists so that an
        # arbitrary `commands` list, where a duplicate row used to render harmlessly, cannot become
        # a crash now that entries carry ids. The sort above fixes the order, so the suffix a given
        # command receives is deterministic.
        claimed: set[str] = set()
        for cmd in sorted_cmds:
            name = cmd.get("name", "unknown")
            entry_id = widget_id("palette-entry", name)
            if entry_id in claimed:
                suffix = 2
                while f"{entry_id}-{suffix}" in claimed:
                    suffix += 1
                entry_id = f"{entry_id}-{suffix}"
            claimed.add(entry_id)
            entry = PaletteEntry(
                id=entry_id,
                cmd_name=name,
                tier=cmd.get("tier", TIER_4),
                promotion_state=cmd.get("promotion_state", ""),
                allowed=cmd.get("allowed", True),
                reason=cmd.get("reason", ""),
                requires_authority=cmd.get("requires_authority", False),
            )
            self._entries.append(entry)

    def _visible_entries(self) -> list[PaletteEntry]:
        return [e for e in self._entries if e.display]

    def _rebuild_filtered(self) -> None:
        self._filtered = self._visible_entries()
        if self._filtered:
            self._selected_index = max(0, min(self._selected_index, len(self._filtered) - 1))
        else:
            self._selected_index = 0

    def _apply_selection_highlight(self) -> None:
        visible = self._visible_entries()
        for i, entry in enumerate(self._entries):
            if entry in visible and visible and entry is visible[self._selected_index]:
                entry.add_class("palette-item-selected")
            else:
                entry.remove_class("palette-item-selected")
            entry.refresh()
        if visible and 0 <= self._selected_index < len(visible):
            try:
                visible[self._selected_index].scroll_visible(animate=False)
            except Exception:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter entries based on search text."""
        query = event.value.lower().strip()
        if not query:
            for entry in self._entries:
                entry.display = True
        else:
            for entry in self._entries:
                entry.display = query in entry.cmd_name.lower()
        self._selected_index = 0
        self._rebuild_filtered()
        self._apply_selection_highlight()

    def action_move_up(self) -> None:
        visible = self._visible_entries()
        if not visible:
            return
        self._selected_index = (self._selected_index - 1) % len(visible)
        self._apply_selection_highlight()

    def action_move_down(self) -> None:
        visible = self._visible_entries()
        if not visible:
            return
        self._selected_index = (self._selected_index + 1) % len(visible)
        self._apply_selection_highlight()

    def action_select_entry(self) -> None:
        """Confirm the keyboard-highlighted entry (same path as click)."""
        visible = self._visible_entries()
        if not visible or not (0 <= self._selected_index < len(visible)):
            return
        entry = visible[self._selected_index]
        if entry.cmd_allowed:
            self.dismiss(entry.cmd_name)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the search field confirms the highlighted entry (not a new search)."""
        event.stop()
        self.action_select_entry()

    def action_dismiss_palette(self) -> None:
        self.dismiss(None)

    def on_click(self, event: events.Click) -> None:
        """Handle clicking on a palette entry."""
        # Walk up to find the PaletteEntry
        widget = event.widget if hasattr(event, "widget") else None
        if isinstance(widget, PaletteEntry) and widget.cmd_allowed:
            self.dismiss(widget.cmd_name)

    def on_key(self, event: events.Key) -> None:
        """When focus is in the search Input, still allow j/k/arrows via bindings.

        Textual delivers binding actions when the screen has them; Input may swallow
        some keys. Up/down/enter are bound at screen level; this keeps j/k usable
        while typing is focused (j/k only navigate when the input is empty so
        operators can still type those letters in the query).
        """
        if event.key in ("j", "k") and self._search_input is not None:
            if self._search_input.value:
                return  # let the character enter the search field
            if event.key == "j":
                self.action_move_down()
                event.stop()
            elif event.key == "k":
                self.action_move_up()
                event.stop()
