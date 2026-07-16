"""Deepagents teaming compose screen — selects profiles; never dispatches."""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from builder_ii.tui.projections.agents import project_agent_roster
from builder_ii.tui.projections.render import bold_themed, themed

# Textual DOM ids: letters, numbers, underscores, hyphens only (no dots).
_ID_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _widget_id_for_profile(name: str) -> str:
    """Map a profile name (may contain '.') to a valid Textual widget id."""
    safe = _ID_SAFE.sub("-", name).strip("-")
    if not safe or safe[0].isdigit():
        safe = f"p-{safe}" if safe else "p-unknown"
    return f"agent-{safe}"


class DeepAgentTeamingScreen(ModalScreen[list[str]]):
    """Select agent profiles and compose assignment commands — no dispatch."""

    CSS = """
    DeepAgentTeamingScreen {
        align: center middle;
        background: rgba(10, 14, 20, 0.85);
    }
    #teaming-dialog {
        width: 64;
        height: auto;
        max-height: 80%;
        background: $stratum-panel-light;
        border: tall $stratum-accent;
        padding: 1 2;
    }
    #teaming-title {
        text-align: center;
        text-style: bold;
        color: $stratum-accent;
        margin-bottom: 1;
    }
    #teaming-list {
        height: auto;
        max-height: 1fr;
        margin-bottom: 1;
        border: solid $stratum-border;
        padding: 0 1;
    }
    .agent-checkbox {
        color: $stratum-bold;
    }
    #teaming-buttons {
        align: center bottom;
        height: auto;
    }
    Button {
        margin: 0 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # widget id → original profile name (preserves dots in names like core.invariant_auditor)
        self._id_to_profile: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        roster = project_agent_roster()
        with Vertical(id="teaming-dialog"):
            yield Static(
                f"{bold_themed('accent', 'DEEPAGENTS COMPOSE')}\n"
                f"{themed('hint', 'select profiles · STRATUM never dispatches')}",
                id="teaming-title",
            )
            yield Static(
                themed(
                    "hint",
                    f"readiness: {roster.readiness_verdict} · dep: {roster.dependency_state}",
                )
            )
            with ScrollableContainer(id="teaming-list"):
                used_ids: set[str] = set()
                for p in roster.profiles:
                    widget_id = _widget_id_for_profile(p.name)
                    # Uniquify if two names sanitize to the same id
                    base = widget_id
                    n = 2
                    while widget_id in used_ids:
                        widget_id = f"{base}-{n}"
                        n += 1
                    used_ids.add(widget_id)
                    self._id_to_profile[widget_id] = p.name
                    yield Checkbox(
                        f"{p.name} [{p.authority}]",
                        id=widget_id,
                        classes="agent-checkbox",
                    )
            with Horizontal(id="teaming-buttons"):
                yield Button("Compose Assignment", id="btn-compose", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss([])
        elif event.button.id == "btn-compose":
            selected: list[str] = []
            for cb in self.query(Checkbox):
                if cb.value and cb.id:
                    selected.append(self._id_to_profile.get(cb.id, cb.id))
            self.dismiss(selected)
