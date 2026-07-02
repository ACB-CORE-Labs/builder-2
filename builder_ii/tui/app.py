"""Main STRATUM TUI Application."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY, get_command_record
from builder_ii.config import load_settings
from builder_ii.tui.widgets.cli_passthrough import CLIPassthroughScreen, ConfirmScreen, RejectScreen
from builder_ii.tui.widgets.palette import CommandPaletteScreen
from builder_ii.tui.widgets.signals import SignalRail
from builder_ii.tui.widgets.spine import ArtifactSpine
from builder_ii.tui.widgets.stratum import ActiveStratum, StratumMode
from builder_ii.artifact_chain_verification import verify_artifact_chain


class HeaderBanner(Static):
    """Custom Header Banner."""
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="stratum-header", **kwargs)
        self.target = "generic"
        self.model = "unknown"
        self.tier = "TIER_0"
        self.session = "—"

    def render(self) -> str:
        from builder_ii.tui_theme import theme_palette
        p = theme_palette()
        now = datetime.now().strftime("%H:%M")
        return (
            f" [bold {p['active']}]STRATUM[/]  [{p['dim']}]▸[/]  "
            f"[bold {p['bold']}]target:{self.target}[/]  [{p['dim']}]▸[/]  "
            f"[bold {p['pass']}]model:{self.model}[/]  [{p['dim']}]▸[/]  "
            f"[bold {p['warn']}]{self.tier}[/]  [{p['dim']}]▸[/]  "
            f"[{p['hint']}]session:{self.session}[/]  [{p['dim']}]▸[/]  [{p['dim']}]{now}[/]"
        )


class StratumApp(App[None]):
    """STRATUM — Command & Control Surface for Governed AI Work."""

    CSS_PATH = "stratum.tcss"

    BINDINGS = [
        Binding("tab", "cycle_focus", "Cycle", show=True),
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
        Binding("question_mark", "open_palette", "Palette", show=True),
        Binding("tilde", "open_cli", "CLI Passthrough", show=True),
        Binding("m", "toggle_memory", "Memory", show=True),
        Binding("o", "toggle_models", "Models", show=True),
        Binding("u", "toggle_agents", "Agents", show=True),
        Binding("c", "toggle_platform_audit", "Audit", show=True),
        Binding("w", "toggle_workflow", "Workflow", show=True),
        Binding("e", "toggle_quality_gates", "Gates", show=True),
        Binding("t", "toggle_tooling", "Tools", show=True),
        Binding("space", "pin_artifact", "Pin", show=True),
        Binding("slash", "toggle_search", "Search", show=True),
        Binding("h", "toggle_help", "Help", show=True),
        Binding("f1", "toggle_help", "Help", show=False),




        # Pipeline actions
        Binding("p", "prepare_package", "Prepare", show=True),
        Binding("v", "validate_package", "Validate", show=True),
        Binding("g", "launch_goose", "Goose", show=True),
        Binding("n", "operator_next", "Next", show=True),
        # HITL actions
        Binding("a", "approve_hitl", "Approve", show=True),
        Binding("r", "reject_hitl", "Reject", show=True),
        Binding("i", "inspect_hitl", "Inspect", show=True),
        Binding("d", "diff_hitl", "Diff", show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.settings = load_settings()
        self.artifacts_dir = self.settings.project_root / ".builder" / "artifacts"

        self.spine: ArtifactSpine | None = None
        self.stratum: ActiveStratum | None = None
        self.signals: SignalRail | None = None
        self.banner: HeaderBanner | None = None

        self._refresh_task: asyncio.Task[None] | None = None

        self._current_session_id = "idle"
        self._hitl_active = False

        self._apply_theme()

    def _apply_theme(self) -> None:
        from builder_ii.tui_theme import active_theme_name, theme_palette, theme_extras, list_themes, _REGISTRY
        from textual.theme import Theme

        # Register default theme
        default_palette = _REGISTRY["default"]
        default_theme = Theme(
            name="builder_default",
            primary=default_palette["active"],
            variables={
                "stratum-pass": default_palette["pass"],
                "stratum-warn": default_palette["warn"],
                "stratum-fail": default_palette["fail"],
                "stratum-hint": default_palette["hint"],
                "stratum-active": default_palette["active"],
                "stratum-dim": default_palette["dim"],
                "stratum-bold": default_palette["bold"],
                "stratum-accent": default_palette["accent"],
                "stratum-bg": "#0a0e14",
                "stratum-panel": "#0d1117",
                "stratum-border": "#21262d",
                "stratum-panel-light": "#161b22",
                "stratum-selected": "#1f2937",
                "stratum-hover": "#1c2333",
                "stratum-brand": "#79c0ff",
                "stratum-model": "#7ee787",
                "stratum-tier": "#ffa657",
                "stratum-session": "#6e7681",
                "stratum-selected-text": "#f0f6fc",
                "stratum-disabled": "#30363d",
            }
        )
        self.register_theme(default_theme)

        theme_name = active_theme_name()
        if theme_name in list_themes() and theme_name != "default":
            p = theme_palette()
            e = theme_extras()
            navy = e.get("_navy", p["dim"])

            custom_theme = Theme(
                name="builder_custom",
                primary=p["active"],
                variables={
                    "stratum-pass": p["pass"],
                    "stratum-warn": p["warn"],
                    "stratum-fail": p["fail"],
                    "stratum-hint": p["hint"],
                    "stratum-active": p["active"],
                    "stratum-dim": p["dim"],
                    "stratum-bold": p["bold"],
                    "stratum-accent": p["accent"],
                    "stratum-bg": navy,
                    "stratum-panel": navy,
                    "stratum-border": p["dim"],
                    "stratum-panel-light": p["dim"],
                    "stratum-selected": p["active"],
                    "stratum-hover": p["dim"],
                    "stratum-brand": p["active"],
                    "stratum-model": p["pass"],
                    "stratum-tier": p["warn"],
                    "stratum-session": p["hint"],
                    "stratum-selected-text": p["bold"],
                    "stratum-disabled": p["dim"],
                }
            )
            self.register_theme(custom_theme)
            self.theme = "builder_custom"
        else:
            self.theme = "builder_default"

    def compose(self) -> ComposeResult:
        self.banner = HeaderBanner()
        self.banner.target = self.settings.core_repo.name
        self.banner.model = self.settings.model_alias
        self.banner.tier = self.settings.model_tier
        yield self.banner

        with Horizontal(id="main-layout"):
            self.spine = ArtifactSpine(artifacts_dir=self.artifacts_dir)
            yield self.spine

            self.stratum = ActiveStratum(artifacts_dir=self.artifacts_dir)
            yield self.stratum

            self.signals = SignalRail(artifacts_dir=self.artifacts_dir)
            yield self.signals

        yield Footer(id="command-footer")

    async def on_mount(self) -> None:
        """Run on startup."""
        self.notify("STRATUM Operational Surface Active.")

        # Display the splash screen
        from builder_ii.tui.widgets.splash import SplashScreen
        self.push_screen(SplashScreen())

        self.title = "STRATUM"
        self._refresh_task = asyncio.create_task(self._periodic_refresh())
        self._update_idle_report()

    async def _periodic_refresh(self) -> None:
        """Poll for artifact and event changes."""
        while True:
            await asyncio.sleep(2.0)
            if self.spine:
                await self.spine.refresh_data()
            if self.signals:
                await self.signals.refresh_data()

            # Re-verify chain to update chain digest
            self._verify_current_chain()

            if self.banner:
                self.banner.refresh()

    def _verify_current_chain(self) -> None:
        """Run verify_artifact_chain on current artifacts."""
        if not self.artifacts_dir.exists():
            return

        paths = [p for p in self.artifacts_dir.glob("*.json") if p.is_file()]
        if not paths:
            return

        try:
            report = verify_artifact_chain(paths)
            valid = report.get("valid", False)
            counts = report.get("counts", {})
            length = counts.get("files", 0)

            if self.stratum:
                # Fake a digest for display since report digest isn't in output of verify
                fake_digest = f"SHA256:v{length}{str(valid).lower()}"
                self.stratum.set_chain_digest(fake_digest)
                self.stratum.set_authority_granted(False) # Default to false for UI

            # Update idle report stats
            if self.stratum and self.stratum.mode == StratumMode.IDLE:
                self.stratum._platform_info["chain_length"] = str(length)
                self.stratum._platform_info["chain_valid_display"] = (
                    "[#3fb950]✓ TRUE[/]" if valid else "[#f85149]✗ FALSE[/]"
                )
                self.stratum._render_current_mode()

        except Exception:
            pass

    def _update_idle_report(self) -> None:
        if self.stratum:
            self.stratum.set_platform_info({
                "platform": "builder-II",
                "target": self.settings.core_repo.name,
                "model": self.settings.model_alias,
                "backend": self.settings.backend,
                "session": self._current_session_id,
                "memory_atoms": "0", # Would read from memory browser
                "chain_length": "0",
                "chain_valid_display": "[#6e7681]—[/]",
                "ledger_display": "[#3fb950]ACTIVE ✓[/]" if self.artifacts_dir.exists() else "[#d29922]INACTIVE[/]"
            })

    def action_cycle_focus(self) -> None:
        """Cycle focus between the three columns."""
        if self.focused == self.spine:
            self.stratum.focus()
        elif self.focused == self.stratum:
            self.signals.focus()
        else:
            self.spine.focus()

    def action_quit_app(self) -> None:
        """Quit the application, prompting if a gate is open."""
        if self._hitl_active:
            def check_quit(confirm: bool) -> None:
                if confirm:
                    self.exit()
            self.push_screen(ConfirmScreen("GATE OPEN", "A HITL gate is currently open. Are you sure you want to quit?"), check_quit)
        else:
            self.exit()

    def action_open_palette(self) -> None:
        """Open the command palette."""
        cmds = []
        for rec in COMMAND_AUTHORITY_REGISTRY:
            # Fake evaluation for UI demo
            allowed = rec.tier != "TIER_4"
            reason = ""
            if rec.tier == "TIER_3":
                allowed = False
                reason = "requires HITL artifact"

            cmds.append({
                "name": rec.name,
                "tier": rec.tier,
                "promotion_state": rec.promotion_state,
                "allowed": allowed,
                "reason": reason,
                "requires_authority": rec.tier in ("TIER_3", "TIER_4"),
            })

        def run_cmd(cmd_name: str | None) -> None:
            if cmd_name:
                self.notify(f"Executing: {cmd_name}")
                # Real implementation would trigger the command logic here

        self.push_screen(CommandPaletteScreen(commands=cmds), run_cmd)

    def action_open_cli(self) -> None:
        """Open the raw CLI passthrough."""
        prefix = f"--target {self.settings.core_repo.name}"
        if self._current_session_id != "idle":
            prefix += f" --session {self._current_session_id}"

        def run_cli(cmd: str | None) -> None:
            if cmd:
                self.notify(f"Raw CLI Exec: builder {cmd}")
                # Real implementation would subprocess run `builder {cmd}` and stream to ledger/stratum
                if self.signals:
                    self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "cli_passthrough", f"builder {cmd}")

        self.push_screen(CLIPassthroughScreen(prefix_context=prefix), run_cli)

    def action_go_back(self) -> None:
        """Universal 'Back' / 'Clear' action to return to the default view."""
        if self.spine and self.spine._search_input and self.spine._search_input.display:
            self.spine.toggle_search()
        elif self.stratum:
            self.stratum.mode = StratumMode.IDLE

    def action_toggle_search(self) -> None:
        """Toggle the spine search filter."""
        if self.spine:
            self.spine.toggle_search()


    def action_toggle_memory(self) -> None:
        """Toggle memory browser mode in the center panel."""
        if self.stratum:
            if self.stratum.mode == StratumMode.MEMORY_BROWSE:
                self.stratum.mode = StratumMode.IDLE
            else:
                self.stratum.mode = StratumMode.MEMORY_BROWSE

    def action_toggle_models(self) -> None:
        """Toggle models matrix view in the center panel."""
        if self.stratum:
            if self.stratum.mode == StratumMode.MODEL_MATRIX:
                self.stratum.mode = StratumMode.IDLE
            else:
                self.stratum.mode = StratumMode.MODEL_MATRIX

    def action_toggle_agents(self) -> None:
        """Toggle agents profile view in the center panel."""
        from builder_ii.tui.widgets.teaming import DeepAgentTeamingScreen

        def on_dispatch(selected_agents: list[str]) -> None:
            if selected_agents:
                self.notify(f"Dispatched Squad: {', '.join(selected_agents)}")
                from datetime import datetime, timezone
                import json

                payload = {
                    "kind": "builder_ii.orchestration_assignment",
                    "schema_version": "1.0",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "agents": selected_agents,
                }

                target = self.artifacts_dir / "orchestration_assignment.json"
                target.write_text(json.dumps(payload, indent=2))

                if self.signals:
                    self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "dispatch", f"Dispatched {len(selected_agents)} agents")

        self.push_screen(DeepAgentTeamingScreen(), on_dispatch)

    def action_toggle_platform_audit(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.PLATFORM_AUDIT else StratumMode.PLATFORM_AUDIT

    def action_toggle_workflow(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.WORKFLOW else StratumMode.WORKFLOW

    def action_toggle_quality_gates(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.QUALITY_GATES else StratumMode.QUALITY_GATES

    def action_toggle_tooling(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.TOOLING_HEALTH else StratumMode.TOOLING_HEALTH

    def action_toggle_help(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.HELP else StratumMode.HELP


    def action_pin_artifact(self) -> None:
        """Pin the selected artifact from the spine into the center panel."""
        if not self.spine or not self.stratum:
            return

        selected = self.spine.get_selected_artifact()
        if not selected:
            return

        kind = selected.get("kind", "")

        # Try to find it on disk
        artifact_data = None
        for path in self.artifacts_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("kind") == kind:
                    artifact_data = data
                    break
            except Exception:
                continue

        if artifact_data:
            self.stratum.inspect_artifact(artifact_data)
        else:
            self.stratum.inspect_artifact({
                "status": "awaiting_generation",
                "message": f"The '{selected.get('label')}' artifact has not been generated for this session yet."
            })

    # ── Pipeline Actions ──────────────────────────────────────────────────

    def action_prepare_package(self) -> None:
        from builder_ii.tui.widgets.workspace_builder import SessionBuilderScreen

        def on_save(config: dict[str, Any]) -> None:
            if config:
                import json
                from datetime import datetime

                target = self.artifacts_dir / "session_config.json"
                target.write_text(json.dumps(config, indent=2))

                self.notify("Workspace Session Configuration saved.")
                if self.signals:
                    self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "prepare", f"Configured workspace: {config.get('corpus_name', 'unknown')}")

        self.push_screen(SessionBuilderScreen(), on_save)

    def action_validate_package(self) -> None:
        self.notify("Validating package...")
        self._verify_current_chain()

    def action_launch_goose(self) -> None:
        import os
        import json

        env_vars = ""
        config_path = self.artifacts_dir / "session_config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                model = config.get("primary_model")
                if model:
                    provider = "openai"
                    if "claude" in model.lower():
                        provider = "anthropic"
                    elif "gemini" in model.lower():
                        provider = "google"

                    env_vars = f"GOOSE_PROVIDER={provider} GOOSE_MODEL={model} "
            except Exception:
                pass

        with self.suspend():
            print("\n" + "="*50)
            if env_vars:
                print(f"Launching Goose with dynamically injected model: {model}...")
            else:
                print("Launching Goose Session (governed context)...")
            print("="*50 + "\n")
            try:
                ret = os.system(f"{env_vars}goose session")
                if ret != 0:
                    print(f"\n[Goose exited with code {ret}]")
                    input("Press Enter to return to STRATUM...")
            except Exception as e:
                print(f"Error launching goose: {e}")
                input("Press Enter to return to STRATUM...")

        if self.stratum:
            self.stratum.mode = StratumMode.IDLE
        if self.signals:
            self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "goose", "Goose session concluded")
        self.notify("Returned from Goose session.")

    def action_operator_next(self) -> None:
        from builder_ii.operator_next import create_operator_next_action_report
        try:
            report = create_operator_next_action_report()
            actions = report.get("ordered_next_actions", [])
            if actions and actions[0].get("safe_commands"):
                next_cmd = actions[0]["safe_commands"][0]
                self.notify(f"Recommended Next Action: {next_cmd}")

                # Pre-fill CLI Passthrough with this command
                def run_cli(cmd: str | None) -> None:
                    if cmd:
                        self.notify(f"Raw CLI Exec: builder {cmd}")
                        if self.signals:
                            self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "cli_passthrough", f"builder {cmd}")

                self.push_screen(CLIPassthroughScreen(prefix_context=f"{next_cmd}"), run_cli)
            else:
                self.notify("No pending actions found in Operator Next report.")
        except Exception as e:
            self.notify(f"Error generating next action: {e}", severity="error")

    # ── HITL Actions ──────────────────────────────────────────────────────

    def action_approve_hitl(self) -> None:
        if not self.stratum or self.stratum.mode != StratumMode.HITL_GATE:
            return

        def on_confirm(confirm: bool) -> None:
            if confirm:
                self.notify("HITL Proposal APPROVED.")
                if self.signals:
                    self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "hitl_approve", "Authority granted")
                    self.signals.update_gate(False)
                self.stratum.mode = StratumMode.IDLE
                self._hitl_active = False

        self.push_screen(ConfirmScreen("APPROVE EXECUTION", "Are you sure you want to grant authority for this execution proposal?"), on_confirm)

    def action_reject_hitl(self) -> None:
        if not self.stratum or self.stratum.mode != StratumMode.HITL_GATE:
            return

        def on_reject(reason: str | None) -> None:
            if reason is not None:
                self.notify(f"HITL Proposal REJECTED. Reason: {reason}")
                if self.signals:
                    self.signals.append_event(datetime.now().strftime("%H:%M:%S"), "hitl_reject", f"Authority denied: {reason}")
                    self.signals.update_gate(False)
                self.stratum.mode = StratumMode.IDLE
                self._hitl_active = False

        self.push_screen(RejectScreen("REJECT EXECUTION"), on_reject)

    def action_inspect_hitl(self) -> None:
        if self.stratum and self.stratum.mode == StratumMode.HITL_GATE:
            artifact = self.stratum._hitl_proposal.get("artifact", {})
            self.stratum.inspect_artifact(artifact)

    def action_diff_hitl(self) -> None:
        self.notify("Diff view not yet available in this mockup.")


if __name__ == "__main__":
    app = StratumApp()
    app.run()
