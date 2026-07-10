"""Command Composer Modal — governed context injection. It composes; it never executes.

Press `~` to open. Pre-fills current chain context (target, session ID) as flags so the operator
can carry location context into their terminal. STRATUM runs no command: `builder` reaches TIER_3
and TIER_4 surfaces whose approval boundaries a keypress may not launder.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class CLIPassthroughScreen(ModalScreen[str | None]):
    """Floating terminal input for raw builder-II commands."""

    BINDINGS = [
        Binding("escape", "dismiss_cli", "Close", show=False),
    ]

    def __init__(self, prefix_context: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.prefix_context = prefix_context
        self._input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="cli-container"):
            yield Static(
                " [bold #3fb950]~ RAW CLI PASSTHROUGH[/]  [#484f58]Governed Context Injection[/]",
                id="palette-title",  # Reusing palette title style
            )
            # We show what context is being injected
            if self.prefix_context:
                yield Static(
                    f" [bold #6e7681]Injected Context:[/] [#79c0ff]{self.prefix_context}[/]",
                    id="cli-hint",
                )
            else:
                yield Static(" [#484f58]No active session context to inject.[/]", id="cli-hint")

            self._input = Input(
                value=self.prefix_context if self.prefix_context else "",
                placeholder="Enter builder command (e.g., 'start --task \"fix login\"')",
                id="cli-input",
            )
            yield self._input

    def on_mount(self) -> None:
        """Focus the input when the modal is mounted."""
        if self._input:
            self._input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        raw_cmd = event.value.strip()
        if not raw_cmd:
            self.dismiss(None)
            return

        self.dismiss(raw_cmd)

    def action_dismiss_cli(self) -> None:
        self.dismiss(None)


# ── Utility Modals ───────────────────────────────────────────────────


class ConfirmScreen(ModalScreen[bool]):
    """Two-key confirmation screen."""

    BINDINGS = [
        Binding("escape", "dismiss_false", "Cancel", show=False),
        Binding("enter", "confirm_true", "Confirm", show=False),
        Binding("y", "confirm_true", "Confirm", show=False),
        Binding("n", "dismiss_false", "Cancel", show=False),
    ]

    def __init__(self, title: str, body: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self.title_text, id="confirm-title")
            yield Static(self.body_text, id="confirm-body")
            yield Static(
                "[#484f58]Press [bold #3fb950]ENTER[/] to confirm, or [bold #f85149]ESC[/] to cancel[/]",
                id="confirm-hint",
            )

    def action_confirm_true(self) -> None:
        self.dismiss(True)

    def action_dismiss_false(self) -> None:
        self.dismiss(False)


class RejectScreen(ModalScreen[str | None]):
    """Rejection annotation screen."""

    BINDINGS = [
        Binding("escape", "dismiss_cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self._input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="reject-dialog"):
            yield Static(self.title_text, id="reject-title")
            self._input = Input(placeholder="Optional reason for rejection...", id="reject-input")
            yield self._input
            yield Static(
                "[#484f58]Press [bold #3fb950]ENTER[/] to reject, or [bold #f85149]ESC[/] to cancel[/]",
                id="reject-hint",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_dismiss_cancel(self) -> None:
        self.dismiss(None)
