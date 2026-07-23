"""Active Stratum — morphing center instrument panel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from builder_ii.tui.projections.agents import (
    compose_assign_command,
    compose_deepagents_commands,
    project_agent_roster,
)
from builder_ii.tui.projections.codevault import project_code_vault
from builder_ii.tui.projections.gates import project_hitl_surface, project_third_door
from builder_ii.tui.projections.models import project_model_matrix
from builder_ii.tui.projections.operator import chain_validity_display, project_operator_dashboard
from builder_ii.tui.projections.orchestration import project_orchestration
from builder_ii.tui.projections.render import bold_themed, kv, rule, section_title, status_glyph, themed
from builder_ii.tui.projections.workflow import project_workflow
from builder_ii.tui.widgets.masterpiece import EpistemicMatrix, ThirdDoorGate


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
    CODE_VAULT = "code_vault"
    ORCHESTRATION = "orchestration"
    HELP = "help"
    GUIDE = "guide"


class ActiveStratum(Vertical):
    """Morphing center panel of STRATUM."""

    mode = reactive(StratumMode.IDLE)

    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="stratum-center", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._content: RichLog | None = None
        self._title_bar: Static | None = None
        self._chain_bar: Static | None = None
        self._epistemic_matrix: EpistemicMatrix | None = None
        self._third_door: ThirdDoorGate | None = None

        self._platform_info: dict[str, str] = {}
        self._hitl_proposal: dict[str, Any] = {}
        self._inspected_artifact: dict[str, Any] = {}
        self._inspected_path: str | None = None
        self._chain_digest = "—"
        self._authority_granted: bool | None = None
        self._target = "generic"
        self._help_page = 0  # 0=keymap 1=walkthrough 2=boundaries
        self._repo_root: Path | None = None

    def compose(self) -> ComposeResult:
        self._title_bar = Static("OPERATOR", id="stratum-title-bar")
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

        self._chain_bar = Static("", id="stratum-chain-bar")
        yield self._chain_bar

    def on_mount(self) -> None:
        self._render_current_mode()

    def watch_mode(self, new_mode: str) -> None:
        self._render_current_mode()

    def _write(self, text: str) -> None:
        if self._content is not None:
            self._content.write(text)

    def _render_current_mode(self) -> None:
        if self._content is None or self._epistemic_matrix is None or self._third_door is None:
            return

        self._content.clear()
        self._epistemic_matrix.display = False
        self._third_door.display = False

        renderers = {
            StratumMode.IDLE: self._render_idle,
            StratumMode.HITL_GATE: self._render_hitl_gate,
            StratumMode.ARTIFACT_INSPECT: self._render_artifact_inspect,
            StratumMode.POSTFLIGHT: self._render_postflight,
            StratumMode.PROMOTION: self._render_promotion,
            StratumMode.GOOSE_LIVE: self._render_goose_live,
            StratumMode.PREPARE: self._render_prepare,
            StratumMode.MEMORY_BROWSE: self._render_memory_browse,
            StratumMode.MODEL_MATRIX: self._render_model_matrix,
            StratumMode.AGENT_PROFILES: self._render_agent_profiles,
            StratumMode.PLATFORM_AUDIT: self._render_platform_audit,
            StratumMode.WORKFLOW: self._render_workflow,
            StratumMode.QUALITY_GATES: self._render_quality_gates,
            StratumMode.TOOLING_HEALTH: self._render_tooling_health,
            StratumMode.CODE_VAULT: self._render_code_vault,
            StratumMode.ORCHESTRATION: self._render_orchestration,
            StratumMode.HELP: self._render_help,
            StratumMode.GUIDE: self._render_guide,
        }
        renderer = renderers.get(self.mode)
        if renderer:
            renderer()

        if self.mode == StratumMode.IDLE:
            self._epistemic_matrix.display = True
        if self.mode == StratumMode.HITL_GATE:
            self._third_door.display = True
            door = project_third_door(self.artifacts_dir)
            self._third_door.set_view(door)

        self._update_title_bar()
        self._update_chain_bar()

    def _update_title_bar(self) -> None:
        if self._title_bar is None:
            return
        labels = {
            StratumMode.IDLE: "OPERATOR",
            StratumMode.PREPARE: "PREPARE",
            StratumMode.HITL_GATE: "HITL GATE",
            StratumMode.GOOSE_LIVE: "GOOSE",
            StratumMode.POSTFLIGHT: "POSTFLIGHT",
            StratumMode.PROMOTION: "PROMOTION",
            StratumMode.ARTIFACT_INSPECT: "INSPECT",
            StratumMode.MEMORY_BROWSE: "MEMORY",
            StratumMode.MODEL_MATRIX: "MODELS",
            StratumMode.AGENT_PROFILES: "AGENTS",
            StratumMode.PLATFORM_AUDIT: "AUDIT",
            StratumMode.WORKFLOW: "WORKFLOW",
            StratumMode.QUALITY_GATES: "GATES",
            StratumMode.TOOLING_HEALTH: "TOOLING",
            StratumMode.CODE_VAULT: "CODEVAULT",
            StratumMode.ORCHESTRATION: "ORCHESTRATION",
            StratumMode.HELP: "HELP",
            StratumMode.GUIDE: "WALKTHROUGH",
        }
        self._title_bar.update(labels.get(self.mode, "STRATUM"))

    def _update_chain_bar(self) -> None:
        if self._chain_bar is None:
            return

        digest_display = "—"
        if self._chain_digest and self._chain_digest != "—":
            # Real digest field only — truncate for bar, never invent.
            digest_display = self._chain_digest[:12] + "…"

        if self._authority_granted is True:
            auth_display = bold_themed("pass", "GRANTED")
            gov_display = bold_themed("fail", "artifact_is_authority = TRUE ⚠")
        elif self._authority_granted is False:
            auth_display = themed("fail", "DENIED")
            gov_display = themed("pass", "artifact_is_authority = FALSE ✓")
        else:
            auth_display = themed("hint", "NOT EVALUATED")
            gov_display = themed("pass", "artifact_is_authority = FALSE ✓")

        self._chain_bar.update(
            f"  {themed('dim', 'DIGEST')}  {themed('hint', digest_display)}     "
            f"{themed('dim', 'AUTH')}  {auth_display}     "
            f"{themed('dim', 'GOV')}  {gov_display}"
        )

    # ── Renderers ────────────────────────────────────────────────────

    def _render_idle(self) -> None:
        info = self._platform_info
        dash = project_operator_dashboard(
            artifacts_dir=self.artifacts_dir,
            target=info.get("target") or self._target,
            model=info.get("model", "—"),
            backend=info.get("backend", "—"),
            session=info.get("session", "idle"),
        )

        if self._epistemic_matrix is not None:
            self._epistemic_matrix.apply_epistemic(dash.epistemic)

        valid_text, valid_token = chain_validity_display(dash.chain_valid)
        ledger = themed("pass", "ACTIVE") if dash.ledger_active else themed("warn", "INACTIVE")

        lines = [
            section_title("SYSTEM"),
            kv("Platform", dash.platform),
            kv("Target", dash.target, value_role="accent"),
            kv("Model", dash.model, value_role="pass"),
            kv("Backend", dash.backend),
            kv("Session", dash.session, value_role="hint"),
            "",
            section_title("PIPELINE"),
            kv("Artifacts", str(dash.chain_length)),
            kv("Chain valid", themed(valid_token, valid_text)),
            kv("Memory", str(dash.memory_atoms)),
            kv("Ledger", ledger),
            "",
            section_title("CAPABILITY"),
            f"  {themed('hint', dash.capability_summary)}",
        ]

        if dash.next_action:
            lines.extend(
                [
                    "",
                    section_title("NEXT", "warn"),
                    kv("Capability", dash.next_action.capability, value_role="active"),
                    kv("State", dash.next_action.state, value_role="warn"),
                    f"  {themed('hint', dash.next_action.reason[:120])}",
                ]
            )
            if dash.next_action.safe_command:
                lines.append(kv("Compose", dash.next_action.safe_command, value_role="pass"))
                lines.append(f"  {themed('dim', 'Press N to prefill Command Composer')}")

        lines.extend(
            [
                "",
                rule(),
                f"  {bold_themed('active', 'P')}repare  "
                f"{bold_themed('active', 'V')}alidate  "
                f"{bold_themed('active', 'G')}oose  "
                f"{bold_themed('active', 'N')}ext",
                f"  {bold_themed('active', '?')}palette "
                f"{bold_themed('active', '~')}compose  "
                f"{bold_themed('active', 'O')}models "
                f"{bold_themed('active', 'U')}agents",
                f"  {themed('hint', 'planned ≠ executed ≠ verified ≠ promoted')}",
            ]
        )
        for w in dash.warnings[:3]:
            lines.append(f"  {themed('warn', '⚠')} {themed('hint', w[:80])}")

        if dash.chain_length == 0:
            lines.extend(
                [
                    "",
                    section_title("FIRST SESSION?", "warn"),
                    f"  {themed('hint', 'No artifacts in this tree .builder/artifacts yet.')}",
                    f"  {bold_themed('active', '0')} walkthrough  "
                    f"{bold_themed('active', 'H')} help  "
                    f"{bold_themed('active', 'P')} prepare  "
                    f"{bold_themed('active', 'O')} models  "
                    f"{bold_themed('active', 'U')} agents",
                    f"  {bold_themed('active', 'W')} recipes/goose  "
                    f"{bold_themed('active', 'Y')} orch  "
                    f"{bold_themed('active', 'B')} vault  "
                    f"{bold_themed('active', 'C')} audit",
                    f"  {themed('dim', 'cmd: uv run builder-session prepare-package generic -o .builder/artifacts')}",
                    f"  {themed('dim', 'STRATUM reads the project you launched from — not another clone.')}",
                ]
            )

        self._write("\n".join(lines))

    def _render_hitl_gate(self) -> None:
        proposal = self._hitl_proposal
        digest = proposal.get("digest") or "—"
        if not isinstance(digest, str) or not digest:
            digest = "—"

        lines = [
            section_title("HITL EXECUTION REQUEST", "warn"),
            rule(),
            kv("Command", str(proposal.get("command", "—")), value_role="active"),
            kv("Tier", str(proposal.get("tier", "—")), value_role="accent"),
            kv("Authority", str(proposal.get("authority", "—")), value_role="warn"),
            kv("Effects", str(proposal.get("effects", "—"))),
            kv("Digest", str(digest), value_role="hint"),
        ]
        path = proposal.get("path")
        if path:
            lines.append(kv("Path", str(path), value_role="hint"))

        artifact_data = proposal.get("artifact", {})
        if artifact_data:
            preview = json.dumps(artifact_data, indent=2)[:500]
            lines.extend(["", section_title("ARTIFACT PREVIEW", "hint"), themed("hint", preview)])

        lines.extend(
            [
                "",
                rule(),
                f"  {bold_themed('pass', 'A')} compose approve   "
                f"{bold_themed('fail', 'R')} compose reject",
                f"  {bold_themed('active', 'I')} inspect payload   "
                f"{bold_themed('accent', 'D')} diff (unimplemented)",
                f"  {themed('hint', 'STRATUM does not harvest confirmation — run the composed CLI')}",
            ]
        )
        self._write("\n".join(lines))

    def _render_artifact_inspect(self) -> None:
        if not self._inspected_artifact:
            self._write(themed("dim", "No artifact selected. Use spine ↑↓ then Space, or pin a stage."))
            return

        data = self._inspected_artifact
        kind = str(data.get("kind", "—"))

        breadcrumb = f"  {themed('dim', 'STRATUM')} {themed('hint', '›')} {themed('dim', 'INSPECT')} {themed('hint', '›')} {bold_themed('active', kind)}"

        lines = [
            breadcrumb,
            "",
            section_title("ARTIFACT"),
            kv("Kind", kind, value_role="active"),
        ]
        if self._inspected_path:
            lines.append(kv("Path", self._inspected_path, value_role="hint"))

        # Surface real digest fields only, labeled as artifact fields (not chain digest).
        for key in ("digest", "content_digest", "sha256", "artifact_digest"):
            val = data.get(key)
            if isinstance(val, str) and val:
                lines.append(kv(f"Field:{key}", val[:64], value_role="hint"))
                break

        gov = data.get("governance")
        if isinstance(gov, dict):
            lines.append(kv("Authority", str(gov.get("artifact_is_authority", "—")), value_role="warn"))

        errors = data.get("errors") or []
        if errors:
            lines.append(kv("Errors", str(len(errors)), value_role="fail"))

        lines.extend(["", section_title("DATA"), ""])
        self._write("\n".join(lines))
        if self._content is not None:
            rendered = json.dumps(data, indent=2)
            self._content.write(Syntax(rendered, "json", theme="monokai", line_numbers=False))

    def _render_postflight(self) -> None:
        lines = [section_title("POSTFLIGHT EVIDENCE"), rule()]
        found = False
        if self.artifacts_dir:
            for search in (self.artifacts_dir / "postflight", self.artifacts_dir):
                if not search.exists():
                    continue
                for path in sorted(search.glob("*.json")):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue
                    kind = str(data.get("kind", ""))
                    if "postflight" not in kind and search == self.artifacts_dir:
                        continue
                    found = True
                    status = str(data.get("status", data.get("result", "present")))
                    name = str(data.get("name", path.stem))
                    if status.lower() in ("pass", "passed", "ok"):
                        glyph = status_glyph("pass")
                    elif status.lower() in ("fail", "failed", "error"):
                        glyph = status_glyph("failed")
                    else:
                        glyph = status_glyph("pending")
                    lines.append(f"  {glyph}  {themed('bold', name)}  {themed('hint', status)}")
        if not found:
            lines.append(themed("dim", "  No postflight evidence on disk."))
            lines.append(themed("hint", "  Run governed verification to emit records."))
        self._write("\n".join(lines))

    def _render_promotion(self) -> None:
        lines = [
            section_title("PROMOTION READINESS"),
            rule(),
            themed("hint", "  Read-only projection — no promote action from STRATUM."),
            "",
        ]
        found = False
        if self.artifacts_dir and self.artifacts_dir.exists():
            for path in sorted(self.artifacts_dir.rglob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                kind = str(data.get("kind", ""))
                if "promotion" not in kind:
                    continue
                found = True
                state = str(data.get("state") or data.get("readiness_state") or data.get("status") or "present")
                lines.append(f"  {status_glyph('pending')}  {themed('bold', path.name)}")
                lines.append(f"      {themed('hint', kind)}  {themed('warn', state)}")
        if not found:
            lines.append(themed("dim", "  No promotion readiness artifacts found."))
            lines.append(kv("Compose", "builder-promote readiness …", value_role="pass"))
        door = project_third_door(self.artifacts_dir)
        lines.extend(["", f"  {themed('hint', f'Third Door source: {door.source}')}"])
        self._write("\n".join(lines))
        if self._third_door is not None:
            self._third_door.display = True
            self._third_door.set_view(door)

    def _render_goose_live(self) -> None:
        self._write(
            "\n".join(
                [
                    section_title("GOOSE", "pass"),
                    rule(),
                    themed("hint", "  STRATUM does not stream model output."),
                    themed("hint", "  G suspends and hands the terminal to builder-goose start-readonly."),
                    "",
                    kv("Compose", "builder-goose start-readonly <manifest>", value_role="pass"),
                ]
            )
        )

    def _render_prepare(self) -> None:
        self._write(
            "\n".join(
                [
                    section_title("PREPARE PACKAGE"),
                    rule(),
                    themed("hint", "  Collect session choices, then compose the governed CLI."),
                    themed("hint", "  STRATUM does not write session artifacts."),
                    "",
                    kv("Compose", "builder-session prepare-package", value_role="pass"),
                    f"  {themed('dim', 'Press P to open the session configurator')}",
                ]
            )
        )

    def _render_memory_browse(self) -> None:
        lines = [section_title("MEMORY ATOMS", "accent"), rule()]
        atoms: list[dict[str, Any]] = []
        if self.artifacts_dir:
            memory_dir = self.artifacts_dir / "memory"
            if memory_dir.exists():
                for path in sorted(memory_dir.glob("*.json")):
                    try:
                        atoms.append(json.loads(path.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError):
                        continue
        if not atoms:
            lines.append(themed("dim", "  No memory atoms found."))
        for atom in atoms[:40]:
            atom_type = str(atom.get("type", "unknown"))
            content = str(atom.get("content", ""))[:48]
            score = atom.get("relevance_score", 0.0)
            pin = "◆" if atom.get("pinned") else "·"
            try:
                score_s = f"{float(score):.2f}"
            except (TypeError, ValueError):
                score_s = "—"
            lines.append(
                f"  {themed('accent', pin)} {themed('accent', f'{atom_type:<12}')} "
                f"{themed('warn', score_s)}  {themed('hint', content)}"
            )
        self._write("\n".join(lines))

    def _render_model_matrix(self) -> None:
        view = project_model_matrix()
        loc = view.local
        lines = [
            section_title("MODEL REGISTRY", "pass"),
            kv("State", view.registry_state, value_role="hint"),
            kv("Backends", " · ".join(view.backends) if view.backends else "—", value_role="active"),
            "",
            section_title("LOCAL CONFIG (.env)", "warn"),
            kv("Backend", loc.backend, value_role="active"),
            kv("Alias", loc.alias, value_role="pass"),
            kv("Tier", loc.tier),
            kv("Base URL", loc.base_url, value_role="hint"),
            kv("Temp", loc.temperature, value_role="hint"),
            f"  {themed('dim', loc.note)}",
            rule(),
        ]
        if view.error:
            lines.append(themed("fail", f"  {view.error}"))

        by_backend: dict[str, list] = {}
        for row in view.rows:
            by_backend.setdefault(row.endpoint_kind, []).append(row)

        for backend, rows in by_backend.items():
            lines.append(f"  {bold_themed('active', backend)}")
            for row in rows:
                mark = themed("pass", "●") if row.enabled else themed("dim", "○")
                name = f"{row.name[:36]:<36}"
                alias = f"{row.alias[:14]:<14}"
                ctx = f"{row.context_window:>6}"
                active_mark = themed("warn", " ◂") if row.alias == loc.alias and loc.alias != "—" else ""
                lines.append(
                    f"    {mark} {themed('bold', name)} "
                    f"{themed('warn', alias)} "
                    f"{themed('hint', ctx)}  "
                    f"{themed('accent', row.cost_class)}{active_mark}"
                )
            lines.append("")

        if view.rules:
            lines.append(section_title("ROUTING RULES", "accent"))
            for rule_v in view.rules[:12]:
                pref = ", ".join(rule_v.preferred[:3]) if rule_v.preferred else "—"
                fb = ", ".join(rule_v.fallback[:2]) if rule_v.fallback else "—"
                lines.append(f"  {themed('active', rule_v.rule_id)}  {themed('bold', rule_v.task_intent)}")
                lines.append(
                    f"    {themed('pass', '→')} {themed('hint', pref)}  "
                    f"{themed('dim', 'fb:')} {themed('hint', fb)}"
                )
                if rule_v.rationale:
                    lines.append(f"    {themed('dim', rule_v.rationale[:72])}")

        lines.extend(
            [
                "",
                section_title("COMPOSE", "hint"),
                f"  {themed('pass', view.compose_models)}",
                f"  {themed('pass', view.compose_policy_render)}",
                f"  {themed('dim', 'uv run builder-model call — only when gateway is permitted; receipts required')}",
                f"  {themed('hint', 'STRATUM never calls a provider. Secrets never appear here.')}",
            ]
        )
        if not view.rows and not view.error:
            lines.append(themed("dim", "  No model clients registered."))
        self._write("\n".join(lines))

    def _render_agent_profiles(self) -> None:
        view = project_agent_roster(target=self._target)
        cmds = compose_deepagents_commands(target=self._target)
        lines = [
            section_title("DEEPAGENTS ROSTER", "accent"),
            kv("Readiness", view.readiness_verdict, value_role="warn"),
            kv("Dependency", view.dependency_state, value_role="hint"),
            kv(
                "Disabled",
                ", ".join(view.disabled_capabilities[:4]) if view.disabled_capabilities else "—",
                value_role="fail",
            ),
            rule(),
        ]
        if view.error:
            lines.append(themed("fail", f"  {view.error}"))

        n = len(view.profiles)
        for i, p in enumerate(view.profiles):
            branch = "└─" if i == n - 1 else "├─"
            cont = "  " if i == n - 1 else "│ "
            lines.append(
                f"  {themed('dim', branch)} {bold_themed('accent', p.name)}  "
                f"{themed('warn', p.authority)}"
            )
            lines.append(f"  {themed('dim', cont)} {themed('hint', p.description[:70])}")
            tools = ", ".join(p.allowed_tools[:6])
            lines.append(f"  {themed('dim', cont)} {themed('pass', 'tools')} {themed('hint', tools)}")
            if p.yaml_path:
                lines.append(f"  {themed('dim', cont)} {themed('dim', p.yaml_path)}")

        if view.required_gates:
            lines.extend(["", section_title("BRIDGE PROMOTION GATES", "hint")])
            for g in view.required_gates:
                lines.append(f"  {themed('dim', '▫')} {themed('hint', g)}")

        lines.extend(
            [
                "",
                section_title("COMPOSE (never dispatches)", "hint"),
                f"  {themed('pass', cmds['forge'])}",
                f"  {themed('pass', cmds['readiness'])}",
                f"  {themed('pass', cmds['policy'])}",
                f"  {themed('pass', cmds['work_plan'])}",
                f"  {themed('dim', compose_assign_command('<profile>', target=self._target))}",
                f"  {themed('hint', 'Press U again for profile multi-select compose picker')}",
            ]
        )
        if not view.profiles and not view.error:
            lines.append(themed("dim", "  No agent profiles loaded."))
        self._write("\n".join(lines))

    def _render_platform_audit(self) -> None:
        lines = [section_title("PLATFORM AUDIT"), rule()]
        try:
            from builder_ii.core.platform_completion_audit import capability_rows

            for row in capability_rows():
                state_str = str(row.state)
                state_name = state_str.split(".")[-1] if "." in state_str else state_str
                if "VERIFIED" in state_name:
                    token, glyph = "pass", "✓"
                elif "FOUNDATION" in state_name or "BOUNDARIES" in state_name:
                    token, glyph = "accent", "●"
                elif "NOT_STARTED" in state_name:
                    token, glyph = "dim", "○"
                else:
                    token, glyph = "warn", "▶"
                lines.append(
                    f"  {themed(token, glyph)} {themed('active', f'{row.name:<32}')} "
                    f"{themed(token, state_name)}"
                )
        except Exception as e:
            lines.append(themed("fail", f"  Error: {e}"))
        self._write("\n".join(lines))

    def _render_workflow(self) -> None:
        view = project_workflow(
            artifacts_dir=self.artifacts_dir,
            repo_root=self._repo_root,
            target=self._target,
        )
        lines = [section_title("WORKFLOW · RECIPES · GOOSE", "accent"), rule()]
        if view.error:
            lines.append(themed("fail", f"  {view.error}"))

        if view.session_id:
            lines.append(kv("Session", view.session_id, value_role="active"))
            lines.append(kv("Stage", view.current_stage or "—", value_role="warn"))
            if view.task:
                lines.append(kv("Task", view.task[:60], value_role="hint"))
        else:
            lines.append(themed("dim", "  No workflow session artifact bound."))

        lines.extend(["", section_title("GOOSE MANIFEST")])
        if view.goose:
            token = "pass" if view.goose.valid_enough else "warn"
            lines.append(kv("Path", view.goose.path, value_role="hint"))
            lines.append(kv("Mode", view.goose.mode, value_role=token))
            lines.append(f"  {themed(token, view.goose.note)}")
        else:
            lines.append(themed("dim", "  No .builder/goose/*.json — mint before G."))
            lines.append(f"  {themed('pass', view.compose_manifest)}")

        lines.extend(["", section_title("STAGES")])
        for stage in view.stages:
            if view.current_stage == stage:
                lines.append(f"  {themed('active', '▶')} {bold_themed('active', stage)}")
            else:
                lines.append(f"  {themed('dim', '·')} {themed('hint', stage)}")

        lines.extend(["", section_title("RECIPES (Goose YAML)")])
        if view.recipes:
            for r in view.recipes:
                tag = themed("accent", "sub") if r.is_subrecipe else themed("active", "top")
                lines.append(f"  {tag} {themed('bold', r.name)}  {themed('hint', r.title[:40])}")
                lines.append(f"      {themed('dim', r.path)}")
        else:
            lines.append(themed("dim", "  No recipes/ YAML found in project root."))

        lines.extend(
            [
                "",
                section_title("COMPOSE", "hint"),
                f"  {themed('pass', view.compose_manifest)}",
                f"  {themed('pass', view.compose_start_readonly)}",
                f"  {themed('hint', 'G = start-readonly hand-off only · recipes ≠ authority')}",
                f"  {themed('dim', 'Press Y for orchestration plans / obligations')}",
            ]
        )
        self._write("\n".join(lines))

    def _render_orchestration(self) -> None:
        view = project_orchestration(artifacts_dir=self.artifacts_dir, target=self._target)
        lines = [
            section_title("ORCHESTRATION", "accent"),
            f"  {themed('hint', 'artifact_only / plan_only — no agents constructed here')}",
            rule(),
        ]
        if view.error:
            lines.append(themed("fail", f"  {view.error}"))

        lines.append(section_title("PLANS / ASSIGNMENTS"))
        if view.plans:
            for p in view.plans:
                lines.append(f"  {themed('active', '▸')} {themed('bold', p.kind)}")
                lines.append(f"      {themed('hint', p.summary[:70])}")
                lines.append(f"      {themed('dim', p.path)}")
        else:
            lines.append(themed("dim", "  No orchestration plan artifacts on disk."))

        lines.extend(["", section_title("OBLIGATIONS")])
        if view.obligations:
            for o in view.obligations:
                lines.append(f"  {themed('warn', '●')} {themed('bold', o.kind)}")
                lines.append(f"      {themed('hint', o.summary[:70])}")
        else:
            lines.append(themed("dim", "  No obligation tickets — Law 1: no speech without a ticket."))

        if view.other:
            lines.extend(["", section_title("OTHER ORCH KINDS", "hint")])
            for o in view.other:
                lines.append(f"  {themed('dim', '·')} {o.kind}  {themed('dim', Path(o.path).name)}")

        lines.extend(
            [
                "",
                section_title("COMPOSE", "hint"),
                f"  {themed('pass', view.compose_plan)}",
                f"  {themed('pass', view.compose_lane_policy)}",
                f"  {themed('pass', view.compose_status)}",
                f"  {themed('dim', 'uv run builder-orchestration validate <path>')}",
                f"  {themed('dim', 'uv run builder-orchestration dry-run — passive; no execution')}",
            ]
        )
        self._write("\n".join(lines))

    def _render_code_vault(self) -> None:
        view = project_code_vault(artifacts_dir=self.artifacts_dir, project_root=self._repo_root)
        lines = [
            section_title("CODEVAULT", "pass"),
            f"  {themed('hint', view.note)}",
            kv("Frames/artifacts", str(view.frame_count), value_role="active"),
            rule(),
        ]
        if view.error:
            lines.append(themed("fail", f"  {view.error}"))

        if view.is_installed:
            if view.artifacts:
                for a in view.artifacts:
                    lines.append(f"  {themed('pass', '◆')} {themed('bold', a.label[:32])}")
                    lines.append(f"      {themed('hint', a.kind[:48])}")
                    lines.append(f"      {themed('dim', a.path)}")
            else:
                lines.append(themed("dim", "  No vault/frame JSON found under .builder yet."))
                lines.append(themed("hint", "  prepare-package --code-vault or builder-code-vault frame"))

            lines.extend(
                [
                    "",
                    section_title("COMPOSE", "hint"),
                    f"  {themed('pass', view.compose_status)}",
                    f"  {themed('pass', view.compose_demo)}",
                    f"  {themed('pass', view.compose_frame)}",
                    f"  {themed('dim', 'uv run builder-code-vault validate-demo')}",
                    f"  {themed('hint', 'Exact recall only — refuse ANN/HNSW/cosine narratives')}",
                ]
            )
        self._write("\n".join(lines))

    def _render_quality_gates(self) -> None:
        lines = [section_title("QUALITY GATES", "warn"), rule()]
        target = self._platform_info.get("target") or self._target or "generic"
        try:
            from builder_ii.lifecycle.candidate.verification_profiles import default_profile_for_target
            from builder_ii.lifecycle.setup.target_profiles import target_names
            from builder_ii.validation.quality_gates import create_quality_gate_artifact

            t = target if target in target_names() else "generic"
            try:
                profile = default_profile_for_target(t).name  # type: ignore[arg-type]
            except Exception:
                profile = "generic_basic"
            try:
                gate = create_quality_gate_artifact(
                    target=t,  # type: ignore[arg-type]
                    verification_profile=profile,  # type: ignore[arg-type]
                    task="stratum-inspect",
                )
            except Exception:
                gate = create_quality_gate_artifact(
                    target="generic",
                    verification_profile="generic_basic",
                    task="stratum-inspect",
                )
            lines.append(kv("Target", str(gate.get("target", t)), value_role="active"))
            lines.append("")
            lines.append(section_title("REQUIRED EVIDENCE", "pass"))
            for req in gate.get("required_evidence") or []:
                lines.append(f"  {themed('pass', '·')} {themed('bold', str(req))}")
            lines.append("")
            lines.append(section_title("MERGE BLOCKERS", "fail"))
            for blk in gate.get("merge_blockers") or []:
                lines.append(f"  {themed('fail', '·')} {themed('bold', str(blk))}")
            lines.append("")
            lines.append(section_title("ROLLBACK", "hint"))
            for rb in gate.get("rollback_requirements") or []:
                lines.append(f"  {themed('hint', '·')} {themed('hint', str(rb))}")
            lines.append("")
            lines.append(themed("hint", "  Gate artifact is advisory — does not execute commands."))
        except Exception as e:
            lines.append(themed("fail", f"  Error: {e}"))
        self._write("\n".join(lines))

    def _render_tooling_health(self) -> None:
        lines = [section_title("TOOLING HEALTH", "pass"), rule()]
        try:
            from builder_ii.core.tool_registry import check_tools

            for chk in check_tools():
                if chk.installed:
                    glyph = themed("pass", "✓")
                    msg = themed("hint", chk.version_string or "installed")
                else:
                    glyph = themed("fail", "✗")
                    msg = themed("fail", f"MISSING — {chk.tool.install_instructions}")
                lines.append(f"  {glyph} {themed('active', f'{chk.tool.name:<16}')} {msg}")
        except Exception as e:
            lines.append(themed("fail", f"  Error: {e}"))
        self._write("\n".join(lines))

    def _render_help(self) -> None:
        from builder_ii.lifecycle.setup.stratum_guide import help_boundary_lines, help_keymap_lines, walkthrough_lines

        pages = (
            ("KEYMAP", help_keymap_lines()),
            ("WALKTHROUGH", walkthrough_lines(include_opt_out_hint=True)),
            ("BOUNDARIES", help_boundary_lines()),
        )
        page = self._help_page % len(pages)
        title, body = pages[page]
        lines = [
            section_title(f"HELP · {title}", "warn"),
            f"  {themed('hint', f'page {page + 1}/{len(pages)}  ·  [ ] next page  ·  0 walkthrough  ·  ESC idle')}",
            rule(),
        ]
        for raw in body:
            if not raw:
                lines.append("")
            elif raw.startswith("   cmd:") or "uv run " in raw or raw.strip().startswith("cmd:"):
                lines.append(themed("pass", raw if raw.startswith(" ") else f"  {raw}"))
            elif raw.startswith("  "):
                lines.append(themed("hint", raw))
            elif raw.isupper() and any(c.isalpha() for c in raw):
                lines.append(bold_themed("accent", raw))
            else:
                lines.append(themed("bold", raw))
        self._write("\n".join(lines))

    def _render_guide(self) -> None:
        from builder_ii.lifecycle.setup.stratum_guide import walkthrough_lines

        lines = [
            section_title("FIRST SESSION WALKTHROUGH", "warn"),
            f"  {themed('hint', 'X dismiss auto-open  ·  ESC idle  ·  H multi-page help')}",
            rule(),
        ]
        for raw in walkthrough_lines(include_opt_out_hint=True):
            if not raw:
                lines.append("")
            elif raw.startswith("   cmd:"):
                lines.append(themed("pass", raw))
            elif raw.startswith("   "):
                lines.append(themed("hint", raw))
            elif len(raw) > 2 and raw[0].isdigit() and raw[1] == ".":
                lines.append(bold_themed("active", raw))
            elif raw.isupper() and any(c.isalpha() for c in raw):
                lines.append(bold_themed("accent", raw))
            else:
                lines.append(themed("bold", raw))
        self._write("\n".join(lines))

    def cycle_help_page(self, delta: int = 1) -> None:
        self._help_page = (self._help_page + delta) % 3
        if self.mode == StratumMode.HELP:
            self._render_current_mode()

    # ── Public API ───────────────────────────────────────────────────

    def set_platform_info(self, info: dict[str, str]) -> None:
        self._platform_info = info
        if info.get("target"):
            self._target = info["target"]
        if self.mode == StratumMode.IDLE:
            self._render_current_mode()

    def set_repo_root(self, root: Path | None) -> None:
        self._repo_root = root

    def show_hitl_gate(self, proposal: dict[str, Any]) -> None:
        self._hitl_proposal = proposal
        self.mode = StratumMode.HITL_GATE

    def try_bind_pending_hitl(self) -> bool:
        """If a pending HITL artifact exists, open gate mode. Returns True when bound."""
        view = project_hitl_surface(self.artifacts_dir)
        if view is None:
            return False
        self.show_hitl_gate(
            {
                "command": view.command,
                "tier": view.tier,
                "authority": view.authority,
                "effects": view.effects,
                "digest": view.digest,
                "artifact": view.artifact,
                "path": view.path,
            }
        )
        return True

    def inspect_artifact(self, artifact: dict[str, Any], *, path: str | None = None) -> None:
        self._inspected_artifact = artifact
        self._inspected_path = path
        self.mode = StratumMode.ARTIFACT_INSPECT

    def set_chain_digest(self, digest: str) -> None:
        self._chain_digest = digest if digest else "—"
        self._update_chain_bar()

    def set_authority_granted(self, granted: bool | None) -> None:
        self._authority_granted = granted
        self._update_chain_bar()

    def append_goose_output(self, text: str) -> None:
        if self._content and self.mode == StratumMode.GOOSE_LIVE:
            self._content.write(text)
