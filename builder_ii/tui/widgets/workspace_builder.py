from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, Select
from textual.containers import Vertical, Horizontal

class SessionBuilderScreen(ModalScreen[dict[str, Any]]):
    """An interactive wizard to configure a new workspace session."""

    CSS = """
    SessionBuilderScreen {
        align: center middle;
        background: rgba(13, 17, 23, 0.8);
    }
    #builder-dialog {
        width: 60;
        height: auto;
        background: #161b22;
        border: tall #58a6ff;
        padding: 1 2;
    }
    #builder-title {
        text-align: center;
        text-style: bold;
        color: #58a6ff;
        margin-bottom: 1;
    }
    .builder-label {
        color: #c9d1d9;
        margin-top: 1;
    }
    #builder-buttons {
        align: center bottom;
        height: auto;
        margin-top: 1;
    }
    Button {
        margin: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="builder-dialog"):
            yield Static("╔══════════════════════════════════════════╗\n"
                         "║      WORKSPACE SESSION CONFIGURATOR      ║\n"
                         "╚══════════════════════════════════════════╝", id="builder-title")
            
            yield Static("Target URI:", classes="builder-label")
            yield Input(placeholder="e.g. file:///Users/you/project", id="input-uri")
            
            yield Static("Corpus Name:", classes="builder-label")
            yield Input(placeholder="e.g. MyProject", id="input-corpus")
            
            yield Static("Primary Model:", classes="builder-label")
            from builder_ii.model_client_registry import model_registry
            models = [(m.model_name, m.model_name) for m in model_registry()]
            default_val = "claude-3-5-sonnet" if any(m[0] == "claude-3-5-sonnet" for m in models) else (models[0][0] if models else None)
            yield Select(models, id="input-model", value=default_val)
            
            with Horizontal(id="builder-buttons"):
                yield Button("Save & Prepare", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss({})
        elif event.button.id == "btn-save":
            uri_input = self.query_one("#input-uri", Input)
            corpus_input = self.query_one("#input-corpus", Input)
            model_input = self.query_one("#input-model", Select)
            
            config = {
                "kind": "builder_ii.session_config",
                "schema_version": "1.0",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "target_uri": uri_input.value,
                "corpus_name": corpus_input.value,
                "primary_model": model_input.value if model_input.value != Select.BLANK else "",
            }
            self.dismiss(config)
