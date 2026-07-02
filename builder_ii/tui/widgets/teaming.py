from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static


class DeepAgentTeamingScreen(ModalScreen[list[str]]):
    """An interactive wizard to select agents for orchestration."""

    CSS = """
    DeepAgentTeamingScreen {
        align: center middle;
        background: rgba(13, 17, 23, 0.8);
    }
    #teaming-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        background: #161b22;
        border: tall #d2a8ff;
        padding: 1 2;
    }
    #teaming-title {
        text-align: center;
        text-style: bold;
        color: #d2a8ff;
        margin-bottom: 1;
    }
    #teaming-list {
        height: auto;
        max-height: 1fr;
        margin-bottom: 1;
        border: solid #30363d;
        padding: 0 1;
    }
    .agent-checkbox {
        color: #c9d1d9;
    }
    #teaming-buttons {
        align: center bottom;
        height: auto;
    }
    Button {
        margin: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        from builder_ii.agent_profiles import agent_profiles
        profiles = agent_profiles()

        with Vertical(id="teaming-dialog"):
            yield Static("╔══════════════════════════════════════════╗\n"
                         "║      DEEPAGENTS TEAMING & DISPATCH       ║\n"
                         "╚══════════════════════════════════════════╝", id="teaming-title")

            with ScrollableContainer(id="teaming-list"):
                for p in profiles:
                    yield Checkbox(f"{p.name} [{p.authority}]", id=f"agent-{p.name}", classes="agent-checkbox")

            with Horizontal(id="teaming-buttons"):
                yield Button("Dispatch Squad", id="btn-dispatch", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss([])
        elif event.button.id == "btn-dispatch":
            selected = []
            for cb in self.query(Checkbox):
                if cb.value and cb.id:
                    # extract name from 'agent-{name}'
                    selected.append(cb.id.replace("agent-", ""))
            self.dismiss(selected)
