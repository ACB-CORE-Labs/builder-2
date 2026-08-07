"""Task entry for a governed run — the operator says what they want done.

The one place in STRATUM where an operator states intent in their own words rather than
selecting from what the console already knows about. What they type becomes the task bound into
a passive `read_only` session manifest, which the governed run command then re-validates at its
own boundary before anything spawns.

This screen collects text and dismisses with it. It writes nothing, spawns nothing, and decides
nothing: the app is what resolves ratification, and the governed CLI is what runs.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class TaskEntryScreen(ModalScreen[str | None]):
    """Ask the operator what the governed run should do."""

    BINDINGS = [
        Binding("escape", "dismiss_task", "Cancel", show=False),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._input: Input | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="cli-container"):
            yield Static(
                " [bold #3fb950]GOVERNED RUN[/]  [#6e7681]read-only tools · every call ledgered[/]",
                id="palette-title",
            )
            yield Static(
                " [#6e7681]Goose runs against this repo with builder-II as its only tool surface:[/]\n"
                " [#6e7681]read, list and search, path-jailed. No shell, no edits, no network.[/]",
                id="cli-hint",
            )
            self._input = Input(
                placeholder="what should this run do? (e.g. map how the HITL patch lane fits together)",
                id="cli-input",
            )
            yield self._input

    def on_mount(self) -> None:
        if self._input:
            self._input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        task = event.value.strip()
        self.dismiss(task or None)

    def action_dismiss_task(self) -> None:
        self.dismiss(None)
