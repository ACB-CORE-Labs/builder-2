"""Main STRATUM TUI Application."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Static

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    TIER_3,
    TIER_4,
    check_command_authority,
)
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
        # A *model* tier, not a command-authority tier: `on_mount` sets this from
        # `settings.model_tier`, whose vocabulary is `config.MODEL_TIERS == ("primary", "fast")`
        # and is enforced there with a ValueError. Binding this placeholder to
        # `command_authority.TIER_0` put a value from an unrelated vocabulary ("Tier 0 — read-only
        # inspection") into the field -- one `load_settings` would itself reject -- and implied to
        # the next reader that this slot displays authority tier, which it never has. "unknown"
        # matches the sibling `self.model` placeholder: not-yet-loaded, and obviously not a real
        # tier.
        self.tier = "unknown"
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
        Binding("y", "toggle_orchestration", "Orch", show=True),
        Binding("b", "toggle_code_vault", "Vault", show=True),
        Binding("e", "toggle_quality_gates", "Gates", show=True),
        Binding("t", "toggle_tooling", "Tools", show=True),
        Binding("space", "pin_artifact", "Pin", show=True),
        Binding("enter", "pin_artifact", "Pin (Enter)", show=False),
        Binding("slash", "toggle_search", "Search", show=True),
        Binding("h", "toggle_help", "Help", show=True),
        Binding("f1", "toggle_help", "Help", show=False),
        Binding("0", "open_guide", "Guide", show=True),
        Binding("x", "dismiss_guide", "Dismiss guide", show=False),
        Binding("left_square_bracket", "help_prev", "Help prev", show=False),
        Binding("right_square_bracket", "help_next", "Help next", show=False),
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

    def __init__(
        self,
        *,
        show_guide: bool | None = None,
        skip_guide: bool = False,
        show_splash: bool = True,
        **kwargs: Any,
    ) -> None:
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
        # show_guide=True forces walkthrough; skip_guide/--no-guide opts out
        self._force_show_guide = bool(show_guide)
        self._force_skip_guide = bool(skip_guide)
        self._show_splash = bool(show_splash)
        self._hitl_notified = False

        self._apply_theme()

    def _apply_theme(self) -> None:
        from textual.theme import Theme

        from builder_ii.tui_theme import _REGISTRY, active_theme_name, list_themes, theme_extras, theme_palette

        # Register default Cosmic Void theme from palette + extras
        default_palette = _REGISTRY["default"]
        default_extras = {k: v for k, v in default_palette.items() if k.startswith("_")}
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
                "stratum-bg": default_extras.get("_bg", "#0a0e14"),
                "stratum-panel": default_extras.get("_panel", "#0d1117"),
                "stratum-border": default_extras.get("_border", "#21262d"),
                "stratum-panel-light": default_extras.get("_panel_light", "#161b22"),
                "stratum-selected": default_extras.get("_selected", "#1f2937"),
                "stratum-hover": default_extras.get("_hover", "#1c2333"),
                "stratum-brand": default_palette["active"],
                "stratum-model": default_palette["pass"],
                "stratum-tier": default_palette["warn"],
                "stratum-session": default_palette["hint"],
                "stratum-selected-text": default_extras.get("_selected_text", "#f0f6fc"),
                "stratum-disabled": default_extras.get("_disabled", "#30363d"),
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
        self.banner.target = self.settings.target_repo.name
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
        self.notify("STRATUM operator console active — observe & compose only.")

        # Opening splash: hero image ~3s (or any key), then instruments
        if self._show_splash:
            from builder_ii.tui.widgets.splash import SplashScreen

            try:
                root = Path(self.settings.project_root)
            except (TypeError, ValueError):
                root = None
            self.push_screen(SplashScreen(project_root=root))

        self.title = "STRATUM"
        if self.spine is not None:
            self.spine.set_selection_handler(self._on_spine_selection)
        if self.stratum is not None:
            try:
                self.stratum.set_repo_root(Path(self.settings.project_root))
            except (TypeError, ValueError):
                pass
        self._refresh_task = asyncio.create_task(self._periodic_refresh())
        self._update_idle_report()
        self._maybe_open_first_run_guide()
        self._maybe_surface_hitl()

    def _maybe_open_first_run_guide(self) -> None:
        from builder_ii.stratum_guide import should_auto_open_guide

        if not self.stratum:
            return
        try:
            root = Path(self.settings.project_root)
        except (TypeError, ValueError):
            return
        try:
            open_guide = should_auto_open_guide(
                project_root=root,
                artifacts_dir=self.artifacts_dir if isinstance(self.artifacts_dir, Path) else None,
                force_show=self._force_show_guide,
                force_skip=self._force_skip_guide,
            )
        except (TypeError, OSError):
            return
        if open_guide:
            self.stratum.mode = StratumMode.GUIDE
            self.notify(
                "First-session walkthrough — press X to opt out of auto-open, 0 anytime.",
                timeout=6,
            )

    def action_open_guide(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.GUIDE else StratumMode.GUIDE
            )

    def action_dismiss_guide(self) -> None:
        from builder_ii.stratum_guide import dismiss_guide

        if not self.stratum or self.stratum.mode != StratumMode.GUIDE:
            return
        path = dismiss_guide(self.settings.project_root)
        self.stratum.mode = StratumMode.IDLE
        self.notify(f"Walkthrough auto-open dismissed ({path.name}). Press 0 anytime to reopen.")

    def action_help_next(self) -> None:
        if self.stratum and self.stratum.mode == StratumMode.HELP:
            self.stratum.cycle_help_page(1)

    def action_help_prev(self) -> None:
        if self.stratum and self.stratum.mode == StratumMode.HELP:
            self.stratum.cycle_help_page(-1)

    def _on_spine_selection(self, stage: dict[str, str] | None) -> None:
        """Auto-inspect selected spine stage (progressive disclosure)."""
        if not stage or not self.stratum:
            return
        # Only auto-inspect when already inspecting or idle — do not yank operator out of instruments
        if self.stratum.mode not in (StratumMode.IDLE, StratumMode.ARTIFACT_INSPECT):
            return
        self._inspect_stage(stage)

    def _inspect_stage(self, stage: dict[str, str]) -> None:
        if not self.stratum:
            return
        from builder_ii.tui.projections.chain import find_artifact_for_kind, find_artifact_path_for_kind

        kind = stage.get("kind", "")
        artifact_data = find_artifact_for_kind(self.artifacts_dir, kind)
        path = find_artifact_path_for_kind(self.artifacts_dir, kind)
        if artifact_data:
            self.stratum.inspect_artifact(artifact_data, path=str(path) if path else None)
        else:
            self.stratum.inspect_artifact(
                {
                    "status": "awaiting_generation",
                    "kind": kind,
                    "message": (
                        f"The '{stage.get('label')}' artifact has not been generated "
                        "for this session yet."
                    ),
                }
            )

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
            self._maybe_surface_hitl(quiet=True)

            if self.banner:
                self.banner.refresh()

    def _maybe_surface_hitl(self, *, quiet: bool = False) -> None:
        """Reflect pending HITL on the signal rail; notify once. Never auto-steal focus mid-instrument."""
        from builder_ii.tui.projections.gates import scan_pending_hitl

        open_, label = scan_pending_hitl(self.artifacts_dir)
        if self.signals:
            self.signals.update_gate(open_, label)
        self._hitl_active = open_
        if open_ and not self._hitl_notified and not quiet:
            self._hitl_notified = True
            self.notify(f"HITL pending: {label} — press I to inspect or open HITL instrument", severity="warning")
        if not open_:
            self._hitl_notified = False

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
        if not self.stratum:
            return
        from builder_ii.tui.projections.operator import idle_report_stats

        # memory_atoms/chain_length were hardcoded "0" here -- a fabricated zero an operator could
        # not tell from a genuine empty state. They now read the real memory-index atom_count and
        # real *.json artifact count (best-effort: any read failure degrades to "—", never crashes
        # mount -- see idle_report_stats).
        memory_atoms, chain_length = idle_report_stats(self.artifacts_dir)

        # set_platform_info replaces the whole dict, so the async verifier's live chain_valid_display
        # (written directly onto _platform_info at verify time) must be carried forward rather than
        # reset to "—": resetting it re-fabricated "not evaluated" over a real verdict on every call.
        existing = self.stratum._platform_info
        self.stratum.set_platform_info(
            {
                "platform": "builder-II",
                "target": self.settings.target_repo.name,
                "model": self.settings.model_alias,
                "backend": self.settings.backend,
                "session": self._current_session_id,
                "memory_atoms": memory_atoms,
                "chain_length": chain_length,
                "chain_valid_display": existing.get("chain_valid_display") or "[#6e7681]—[/]",
                "ledger_display": "[#3fb950]ACTIVE ✓[/]" if self.artifacts_dir.exists() else "[#d29922]INACTIVE[/]",
            }
        )

    def action_cycle_focus(self) -> None:
        """Never runs. TAB does cycle focus, but not through here.

        Textual's `Screen.BINDINGS` binds `tab` to `focus_next`, and bindings resolve from the
        focused widget up through its ancestors to the Screen *before* reaching the App -- so the
        App-level `Binding("tab", "cycle_focus", ...)` above is permanently shadowed. Measured by
        spying on this method: zero calls across five `tab` presses, while focus still advanced
        through five distinct stops (spine-list, stratum-content, RichLog, ledger-log,
        spine-container) under Textual's own `focus_next`. The Footer's "Cycle" hint is therefore
        honest about the behaviour and wrong about its source.

        Do not read this body as live. An audit already mistook it for the mechanism behind TAB and
        reported a focus bug that did not exist. Making it authoritative needs `priority=True` on
        the binding, and would swap Textual-idiomatic traversal for a three-stop cycle that no
        longer reaches the scrollable panes -- a UX change, not a bug fix. Deleting it drops the
        Footer label, since Textual's own tab binding is `show=False`. Both are operator calls;
        `test_tab_cycles_focus_but_not_through_the_app_binding` pins the current state either way.
        """
        # The panes are `X | None` until `compose()` builds them, and this body dereferenced all
        # three unguarded. It has never crashed only because it has never run (see above) -- so the
        # guards are not defensive padding, they are what makes the method's claim about its own
        # liveness checkable. Anything that made this binding live would have hit them.
        if self.focused == self.spine:
            if self.stratum is not None:
                self.stratum.focus()
        elif self.focused == self.stratum:
            if self.signals is not None:
                self.signals.focus()
        elif self.spine is not None:
            self.spine.focus()

    def action_quit_app(self) -> None:
        """Quit the application, prompting if a gate is open."""
        if self._hitl_active:

            # `bool | None`, not `bool`: `ModalScreen[bool]` is dismissed with no argument on
            # escape, and Textual passes that `None` straight to this callback. The annotation
            # claimed a value that cannot be relied on. The body already treated it as falsy.
            def check_quit(confirm: bool | None) -> None:
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
                    # Keyed on the tier constants, never on their identifier spelling. The values
                    # of TIER_3/TIER_4 are prose ("Tier 3 — HITL-gated execution candidate"), so
                    # `rec.tier in ("TIER_3", "TIER_4")` is a comparison that cannot ever be true:
                    # it silently reported 0 of the registry's 29 authority-requiring commands and
                    # made the palette's `⚡` glyph unreachable. `_tier_labels()` was corrected to
                    # bind the constants while this site -- a tuple membership rather than an
                    # assignment -- was left behind, which is why the palette's tier *badges* look
                    # right while its authority *flag* stayed dead.
                    "requires_authority": rec.tier in (TIER_3, TIER_4),
                }
            )

        def on_selected(cmd_name: str | None) -> None:
            # Palette is a tier inspector. Selection composes for the operator; never executes.
            if cmd_name:
                decision = check_command_authority(cmd_name)
                verdict = "permitted" if decision.allowed else "refused"
                reason = f" ({', '.join(decision.reasons)})" if decision.reasons else ""
                self.notify(f"{cmd_name}: {verdict}{reason}.")
                if decision.allowed:
                    self.push_screen(
                        CLIPassthroughScreen(prefix_context=cmd_name),
                        self._show_composed_command,
                    )

        self.push_screen(CommandPaletteScreen(commands=cmds), on_selected)

    def action_open_cli(self) -> None:
        """Compose a governed command with the current context injected. STRATUM runs nothing."""
        prefix = f"--target {self.settings.target_repo.name}"
        if self._current_session_id != "idle":
            prefix += f" --session {self._current_session_id}"

        self.push_screen(CLIPassthroughScreen(prefix_context=prefix), self._show_composed_command)

    def _show_composed_command(self, cmd: str | None) -> None:
        """Surface the composed command for the operator to run. Never claim it ran.

        This said `Raw CLI Exec: builder <cmd>` and appended a `cli_passthrough` event to the signal
        rail -- writing a record of an execution that never occurred into the very panel that shows
        the operator what happened -- next to a comment reading "Real implementation would subprocess
        run". Running an arbitrary `builder` command from here would be the Goose problem again:
        `builder` reaches TIER_3 and TIER_4 surfaces, whose approval boundaries a keypress may not
        launder. So the screen composes, and the operator runs.
        """
        if cmd:
            from builder_ii.stratum_guide import normalize_composed_command

            display = normalize_composed_command(cmd)
            self.notify(f"Composed: {display} — run it in your terminal; STRATUM executes nothing.")

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
        """Show agent roster; second press opens compose picker for assignment."""
        from builder_ii.tui.projections.agents import compose_assign_command
        from builder_ii.tui.widgets.teaming import DeepAgentTeamingScreen

        if self.stratum and self.stratum.mode != StratumMode.AGENT_PROFILES:
            self.stratum.mode = StratumMode.AGENT_PROFILES
            return

        # `list[str] | None`: escaping the picker dismisses with no value. The `not selected_agents`
        # guard below already covered it; only the annotation disagreed.
        def on_compose(selected_agents: list[str] | None) -> None:
            # Constitutive refusal to dispatch — compose the governed CLI only.
            if not selected_agents:
                if self.stratum and self.stratum.mode == StratumMode.AGENT_PROFILES:
                    self.stratum.mode = StratumMode.IDLE
                return
            target = self.settings.target_repo.name if self.settings else "generic"
            profile = selected_agents[0]
            cmd = compose_assign_command(profile, target=target)
            # compose_assign_command returns full binary name; strip for composer prefix style
            prefill = cmd.removeprefix("builder-deepagents ").removeprefix("builder ")
            if cmd.startswith("builder-deepagents"):
                prefill = cmd
            self.notify(
                "STRATUM cannot dispatch subagents or write assignment artifacts; "
                "composed assign-subagent for your terminal.",
                severity="warning",
            )
            self.push_screen(CLIPassthroughScreen(prefix_context=prefill), self._show_composed_command)

        self.push_screen(DeepAgentTeamingScreen(), on_compose)

    def action_toggle_platform_audit(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.PLATFORM_AUDIT else StratumMode.PLATFORM_AUDIT
            )

    def action_toggle_workflow(self) -> None:
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE if self.stratum.mode == StratumMode.WORKFLOW else StratumMode.WORKFLOW

    def action_toggle_orchestration(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.ORCHESTRATION else StratumMode.ORCHESTRATION
            )

    def action_toggle_code_vault(self) -> None:
        if self.stratum:
            self.stratum.mode = (
                StratumMode.IDLE if self.stratum.mode == StratumMode.CODE_VAULT else StratumMode.CODE_VAULT
            )

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
        self._inspect_stage(selected)

    # ── Pipeline Actions ──────────────────────────────────────────────────

    def action_prepare_package(self) -> None:
        from builder_ii.tui.widgets.workspace_builder import SessionBuilderScreen

        # `dict[str, Any] | None`: escaping the builder dismisses with no value, same as above.
        def on_save(config: dict[str, Any] | None) -> None:
            # Collect choices only; emit is the governed CLI's job.
            if not config:
                return
            compose = str(config.get("compose_command") or "builder-session prepare-package")
            self.notify(
                "STRATUM does not write artifacts; run `builder-session prepare-package` "
                "in your terminal (Command Composer prefilled).",
                severity="warning",
            )
            self.push_screen(CLIPassthroughScreen(prefix_context=compose), self._show_composed_command)

        self.push_screen(SessionBuilderScreen(), on_save)

    async def action_validate_package(self) -> None:
        """Re-verify on-disk chain; also offer the governed validate-prepare-package compose line."""
        self.notify("Re-checking artifact chain on disk…")
        await self._verify_current_chain_async()
        # Compose the real package validator — operator runs it; STRATUM does not write.
        self.push_screen(
            CLIPassthroughScreen(
                prefix_context="uv run builder-session validate-prepare-package .builder/session"
            ),
            self._show_composed_command,
        )

    # Fixed argv into builder-II's own governed CLI. Never `goose` directly, and never
    # `goose_launcher.launch_goose_session` -- that spawns `goose session --with-builtin
    # developer,skills,summon`, whose developer builtin carries file editing and shell, takes no
    # preflight snapshot and emits no receipt. `builder-goose start-readonly` runs
    # `GooseRuntimeHarness.launch_readonly`, which spawns `goose session --with-builtin ""` (no
    # builtins at all), snapshots every target file's digest before launch, and on close emits a
    # launch receipt, a close receipt and a no-mutation postflight that FAILS if the target moved.
    GOVERNED_GOOSE_COMMAND = "builder-goose start-readonly"
    _GOOSE_MANIFEST_DIR = "goose"

    def _governed_readonly_manifest(self) -> Path | None:
        """Newest valid read_only Goose session manifest under .builder/goose, if any."""
        from builder_ii.goose_session import validate_goose_session_manifest_file

        manifest_dir = self.artifacts_dir.parent / self._GOOSE_MANIFEST_DIR
        if not manifest_dir.is_dir():
            return None
        candidates = sorted(manifest_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for candidate in candidates:
            if validate_goose_session_manifest_file(candidate):
                continue
            try:
                manifest = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("requested_runtime_mode") == "read_only":
                return candidate
        return None

    def _goose_manifest_compose_line(self) -> str:
        target = "builder" if (Path(self.settings.project_root) / "builder_ii").is_dir() else "generic"
        return (
            f"uv run builder-goose manifest --target {target} --mode read_only "
            f'--task "readonly inspect" --output .builder/goose/session.json'
        )

    def _offer_manual_goose_manifest_compose(self) -> None:
        """Surface the manual mint command; does not run it."""
        self.push_screen(
            CLIPassthroughScreen(prefix_context=self._goose_manifest_compose_line()),
            self._show_composed_command,
        )

    def _mint_readonly_goose_manifest(self) -> Path | None:
        """Operator-approved local prep: scaffold + passive read_only manifest if needed.

        Called only after ConfirmScreen yes. Does not start Goose or grant authority.
        """
        from builder_ii.stratum_prepare import ensure_readonly_goose_manifest

        path, note = ensure_readonly_goose_manifest(
            settings=self.settings,
            builder_root=self.artifacts_dir.parent,
        )
        if path is not None:
            self.notify(note)
            return path
        self.notify(
            f"{note}. Compose a manual manifest when ready.",
            severity="warning",
        )
        self._offer_manual_goose_manifest_compose()
        return None

    def _hand_off_goose_readonly(self, manifest: Path) -> None:
        """Suspend and give the terminal to start-readonly for an existing manifest path."""
        import subprocess
        import sys

        argv = (sys.executable, "-m", "builder_ii.cli.goose_cli", "start-readonly", str(manifest))
        with self.suspend():
            completed = subprocess.run(argv, check=False)  # noqa: S603 - fixed argv, shell=False
        self._render_goose_session_outcome(completed.returncode)

    def _on_goose_autoprep_confirm(self, confirmed: bool | None) -> None:
        """After operator answers the auto-prep prompt for G."""
        if not confirmed:
            self.notify(
                "Skipped auto-prep. Compose a read-only manifest first, or press G again to be asked.",
            )
            self._offer_manual_goose_manifest_compose()
            return
        manifest = self._mint_readonly_goose_manifest()
        if manifest is None:
            return
        self._hand_off_goose_readonly(manifest)

    def action_launch_goose(self) -> None:
        """Hand the terminal to the governed read-only command. STRATUM starts no runtime itself.

        If a valid read_only manifest already exists, hands off immediately. If not, asks the
        operator before minting a passive default under .builder/goose (local convenience only).
        Still fail-closed on command authority; start-readonly applies its own policy, receipts,
        and no-mutation postflight.
        """
        from builder_ii.command_authority import CommandAuthorityError, enforce_command_authority

        try:
            enforce_command_authority(self.GOVERNED_GOOSE_COMMAND)
        except CommandAuthorityError as exc:
            self.notify(f"{self.GOVERNED_GOOSE_COMMAND} is not permitted: {exc}", severity="error")
            return

        existing = self._governed_readonly_manifest()
        if existing is not None:
            self._hand_off_goose_readonly(existing)
            return

        self.push_screen(
            ConfirmScreen(
                "PREPARE READ-ONLY GOOSE MANIFEST?",
                "No valid read-only Goose session manifest found under .builder/goose.\n\n"
                "Create a passive default (stratum-auto-readonly.json) and hand off to "
                "builder-goose start-readonly?\n\n"
                "This only writes a local artifact under .builder/ — it does not start Goose "
                "or grant authority. start-readonly still applies its own policy.",
            ),
            self._on_goose_autoprep_confirm,
        )

    def _render_goose_session_outcome(self, returncode: int) -> None:
        """Report what the governed command did. Never assert an outcome it did not record."""
        if returncode == 0:
            self.notify(f"{self.GOVERNED_GOOSE_COMMAND} completed; receipts written under .builder/receipts.")
        else:
            self.notify(
                f"{self.GOVERNED_GOOSE_COMMAND} exited {returncode}; see its output and receipts.",
                severity="error",
            )
        if self.stratum:
            self.stratum.mode = StratumMode.IDLE
        if self.signals:
            self.signals.append_event(
                datetime.now().strftime("%H:%M:%S"),
                "goose_readonly",
                f"{self.GOVERNED_GOOSE_COMMAND} exited {returncode}",
            )

    def action_operator_next(self) -> None:
        from builder_ii.operator_next import create_operator_next_action_report

        try:
            report = create_operator_next_action_report()
            actions = report.get("ordered_next_actions", [])
            if actions and actions[0].get("safe_commands"):
                next_cmd = actions[0]["safe_commands"][0]
                self.notify(f"Recommended Next Action: {next_cmd}")

                # Pre-fill the composer with the recommendation. It composes; it does not run.
                self.push_screen(CLIPassthroughScreen(prefix_context=f"{next_cmd}"), self._show_composed_command)
            else:
                self.notify("No pending actions found in Operator Next report.")
        except Exception as e:
            self.notify(f"Error generating next action: {e}", severity="error")

    # ── HITL Actions ──────────────────────────────────────────────────────

    def action_approve_hitl(self) -> None:
        if not self.stratum:
            return
        if self.stratum.mode != StratumMode.HITL_GATE and not self.stratum.try_bind_pending_hitl():
            self.notify("No HITL gate open to approve.", severity="warning")
            return
        self.notify(
            "TUI cannot harvest confirmation for a digest it renders; "
            "composing `builder-hitl approve-patch` for your terminal.",
            severity="warning",
        )
        self.push_screen(
            CLIPassthroughScreen(prefix_context="uv run builder-hitl approve-patch"),
            self._show_composed_command,
        )

    def action_reject_hitl(self) -> None:
        if not self.stratum:
            return
        if self.stratum.mode != StratumMode.HITL_GATE and not self.stratum.try_bind_pending_hitl():
            self.notify("No HITL gate open to reject.", severity="warning")
            return
        self.notify(
            "STRATUM is display-only and cannot mutate approval state; "
            "composing `builder-hitl rejection-record` for your terminal.",
            severity="warning",
        )
        self.push_screen(
            CLIPassthroughScreen(prefix_context="uv run builder-hitl rejection-record"),
            self._show_composed_command,
        )

    def action_inspect_hitl(self) -> None:
        if not self.stratum:
            return
        if self.stratum.mode != StratumMode.HITL_GATE:
            # Progressive: I binds pending HITL if present
            if self.stratum.try_bind_pending_hitl():
                return
            self.notify("No pending HITL proposal on disk.", severity="warning")
            return
        artifact = self.stratum._hitl_proposal.get("artifact", {})
        path = self.stratum._hitl_proposal.get("path")
        self.stratum.inspect_artifact(artifact, path=str(path) if path else None)

    def action_diff_hitl(self) -> None:
        self.notify(f"{STRATUM_UNIMPLEMENTED_SURFACES[0]} is not implemented in this surface.")


def run_tui(app: App[Any]) -> int:
    """Run a Textual app and return the exit code it actually reported.

    `App.run()` returning is not evidence the app worked. Textual catches an unhandled exception
    from a message handler, prints the traceback into the terminal, tears the app down, and
    *returns normally* -- recording the failure only in `app.return_code`. Every launch site here
    called `app.run()` and discarded that, so a STRATUM that raised on mount still exited `0`:
    measured, an app whose `on_mount` raises `RuntimeError` exits `0` both under a pty and without
    one, while `return_code` is `1` and `_exception` is the `RuntimeError`.

    That made every launcher report success for a crash, and made an exit code useless as evidence
    to anything scripting the TUI -- which is precisely why no lane could assert that a `builder-*`
    console script boots. Textual's own `return_code` docstring prescribes this exact pattern
    (`my_app.run()` then `sys.exit(my_app.return_code)`); builder-II simply was not following it.

    `None` means the app never exited, which cannot happen once `run()` has returned; it is mapped
    to `0` rather than crashing the launcher on a state Textual says is impossible here.
    """
    app.run()
    return 0 if app.return_code is None else app.return_code
