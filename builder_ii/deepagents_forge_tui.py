"""
deepagents_forge_tui.py

Textual TUI wizard for the deepagents Forge.
This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
    TextArea,
)

from builder_ii.deepagents_forge_emit import emit_agent
from builder_ii.deepagents_forge_preview import render_preview
from builder_ii.deepagents_forge_schema import DeepAgentSpec
from builder_ii.deepagents_forge_wizard import ForgeWizard


class ForgeProgressBar(Static):
    """Renders a step counter and filled progress bar."""

    def set_progress(self, current: int, total: int) -> None:
        filled = int((current / total) * 20) if total else 0
        bar = "▓" * filled + "░" * (20 - filled)
        self.update(f"Step {current}/{total}  [{bar}]")


class ForgeSpecPane(Static):
    """Always-visible bottom pane showing accumulated spec summary."""

    def refresh_spec(self, spec: DeepAgentSpec) -> None:
        lines = spec.summary_lines()
        self.update("\n".join(lines) if lines else "(no fields set yet)")


class ForgePreviewWidget(Static):
    """Renders governance checklist, warnings, YAML preview, and write summary."""

    def set_spec(self, spec: DeepAgentSpec) -> None:
        preview = render_preview(spec)
        gov = preview.governance_check
        lines = ["=== Governance Checklist ==="]
        if gov is not None:
            lines.extend(gov.as_lines())
        lines.append("")
        if preview.warnings:
            lines.append("=== Warnings ===")
            lines.extend(f"  ⚠  {warning}" for warning in preview.warnings)
            lines.append("")
        lines.append("=== Agent Spec (YAML) ===")
        lines.append(preview.yaml_preview)
        lines.append("=== What will be written ===")
        lines.append(preview.profile_diff)
        self.update("\n".join(lines))


class ForgeScreen(Screen):
    """Main Textual screen for the Forge wizard."""

    BINDINGS = [
        Binding("escape", "abort", "Abort"),
        Binding("ctrl+b", "back", "Back"),
    ]

    CSS = """
    ForgeScreen {
        layout: vertical;
    }
    #forge-header {
        height: 4;
        background: $primary;
        color: $text;
        padding: 1 2;
    }
    #forge-progress {
        color: $accent;
    }
    #forge-body {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    #forge-prompt {
        margin-bottom: 1;
        color: $text-muted;
    }
    #forge-hint {
        margin-bottom: 1;
        color: $text-disabled;
        text-style: italic;
    }
    #forge-governance-note {
        margin-bottom: 1;
        color: $warning;
    }
    #forge-input {
        margin-bottom: 1;
    }
    #forge-spec-pane {
        height: 8;
        background: $surface;
        border-top: solid $primary;
        padding: 0 2;
        color: $text-muted;
    }
    #forge-nav {
        height: 3;
        align: center middle;
        background: $surface-darken-1;
    }
    #forge-result {
        padding: 1 2;
        color: $success;
    }
    """

    def __init__(self, wizard: ForgeWizard, dry_run: bool = False) -> None:
        super().__init__()
        self.wizard = wizard
        self.dry_run = dry_run
        self._current_checkboxes: dict[str, Checkbox] = {}
        self._governance_fields: dict[str, str] = {}
        self._emitted = False

    def compose(self) -> ComposeResult:
        with Container(id="forge-header"):
            yield Label("deepagents Forge", id="forge-title")
            yield ForgeProgressBar(id="forge-progress")
        with ScrollableContainer(id="forge-body"):
            yield Static("", id="forge-prompt")
            yield Static("", id="forge-hint")
            yield Static("", id="forge-governance-note")
            yield Container(id="forge-input-area")
            yield Static("", id="forge-result")
        with Container(id="forge-spec-pane"):
            yield ForgeSpecPane(id="forge-spec-display")
        with Horizontal(id="forge-nav"):
            yield Button("← Back", id="btn-back", variant="default")
            yield Button("Skip", id="btn-skip", variant="default")
            yield Button("Next →", id="btn-next", variant="primary")
            yield Button("✗ Abort", id="btn-abort", variant="error")

    def on_mount(self) -> None:
        self._render_current_step()

    def _render_current_step(self) -> None:
        if self.wizard.is_complete():
            self._render_complete()
            return

        step = self.wizard.current_step()
        current, total = self.wizard.get_progress()

        self.query_one("#forge-title", Label).update(f"deepagents Forge — {step.title}")
        self.query_one("#forge-progress", ForgeProgressBar).set_progress(current, total)
        self.query_one("#forge-prompt", Static).update(step.prompt)
        self.query_one("#forge-hint", Static).update(step.hint or "")
        self.query_one("#forge-governance-note", Static).update(step.governance_note or "")
        self.query_one("#forge-result", Static).update("")

        input_area = self.query_one("#forge-input-area", Container)
        input_area.remove_children()
        self._current_checkboxes = {}
        self._governance_fields = {}
        self._emitted = False

        if step.render_mode == "dry_run_preview":
            preview_widget = ForgePreviewWidget(id="forge-preview")
            input_area.mount(preview_widget)
            preview_widget.set_spec(self.wizard.spec)
        elif step.multi_select:
            current_vals = getattr(self.wizard.spec, step.field or "", []) or []
            for option in step.options:
                checkbox = Checkbox(option, value=(option in current_vals), id=f"cb_{option}")
                self._current_checkboxes[option] = checkbox
                input_area.mount(checkbox)
        elif step.options and not step.multi_select and not step.fields:
            current_val = getattr(self.wizard.spec, step.field or "", "") or step.default or ""
            radio_set = RadioSet(id="forge-radioset")
            input_area.mount(radio_set)
            for option in step.options:
                radio_set.mount(RadioButton(option, value=(option == current_val)))
        elif step.multi_line:
            current_val = getattr(self.wizard.spec, step.field or "", "") or ""
            input_area.mount(TextArea(current_val, id="forge-textarea"))
        elif step.fields:
            for field_name in step.fields:
                current_val = getattr(self.wizard.spec, field_name, "") or ""
                input_area.mount(Label(field_name.replace("_", " ").title() + ":"))
                self._governance_fields[field_name] = str(current_val)
                input_area.mount(
                    Input(
                        value=str(current_val),
                        placeholder=field_name,
                        id=f"gov_input_{field_name}",
                    )
                )
        else:
            current_val = getattr(self.wizard.spec, step.field or "", "") or ""
            input_area.mount(
                Input(
                    value=str(current_val),
                    placeholder=step.hint or step.field or "",
                    id="forge-input",
                )
            )

        self.query_one("#forge-spec-display", ForgeSpecPane).refresh_spec(self.wizard.spec)

    def _collect_current_value(self):
        step = self.wizard.current_step()

        if step.render_mode == "dry_run_preview":
            return True

        if step.multi_select:
            return [option for option, checkbox in self._current_checkboxes.items() if checkbox.value]

        if step.options and not step.multi_select and not step.fields:
            try:
                radio_set = self.query_one("#forge-radioset", RadioSet)
                if radio_set.pressed_button:
                    return str(radio_set.pressed_button.label)
            except Exception:
                pass
            return step.default or (step.options[0] if step.options else "")

        if step.multi_line:
            try:
                return self.query_one("#forge-textarea", TextArea).text
            except Exception:
                return ""

        if step.fields:
            result = {}
            for field_name in step.fields:
                try:
                    input_widget = self.query_one(f"#gov_input_{field_name}", Input)
                    result[field_name] = input_widget.value
                except Exception:
                    result[field_name] = self._governance_fields.get(field_name, "")
            return result

        try:
            return self.query_one("#forge-input", Input).value
        except Exception:
            return ""

    def on_input_changed(self, event: Input.Changed) -> None:
        step = self.wizard.current_step()
        if step.fields and event.input.id and event.input.id.startswith("gov_input_"):
            field_name = event.input.id[len("gov_input_"):]
            self._governance_fields[field_name] = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "btn-abort":
            self.app.exit(result=None)
            return

        if button_id == "btn-back":
            self.wizard.back()
            self._render_current_step()
            return

        if button_id == "btn-skip":
            skipped = self.wizard.skip()
            if skipped:
                self._render_current_step()
            else:
                self.query_one("#forge-result", Static).update("⚠  This step is required and cannot be skipped.")
            return

        if button_id == "btn-next":
            if self._emitted or str(event.button.label) == "Done":
                self.app.exit(result=self.wizard.spec)
                return

            step = self.wizard.current_step()
            if step.render_mode == "dry_run_preview":
                self._do_emit()
                return

            value = self._collect_current_value()
            result = self.wizard.apply(value)
            if result.ok:
                self._render_current_step()
            else:
                self.query_one("#forge-result", Static).update(f"\u274c  {result.error}")

    def _do_emit(self) -> None:
        """Run emit_agent once and show result."""
        emit_result = emit_agent(self.wizard.spec, dry_run=self.dry_run)
        self.query_one("#forge-result", Static).update("\n".join(emit_result.as_lines()))
        if emit_result.ok:
            self._emitted = True
            input_area = self.query_one("#forge-input-area", Container)
            input_area.remove_children()
            self.query_one("#btn-next", Button).label = "Done"

    def _render_complete(self) -> None:
        self.query_one("#forge-prompt", Static).update("Agent spec complete. Press Next to emit.")

    def action_abort(self) -> None:
        self.app.exit(result=None)

    def action_back(self) -> None:
        self.wizard.back()
        self._render_current_step()


class ForgeApp(App):
    """Textual application that hosts the ForgeScreen."""

    TITLE = "deepagents Forge"
    SUB_TITLE = "builder-II interactive agent creation wizard"

    def __init__(self, wizard: ForgeWizard, dry_run: bool = False) -> None:
        super().__init__()
        self._wizard = wizard
        self._dry_run = dry_run

    def on_mount(self) -> None:
        self.push_screen(ForgeScreen(self._wizard, dry_run=self._dry_run))


def run_forge_tui(
    seed_name: str = "",
    seed_profile: str = "generic",
    dry_run: bool = False,
) -> Optional[DeepAgentSpec]:
    """
    Launch the Forge TUI wizard.
    Returns the completed DeepAgentSpec, or None if aborted.
    """
    wizard = ForgeWizard(seed_name=seed_name, seed_profile=seed_profile)
    app = ForgeApp(wizard=wizard, dry_run=dry_run)
    app.run()
    ready, _ = wizard.spec.is_emit_ready()
    return wizard.spec if ready else None
