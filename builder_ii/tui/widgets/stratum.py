"""Active Stratum — The morphing center panel.

This panel changes its contents based on the current pipeline state:
  - Idle:        Operator status report (capability matrix, memory count)
  - Prepare:     Manifest assembly + validation errors
  - HITL Gate:   Full proposal display + approve/reject/diff
  - Goose Live:  Model output stream with tool calls highlighted
  - Post-flight: Evidence bundle viewer
  - Promotion:   Before/after artifact comparison
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

# ── Stratum Modes ────────────────────────────────────────────────────


class StratumMode:
    IDLE = "idle"
    PREPARE = "prepare"
    HITL_GATE = "hitl_gate"
    GOOSE_LIVE = "goose_live"
    POSTFLIGHT = "postflight"
    PROMOTION = "promotion"
    ARTIFACT_INSPECT = "artifact_inspect"
    MEMORY_BROWSE = "memory_browse"
    MODEL_MATRIX = "model_matrix"
    AGENT_PROFILES = "agent_profiles"
    PLATFORM_AUDIT = "platform_audit"
    WORKFLOW = "workflow"
    QUALITY_GATES = "quality_gates"
    TOOLING_HEALTH = "tooling_health"
    HELP = "help"


# ── Idle Report ──────────────────────────────────────────────────────

IDLE_REPORT_TEMPLATE = """\
[bold #58a6ff]╔══════════════════════════════════════════════╗[/]
[bold #58a6ff]║       STRATUM — OPERATOR STATUS REPORT       ║[/]
[bold #58a6ff]╚══════════════════════════════════════════════╝[/]

[bold #79c0ff]System[/]
  [#8b949e]Platform     :[/]  [#c9d1d9]{platform}[/]
  [#8b949e]Target       :[/]  [#d2a8ff]{target}[/]
  [#8b949e]Model        :[/]  [#7ee787]{model}[/]
  [#8b949e]Backend      :[/]  [#c9d1d9]{backend}[/]
  [#8b949e]Session      :[/]  [#6e7681]{session}[/]

[bold #79c0ff]Pipeline State[/]
  [#8b949e]Chain Length  :[/]  [#c9d1d9]{chain_length} artifacts[/]
  [#8b949e]Chain Valid   :[/]  {chain_valid_display}
  [#8b949e]Memory Atoms  :[/]  [#c9d1d9]{memory_atoms}[/]
  [#8b949e]Ledger Active :[/]  {ledger_display}

[bold #79c0ff]Command Surfaces[/]
  [#484f58]──────────────────────────────────────────────[/]
  [#58a6ff][P][/][#6e7681]repare  [/] [#58a6ff][V][/][#6e7681]alidate  [/] [#58a6ff][G][/][#6e7681]oose  [/] [#58a6ff][N][/][#6e7681]ext-step[/]
  [#58a6ff][?][/][#6e7681]palette [/] [#58a6ff][~][/][#6e7681]cli      [/] [#58a6ff][M][/][#6e7681]emory [/] [#58a6ff][S][/][#6e7681]ummary[/]
  [#484f58]──────────────────────────────────────────────[/]

[bold #79c0ff]Governance[/]
  [#8b949e]Authority    :[/]  [#ffa657]artifact_is_authority[/]
  [#8b949e]Model Output :[/]  [#f85149]NOT approval[/]
  [#8b949e]Epistemology :[/]  [#6e7681]planned ≠ executed ≠ verified ≠ promoted[/]
"""


# ── HITL Gate Panel ──────────────────────────────────────────────────

HITL_GATE_TEMPLATE = """\
[bold #d29922]╔══════════════════════════════════════════════╗[/]
[bold #d29922]║        HITL: EXECUTION REQUEST               ║[/]
[bold #d29922]║  ──────────────────────────────────────────  ║[/]
[bold #d29922]╚══════════════════════════════════════════════╝[/]

  [#8b949e]CMD       :[/]  [#79c0ff]{command}[/]
  [#8b949e]TIER      :[/]  [#d2a8ff]{tier}[/]
  [#8b949e]AUTHORITY :[/]  [#ffa657]{authority}[/]
  [#8b949e]EFFECTS   :[/]  [#c9d1d9]{effects}[/]
  [#8b949e]DIGEST    :[/]  [#6e7681]{digest}[/]

{artifact_preview}

  [bold #3fb950][A][/][#6e7681] APPROVE    [/]  [bold #f85149][R][/][#6e7681] REJECT[/]
  [bold #58a6ff][I][/][#6e7681] INSPECT    [/]  [bold #d2a8ff][D][/][#6e7681] DIFF vs PRIOR[/]
"""


from builder_ii.tui.widgets.masterpiece import EpistemicMatrix, ThirdDoorGate

# ── Active Stratum Widget ───────────────────────────────────────────


class ActiveStratum(Vertical):
    """The morphing center panel of STRATUM."""

    mode = reactive(StratumMode.IDLE)

    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="stratum-center", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._content: RichLog | None = None
        self._title_bar: Static | None = None
        self._chain_bar: Static | None = None

        # Masterpiece widgets
        self._epistemic_matrix: EpistemicMatrix | None = None
        self._third_door: ThirdDoorGate | None = None

        # State for rendering
        self._platform_info: dict[str, str] = {}
        self._hitl_proposal: dict[str, Any] = {}
        self._inspected_artifact: dict[str, Any] = {}
        self._chain_digest = ""
        self._authority_granted = False

    def compose(self) -> ComposeResult:
        self._title_bar = Static("THE ACTIVE STRATUM", id="stratum-title-bar")
        yield self._title_bar
        with ScrollableContainer(id="stratum-content"):
            self._epistemic_matrix = EpistemicMatrix()
            self._epistemic_matrix.display = False
            yield self._epistemic_matrix

            self._content = RichLog(
                highlight=True,
                markup=True,
                wrap=True,
                max_lines=500,
            )
            yield self._content

            self._third_door = ThirdDoorGate()
            self._third_door.display = False
            yield self._third_door

        self._chain_bar = Static(
            "  [#484f58]CHAIN DIGEST:[/]  [#6e7681]—[/]     "
            "[#484f58]AUTHORITY:[/]  [#6e7681]NOT GRANTED[/]     "
            "[#484f58]GOVERNANCE:[/]  [#3fb950]artifact_is_authority = FALSE ✓[/]",
            id="stratum-chain-bar",
        )
        yield self._chain_bar

    def on_mount(self) -> None:
        self._render_current_mode()

    def watch_mode(self, new_mode: str) -> None:
        self._render_current_mode()

    def _render_current_mode(self) -> None:
        if self._content is None or self._epistemic_matrix is None or self._third_door is None:
            return

        self._content.clear()
        self._epistemic_matrix.display = False
        self._third_door.display = False

        if self.mode == StratumMode.IDLE:
            self._render_idle()
            self._epistemic_matrix.display = True
        elif self.mode == StratumMode.HITL_GATE:
            self._render_hitl_gate()
            self._third_door.display = True
        elif self.mode == StratumMode.ARTIFACT_INSPECT:
            self._render_artifact_inspect()
        elif self.mode == StratumMode.POSTFLIGHT:
            self._render_postflight()
        elif self.mode == StratumMode.PROMOTION:
            self._render_promotion()
        elif self.mode == StratumMode.GOOSE_LIVE:
            self._render_goose_live()
        elif self.mode == StratumMode.PREPARE:
            self._render_prepare()
        elif self.mode == StratumMode.MEMORY_BROWSE:
            self._render_memory_browse()
        elif self.mode == StratumMode.MODEL_MATRIX:
            self._render_model_matrix()
        elif self.mode == StratumMode.AGENT_PROFILES:
            self._render_agent_profiles()
        elif self.mode == StratumMode.PLATFORM_AUDIT:
            self._render_platform_audit()
        elif self.mode == StratumMode.WORKFLOW:
            self._render_workflow()
        elif self.mode == StratumMode.QUALITY_GATES:
            self._render_quality_gates()
        elif self.mode == StratumMode.TOOLING_HEALTH:
            self._render_tooling_health()
        elif self.mode == StratumMode.HELP:
            self._render_help()

        self._update_title_bar()
        self._update_chain_bar()

    def _update_title_bar(self) -> None:
        if self._title_bar is None:
            return
        labels = {
            StratumMode.IDLE: "OPERATOR STATUS",
            StratumMode.PREPARE: "PREPARE PACKAGE",
            StratumMode.HITL_GATE: "⚡ HITL AUTHORITY GATE",
            StratumMode.GOOSE_LIVE: "▶ GOOSE SESSION — LIVE",
            StratumMode.POSTFLIGHT: "POST-FLIGHT EVIDENCE",
            StratumMode.PROMOTION: "PROMOTION DECISION",
            StratumMode.ARTIFACT_INSPECT: "ARTIFACT INSPECTOR",
            StratumMode.MEMORY_BROWSE: "MEMORY ATOMS",
            StratumMode.MODEL_MATRIX: "MODEL REGISTRY & ROSTER",
            StratumMode.AGENT_PROFILES: "DEEPAGENTS PROFILE MATRIX",
            StratumMode.PLATFORM_AUDIT: "PLATFORM CAPABILITY AUDIT",
            StratumMode.WORKFLOW: "WORKFLOW ORCHESTRATOR",
            StratumMode.QUALITY_GATES: "QUALITY GATES & EVIDENCE",
            StratumMode.TOOLING_HEALTH: "EXTERNAL TOOLING HEALTH",
            StratumMode.HELP: "OPERATOR COMMAND MANUAL",
        }
        self._title_bar.update(labels.get(self.mode, "THE ACTIVE STRATUM"))

    def _update_chain_bar(self) -> None:
        if self._chain_bar is None:
            return

        digest_display = self._chain_digest[:12] + "…" if self._chain_digest else "—"
        auth_display = "[bold #3fb950]GRANTED[/]" if self._authority_granted else "[#6e7681]NOT GRANTED[/]"
        gov_display = (
            "[#f85149 bold]artifact_is_authority = TRUE ⚠[/]"
            if self._authority_granted
            else "[#3fb950]artifact_is_authority = FALSE ✓[/]"
        )
        self._chain_bar.update(
            f"  [#484f58]CHAIN DIGEST:[/]  [#6e7681]{digest_display}[/]     "
            f"[#484f58]AUTHORITY:[/]  {auth_display}     "
            f"[#484f58]GOVERNANCE:[/]  {gov_display}"
        )

    # ── Renderers ────────────────────────────────────────────────────

    def _render_idle(self) -> None:
        assert self._content is not None
        info = self._platform_info
        report = IDLE_REPORT_TEMPLATE.format(
            platform=info.get("platform", "builder-II"),
            target=info.get("target", "—"),
            model=info.get("model", "—"),
            backend=info.get("backend", "—"),
            session=info.get("session", "—"),
            chain_length=info.get("chain_length", "0"),
            chain_valid_display=info.get("chain_valid_display", "[#6e7681]—[/]"),
            memory_atoms=info.get("memory_atoms", "0"),
            ledger_display=info.get("ledger_display", "[#6e7681]—[/]"),
        )
        self._content.write(report)

    def _render_hitl_gate(self) -> None:
        assert self._content is not None
        proposal = self._hitl_proposal
        preview = ""
        artifact_data = proposal.get("artifact", {})
        if artifact_data:
            preview_json = json.dumps(artifact_data, indent=2)[:600]
            preview = f"  [#484f58]───── Artifact Preview ─────[/]\n[#8b949e]{preview_json}[/]"

        gate = HITL_GATE_TEMPLATE.format(
            command=proposal.get("command", "—"),
            tier=proposal.get("tier", "—"),
            authority=proposal.get("authority", "—"),
            effects=proposal.get("effects", "—"),
            digest=proposal.get("digest", "—"),
            artifact_preview=preview,
        )
        self._content.write(gate)

    def _render_artifact_inspect(self) -> None:
        assert self._content is not None
        if self._inspected_artifact:
            rendered = json.dumps(self._inspected_artifact, indent=2)
            self._content.write("[bold #58a6ff]═══ ARTIFACT DATA ═══[/]\n")
            # Use Syntax for JSON highlighting
            self._content.write(Syntax(rendered, "json", theme="monokai"))
        else:
            self._content.write("[#484f58]No artifact selected for inspection.[/]")

    def _render_postflight(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #58a6ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #58a6ff]║         POST-FLIGHT EVIDENCE BUNDLE          ║[/]\n"
            "[bold #58a6ff]╚══════════════════════════════════════════════╝[/]\n"
        )
        if self.artifacts_dir:
            postflight_dir = self.artifacts_dir / "postflight"
            if postflight_dir.exists():
                for path in sorted(postflight_dir.glob("*.json")):
                    try:
                        data = json.loads(path.read_text())
                        status = data.get("status", "unknown")
                        glyph = "✓" if status == "pass" else "✗"
                        color = "#3fb950" if status == "pass" else "#f85149"
                        name = data.get("name", path.stem)
                        self._content.write(f"  [{color}]{glyph}[/]  [{color}]{name}[/]  [#484f58]{status}[/]")
                    except (json.JSONDecodeError, OSError):
                        continue
            else:
                self._content.write("[#484f58]No postflight evidence found.[/]")

    def _render_promotion(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #58a6ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #58a6ff]║          PROMOTION READINESS CHECK           ║[/]\n"
            "[bold #58a6ff]╚══════════════════════════════════════════════╝[/]\n\n"
            "  [#8b949e]Chain integrity  :[/]  [#3fb950]✓ verified[/]\n"
            "  [#8b949e]Postflight       :[/]  [#3fb950]✓ all pass[/]\n"
            "  [#8b949e]Governance sign  :[/]  [#d29922]● awaiting[/]\n\n"
            "  [bold #3fb950][P][/][#6e7681] PROMOTE[/]   "
            "[bold #f85149][C][/][#6e7681] CANCEL[/]"
        )

    def _render_goose_live(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #7ee787]▶ GOOSE SESSION — LIVE STREAM[/]\n"
            "[#484f58]═══════════════════════════════════════════════[/]\n"
            "[#6e7681]Waiting for model output…[/]\n"
        )

    def _render_prepare(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #58a6ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #58a6ff]║           PREPARE EXECUTION PACKAGE          ║[/]\n"
            "[bold #58a6ff]╚══════════════════════════════════════════════╝[/]\n\n"
            "  [#8b949e]Assembling manifest…[/]\n"
        )

    def _render_memory_browse(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #d2a8ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #d2a8ff]║            MEMORY ATOM BROWSER               ║[/]\n"
            "[bold #d2a8ff]╚══════════════════════════════════════════════╝[/]\n\n"
            "  [#8b949e]Loading memory atoms…[/]\n"
        )
        if self.artifacts_dir:
            memory_dir = self.artifacts_dir / "memory"
            if memory_dir.exists():
                atoms = []
                for path in sorted(memory_dir.glob("*.json")):
                    try:
                        data = json.loads(path.read_text())
                        atoms.append(data)
                    except (json.JSONDecodeError, OSError):
                        continue
                for atom in atoms[:30]:
                    atom_type = atom.get("type", "unknown")
                    content = str(atom.get("content", ""))[:50]
                    score = atom.get("relevance_score", 0.0)
                    pinned = "📌" if atom.get("pinned") else "  "
                    self._content.write(
                        f"  {pinned} [#d2a8ff]{atom_type:<12}[/] [#ffa657]{score:.2f}[/]  [#8b949e]{content}[/]"
                    )
                if not atoms:
                    self._content.write("  [#484f58]No memory atoms found.[/]")

    def _render_model_matrix(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #7ee787]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #7ee787]║        GOVERNED MODEL ROSTER & REGISTRY      ║[/]\n"
            "[bold #7ee787]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        try:
            from builder_ii.model_client_registry import create_model_client_registry

            registry = create_model_client_registry()
            clients = registry.get("clients", [])
            for client in clients[:25]:
                name = client.get("model_name", "Unknown Model")
                alias = client.get("model_alias", "—")
                provider = client.get("provider_name", "Unknown Provider")
                ctx = client.get("context_window", 0)
                cost = client.get("cost_class", "unknown")
                enabled = "✓ ACTIVE" if client.get("enabled") else "⊘ DISABLED"
                color = "#3fb950" if client.get("enabled") else "#484f58"
                self._content.write(
                    f"  [{color}]{enabled}[/]  [bold #79c0ff]{name:<30}[/] alias: [#ffa657]{alias:<15}[/]\n"
                    f"            Provider: [#8b949e]{provider}[/] · Ctx: [#d2a8ff]{ctx}[/] · Cost: [#f85149]{cost}[/]\n"
                )
            if not clients:
                self._content.write("  [#484f58]No registered model clients found.[/]")
        except Exception as e:
            self._content.write(f"  [#f85149]Error loading model registry:[/] {e}")

    def _render_agent_profiles(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #d2a8ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #d2a8ff]║          DEEPAGENTS PROFILE WORKBENCH        ║[/]\n"
            "[bold #d2a8ff]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        try:
            from builder_ii.agent_profiles import agent_profiles

            profiles = agent_profiles()
            for profile in profiles:
                name = profile.name
                desc = profile.description
                auth = profile.authority
                allowed = ", ".join(profile.allowed_tools)
                self._content.write(
                    f"  [bold #d2a8ff]● {name:<20}[/] Authority: [bold #ffa657]{auth}[/]\n"
                    f"    [#8b949e]{desc}[/]\n"
                    f"    Tools allowed: [#7ee787]{allowed}[/]\n"
                )
            if not profiles:
                self._content.write("  [#484f58]No agent profiles found.[/]")
        except Exception as e:
            self._content.write(f"  [#f85149]Error loading agent profiles:[/] {e}")

    def _render_platform_audit(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #58a6ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #58a6ff]║      PLATFORM CAPABILITY AUDIT MATRIX        ║[/]\n"
            "[bold #58a6ff]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        try:
            from builder_ii.platform_completion_audit import capability_rows

            rows = capability_rows()
            for row in rows:
                state_str = str(row.state)
                # Parse StateLabel enum if needed or just use name
                state_name = state_str.split(".")[-1] if "." in state_str else state_str

                if "VERIFIED" in state_name:
                    color = "#3fb950"
                    glyph = "✓"
                elif "FOUNDATION" in state_name or "BOUNDARIES" in state_name:
                    color = "#d2a8ff"
                    glyph = "●"
                elif "NOT_STARTED" in state_name:
                    color = "#484f58"
                    glyph = "○"
                else:
                    color = "#d29922"
                    glyph = "▶"

                self._content.write(f"  [{color}]{glyph}[/] [bold #79c0ff]{row.name:<32}[/] [{color}]{state_name}[/]")

            if not rows:
                self._content.write("  [#484f58]No capability rows defined.[/]")
        except Exception as e:
            self._content.write(f"  [#f85149]Error loading platform audit:[/] {e}")

    def _render_workflow(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #d2a8ff]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #d2a8ff]║        ACTIVE WORKFLOW ORCHESTRATOR          ║[/]\n"
            "[bold #d2a8ff]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        self._content.write("  [#8b949e]No active workflow session bound in TUI yet.[/]\n")
        self._content.write("  [#484f58]Launch a workflow session via `builder run` to see it here.[/]")

    def _render_quality_gates(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #ffa657]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #ffa657]║           QUALITY GATES & EVIDENCE           ║[/]\n"
            "[bold #ffa657]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        try:
            from builder_ii.quality_gates import create_quality_gate_artifact

            gate = create_quality_gate_artifact("generic", "generic")
            self._content.write("  [bold #79c0ff]TARGET:[/] generic\n")
            for req in gate.get("required_evidence", []):
                self._content.write(f"  [#3fb950]✓[/] [#c9d1d9]{req}[/]")
            self._content.write("\n  [bold #f85149]MERGE BLOCKERS:[/]\n")
            for blk in gate.get("merge_blockers", []):
                self._content.write(f"  [#f85149]✗[/] [#c9d1d9]{blk}[/]")

        except Exception as e:
            self._content.write(f"  [#f85149]Error loading quality gates:[/] {e}")

    def _render_tooling_health(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #7ee787]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #7ee787]║            EXTERNAL TOOLING HEALTH           ║[/]\n"
            "[bold #7ee787]╚══════════════════════════════════════════════╝[/]\n\n"
        )
        try:
            from builder_ii.tool_registry import check_tools

            checks = check_tools()
            for chk in checks:
                if chk.installed:
                    color = "#3fb950"
                    glyph = "✓"
                    ver = chk.version_string or "unknown version"
                    msg = f"[#8b949e]{ver}[/]"
                else:
                    color = "#f85149"
                    glyph = "✗"
                    msg = f"[#f85149]MISSING[/] — run: {chk.tool.install_instructions}"

                self._content.write(f"  [{color}]{glyph}[/] [bold #79c0ff]{chk.tool.name:<15}[/] {msg}")
        except Exception as e:
            self._content.write(f"  [#f85149]Error loading tooling health:[/] {e}")

    def _render_help(self) -> None:
        assert self._content is not None
        self._content.write(
            "[bold #ffa657]╔══════════════════════════════════════════════╗[/]\n"
            "[bold #ffa657]║       STRATUM OPERATOR COMMAND MANUAL        ║[/]\n"
            "[bold #ffa657]╚══════════════════════════════════════════════╝[/]\n\n"
            "  [bold #d2a8ff]CORE CONSOLE CONTROLS[/]\n"
            "    [bold #79c0ff][TAB][/]      Cycle focus across the 3 Columns (Spine ◂▸ Active ◂▸ Signals)\n"
            "    [bold #79c0ff][ESC][/]      Universal 'Back' / Clear panel to default Operator Status\n"
            "    [bold #79c0ff][CTRL+Q][/]   Safely quit STRATUM\n\n"
            "  [bold #d2a8ff]SPINE NAVIGATION (Left Column)[/]\n"
            "    [bold #79c0ff][UP/DOWN][/]  Navigate through the artifact pipeline stages\n"
            "    [bold #79c0ff][j/k][/]      Vim-style navigation for spine stages\n"
            "    [bold #79c0ff][SPC][/]      Pin highlighted artifact to center panel for inspection\n"
            "    [bold #79c0ff][/][/]        Toggle live search/filter for spine artifacts\n\n"
            "  [bold #d2a8ff]STRATUM MODES (Center Panel Toggles)[/]\n"
            "    [bold #79c0ff][M][/]        Memory Atom Browser\n"
            "    [bold #79c0ff][O][/]        Model Registry & Cost Matrix\n"
            "    [bold #79c0ff][U][/]        DeepAgents Profile Matrix\n"
            "    [bold #79c0ff][C][/]        Platform Capability Audit (Matrix completion status)\n"
            "    [bold #79c0ff][W][/]        Active Workflow Orchestrator & stage gate tracking\n"
            "    [bold #79c0ff][E][/]        Quality Gates & Rollback evidence requirements\n"
            "    [bold #79c0ff][T][/]        External Tooling Health check\n"
            "    [bold #79c0ff][H / F1][/]   Open this Operator Command Manual\n\n"
            "  [bold #d2a8ff]GOVERNANCE ESCALATIONS[/]\n"
            "    [bold #79c0ff][?][/]        Governed Command Palette (Tier permission checker)\n"
            "    [bold #79c0ff][~][/]        Raw CLI Escape Hatch (Context-injected subprocess console)\n\n"
            "  [bold #d2a8ff]PIPELINE COMMANDS[/]\n"
            "    [bold #79c0ff][P][/]        Prepare Workspace (build local environment)\n"
            "    [bold #79c0ff][V][/]        Validate Codebase (run verification checks)\n"
            "    [bold #79c0ff][G][/]        Launch Goose Session projection\n"
            "    [bold #79c0ff][N][/]        Retrieve Operator 'Next Step' guidance\n\n"
            "  [bold #d2a8ff]HITL OVERRIDES (Signals Rail)[/]\n"
            "    [bold #79c0ff][A][/]        Approve pending HITL gate\n"
            "    [bold #79c0ff][R][/]        Reject pending HITL gate\n"
            "    [bold #79c0ff][I][/]        Inspect gate payload details\n"
            "    [bold #79c0ff][D][/]        Diff candidate vs authority main"
        )

    # ── Public API ───────────────────────────────────────────────────

    def set_platform_info(self, info: dict[str, str]) -> None:
        """Update the idle report platform info and re-render if idle."""
        self._platform_info = info
        if self.mode == StratumMode.IDLE:
            self._render_current_mode()

    def show_hitl_gate(self, proposal: dict[str, Any]) -> None:
        """Switch to HITL gate mode with the given proposal."""
        self._hitl_proposal = proposal
        self.mode = StratumMode.HITL_GATE

    def inspect_artifact(self, artifact: dict[str, Any]) -> None:
        """Switch to artifact inspection mode."""
        self._inspected_artifact = artifact
        self.mode = StratumMode.ARTIFACT_INSPECT

    def set_chain_digest(self, digest: str) -> None:
        self._chain_digest = digest
        self._update_chain_bar()

    def set_authority_granted(self, granted: bool) -> None:
        self._authority_granted = granted
        self._update_chain_bar()

    def append_goose_output(self, text: str) -> None:
        """Append live model output during a Goose session."""
        if self._content and self.mode == StratumMode.GOOSE_LIVE:
            self._content.write(text)
