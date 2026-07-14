"""Session prepare configurator — collects choices; never writes artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from builder_ii.tui.projections.render import bold_themed, themed


class SessionBuilderScreen(ModalScreen[dict[str, Any]]):
    """Interactive wizard to configure a prepare-package compose line."""

    CSS = """
    SessionBuilderScreen {
        align: center middle;
        background: rgba(10, 14, 20, 0.85);
    }
    #builder-dialog {
        width: 60;
        height: auto;
        background: $stratum-panel-light;
        border: tall $stratum-active;
        padding: 1 2;
    }
    #builder-title {
        text-align: center;
        text-style: bold;
        color: $stratum-active;
        margin-bottom: 1;
    }
    .builder-label {
        color: $stratum-bold;
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
            yield Static(
                f"{bold_themed('active', 'SESSION PREPARE')}\n"
                f"{themed('hint', 'compose only · no artifact writes')}",
                id="builder-title",
            )

            yield Static("Target profile:", classes="builder-label")
            yield Select(
                [("generic", "generic"), ("builder", "builder"), ("core", "core")],
                id="input-target",
                value="generic",
            )

            yield Static("Task / corpus label:", classes="builder-label")
            yield Input(placeholder="e.g. onboard-docs", id="input-corpus")

            yield Static("Primary model alias:", classes="builder-label")
            model_options = self._model_options()
            default_val = model_options[0][0] if model_options else Select.BLANK
            yield Select(model_options or [("—", "—")], id="input-model", value=default_val)

            with Horizontal(id="builder-buttons"):
                yield Button("Compose prepare-package", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="error")

    def _model_options(self) -> list[tuple[str, str]]:
        try:
            from builder_ii.model_client_registry import create_model_client_registry

            registry = create_model_client_registry()
            opts: list[tuple[str, str]] = []
            for client in registry.get("clients") or []:
                if not isinstance(client, dict):
                    continue
                alias = str(client.get("model_alias") or client.get("model_name") or "")
                if alias:
                    opts.append((alias, alias))
            return opts
        except Exception:
            return []

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss({})
        elif event.button.id == "btn-save":
            corpus = self.query_one("#input-corpus", Input).value
            target_sel = self.query_one("#input-target", Select)
            model_sel = self.query_one("#input-model", Select)
            target = str(target_sel.value) if target_sel.value != Select.BLANK else "generic"
            model = str(model_sel.value) if model_sel.value != Select.BLANK else ""
            # Matches: builder-session prepare-package TARGET -o DIR [--task …]
            task = corpus.strip() or "stratum-session"
            compose = (
                f"uv run builder-session prepare-package {target} "
                f"-o .builder/session --task \"{task}\""
            )
            config = {
                "schema_version": "1.0",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "target": target,
                "corpus_name": corpus,
                "primary_model": model,
                "compose_command": compose,
            }
            self.dismiss(config)
