"""Main STRATUM TUI Application."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Static

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.config import load_settings
from builder_ii.tui.widgets.cli_passthrough import CLIPassthroughScreen, ConfirmScreen
from builder_ii.tui.widgets.palette import CommandPaletteScreen
from builder_ii.tui.widgets.signals import SignalRail
from builder_ii.tui.widgets.spine import ArtifactSpine
from builder_ii.tui.widgets.stratum import ActiveStratum, StratumMode

# Rendered wherever a chain digest would go. `verify_artifact_chain` exposes no digest, so there
# is nothing truthful to bind here; STRATUM shows that absence rather than a value shaped like a
# digest. A previous revision interpolated the artifact count and the validity flag into a
# digest-shaped string and rendered it in this slot -- a fabricated digest, in a codebase whose
# governance rests on digests binding evidence. Absence is displayed as absence; never defaulted,
# never synthesized, never inferred. `tests/test_stratum_tui.py` pins that no source file under
# `builder_ii/tui/` may contain a digest-shaped literal at all, so it cannot creep back.
CHAIN_DIGEST_ABSENT = "—"

# Surfaces that are still mockups. `builder stratum`'s command_authority record must name exactly
# these -- no fewer (it would understate what is unfinished) and no more (it would understate what
# now works). `tests/test_stratum_tui.py` pins that correspondence in both directions, because
# `builder-platform audit-docs` only catches docs that *overstate* a capability, never docs that
# understate one, and truth is symmetric even when the audit is not.
STRATUM_UNIMPLEMENTED_SURFACES: tuple[str, ...] = ("HITL diff viewer",)


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
        Binding("enter", "pin_artifact", "Pin (Enter)", show=False),
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
        from textual.theme import Theme

        from builder_ii.tui_theme import _REGISTRY, active_theme_name, list_themes, theme_extras, theme_palette

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
            },
        )
        self.register_theme(default_theme)

        theme_name = active_theme_name()
        if theme_name in list_themes() and theme_name != "default":
            p = theme_palette()
            e = theme_extras()

            bg = e.get("_bg", e.get("_navy", p["dim"]))
            panel = e.get("_panel", bg)
            panel_light = e.get("_panel_light", p["dim"])
            border = e.get("_border", p["dim"])
            selected = e.get("_selected", p["active"])
            hover = e.get("_hover", p["dim"])

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
                    "stratum-bg": bg,
                    "stratum-panel": panel,
                    "stratum-border": border,
                    "stratum-panel-light": panel_light,
                    "stratum-selected": selected,
                    "stratum-hover": hover,
                    "stratum-brand": p["active"],
                    "stratum-model": p["pass"],
                    "stratum-tier": p["warn"],
                    "stratum-session": p["hint"],
                    "stratum-selected-text": p["bold"],
                    "stratum-disabled": p["dim"],
                },
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

            # Re-verify chain to update chain digest asynchronously
            await self._verify_current_chain_async()

            if self.banner:
                self.banner.refresh()

    async def _verify_current_chain_async(self) -> None:
        """Run verify_artifact_chain on current artifacts asynchronously in a thread."""
        if not self.artifacts_dir.exists():
            return

        def _verify():
            paths = [p for p in self.artifacts_dir.glob("*.json") if p.is_file()]
            if not paths:
                return None
            return verify_artifact_chain(paths)

        try:
            report = await asyncio.to_thread(_verify)
            if report is None:
                return

            valid = report.get("valid", False)
            counts = report.get("counts", {})
            length = counts.get("files", 0)

            if self.stratum:
                # No digest, and no authority evaluation, was performed here -- say so. "Not
                # evaluated" is not "denied", and an absent digest is not a short one.
                self.stratum.set_chain_digest(CHAIN_DIGEST_ABSENT)
                self.stratum.set_authority_granted(None)

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
            self.stratum.set_platform_info(
                {
                    "platform": "builder-II",
                    "target": self.settings.core_repo.name,
                    "model": self.settings.model_alias,
                    "backend": self.settings.backend,
                    "session": self._current_session_id,
                    "memory_atoms": "0",  # Would read from memory browser
                    "chain_length": "0",
                    "chain_valid_display": "[#6e7681]—[/]",
                    "ledger_display": "[#3fb950]ACTIVE ✓[/]" if self.artifacts_dir.exists() else "[#d29922]INACTIVE[/]",
                }
            )

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

            self.push_screen(
                ConfirmScreen("GATE OPEN", "A HITL gate is currently open. Are you sure you want to quit?"), check_quit
            )
        else:
            self.exit()

    def action_open_palette(self) -> None:
        """Open the command palette."""
        cmds = []
        from builder_ii.command_authority import check_command_authority
        for rec in COMMAND_AUTHORITY_REGISTRY:
            decision = check_command_authority(rec.name)
            allowed = decision.allowed
            reason = ", ".join(decision.reasons) if decision.reasons else ""

            cmds.append(
                {
                    "name": rec.name,
                    "tier": rec.tier,
                    "promotion_state": rec.promotion_state,
                    "allowed": allowed,
                    "reason": reason,
                    "requires_authority": rec.tier in ("TIER_3", "TIER_4"),
                }
            )

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
            # This announced a dispatch and wrote `orchestration_assignment.json` under a bare
            # assignment kind. Nothing was dispatched, and that kind does not exist -- the governed
            # one carries a `_plan` suffix. So
            # the TUI fabricated a success, invented an artifact kind to record it under, and wrote
            # the result somewhere nothing reads. Fabricated success is the defect Ladder 4 removed
            # from `deepagents_runtime`; it does not get to live on behind a keybinding.
            if selected_agents:
                self.notify(
                    "STRATUM cannot dispatch subagents or write assignment artifacts; run "
                    "`builder-deepagents assign-subagent` in your terminal.",
                    severity="warning",
                )

        self.push_screen(DeepAgentTeamingScreen(), on_dispatch)

    def action_toggle_platform_audit(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.PLATFORM_AUDIT else StratumMode.PLATFORM_AUDIT
            )

    def action_toggle_workflow(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.WORKFLOW else StratumMode.WORKFLOW

    def action_toggle_quality_gates(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.QUALITY_GATES else StratumMode.QUALITY_GATES
            )

    def action_toggle_tooling(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.TOOLING_HEALTH else StratumMode.TOOLING_HEALTH
            )

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
            self.stratum.inspect_artifact(
                {
                    "status": "awaiting_generation",
                    "message": f"The '{selected.get('label')}' artifact has not been generated for this session yet.",
                }
            )

    # ── Pipeline Actions ──────────────────────────────────────────────────

    def action_prepare_package(self) -> None:
        from builder_ii.tui.widgets.workspace_builder import SessionBuilderScreen

        def on_save(config: dict[str, Any]) -> None:
            # This used to write `session_config.json` into the artifact root, tagged
            # under a session-config kind that is registered nowhere (the governed one is
            # SESSION_CONFIG_KIND in `session_config.py`), and that nothing
            # outside this TUI ever read. So the record's "No direct write authority at TUI render
            # level" was false, and the bytes it wrote were not a governed artifact by any
            # definition. The screen still collects the operator's choices; emitting them is the
            # governed CLI's job, and only its job.
            if config:
                self.notify(
                    "STRATUM does not write artifacts; run `builder-session prepare-package` "
                    "in your terminal to emit a governed session package.",
                    severity="warning",
                )

        self.push_screen(SessionBuilderScreen(), on_save)

    async def action_validate_package(self) -> None:
        self.notify("Validating package...")
        await self._verify_current_chain_async()

    def action_launch_goose(self) -> None:
        """Refuse. STRATUM must not launch a runtime the governed CLI gates at a higher tier.

        This binding used to call `goose_launcher.launch_goose_session`, which spawns
        `goose session --with-builtin developer,skills,summon` -- the developer builtin carries file
        editing and shell. No read-only policy, no launch receipt, no approval.

        `builder stratum` is TIER_2, operator-managed, and its record declares no write authority.
        The governed command for exactly this runtime, `builder-goose start-readonly`, is TIER_3,
        STATE_READ_ONLY_RUNTIME_CANDIDATE, bounded by read-only policies, and "requires implicit or
        explicit HITL approval for launch." A keypress inside a TIER_2 render surface must not
        launder a TIER_3 approval boundary. Same principle that makes the HITL approve/reject
        actions constitutive refusals: the surface that renders authority state does not get to
        originate authority.
        """
        self.notify(
            "STRATUM cannot start a Goose runtime; run `builder-goose start-readonly` in your "
            "terminal, where the read-only policy and launch approval apply.",
            severity="warning",
        )

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
                            self.signals.append_event(
                                datetime.now().strftime("%H:%M:%S"), "cli_passthrough", f"builder {cmd}"
                            )

                self.push_screen(CLIPassthroughScreen(prefix_context=f"{next_cmd}"), run_cli)
            else:
                self.notify("No pending actions found in Operator Next report.")
        except Exception as e:
            self.notify(f"Error generating next action: {e}", severity="error")

    # ── HITL Actions ──────────────────────────────────────────────────────

    def action_approve_hitl(self) -> None:
        if not self.stratum or self.stratum.mode != StratumMode.HITL_GATE:
            return
        self.notify("TUI cannot harvest confirmation for a digest it renders; run `builder-hitl approve-patch` in your terminal instead.", severity="warning")

    def action_reject_hitl(self) -> None:
        if not self.stratum or self.stratum.mode != StratumMode.HITL_GATE:
            return
        self.notify("STRATUM is display-only and cannot mutate approval state; run `builder-hitl rejection-record` in your terminal instead.", severity="warning")

    def action_inspect_hitl(self) -> None:
        if self.stratum and self.stratum.mode == StratumMode.HITL_GATE:
            artifact = self.stratum._hitl_proposal.get("artifact", {})
            self.stratum.inspect_artifact(artifact)

    def action_diff_hitl(self) -> None:
        self.notify(f"{STRATUM_UNIMPLEMENTED_SURFACES[0]} is not implemented in this surface.")
