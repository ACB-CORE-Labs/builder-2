"""Masterpiece Widgets — Visualizing the Builder-II Engineering Pillars.

1. EpistemicMatrix (Semantic Rigor)
   planned → executed → verified → promoted. Digests only when injected;
   default absence is "—", never a fabricated hash fragment.

2. MechanicalSympathyHud (Mechanical Sympathy)
   Low-overhead HUD for unified memory pressure.

3. ThirdDoorGate (The Third Door)
   Eight authority constraints; unevaluated slots stay open, never painted green.
"""

from __future__ import annotations

from typing import Any

from textual.reactive import reactive
from textual.widgets import Static

from builder_ii.tui.projections.gates import (
    THIRD_DOOR_CONSTRAINTS,
    THIRD_DOOR_INCOMPLETE,
    THIRD_DOOR_LOCKED,
    THIRD_DOOR_UNASSESSED,
    THIRD_DOOR_UNLOCKED,
    ThirdDoorView,
    unassessed_third_door,
)
from builder_ii.tui.projections.render import bold_themed, epistemic_node, themed


class EpistemicMatrix(Static):
    """Proof chain visualization — not a progress bar.

    Defaults are honest: all pending, all digests absent.
    """

    state_planned = reactive("pending")
    state_executed = reactive("pending")
    state_verified = reactive("pending")
    state_promoted = reactive("pending")

    digest_planned = reactive("—")
    digest_executed = reactive("—")
    digest_verified = reactive("—")
    digest_promoted = reactive("—")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="epistemic-matrix", **kwargs)

    def apply_epistemic(self, data: dict[str, str]) -> None:
        """Bind states from a projection. Digests default to absence."""
        self.state_planned = data.get("state_planned", "pending")
        self.state_executed = data.get("state_executed", "pending")
        self.state_verified = data.get("state_verified", "pending")
        self.state_promoted = data.get("state_promoted", "pending")
        self.digest_planned = data.get("digest_planned") or "—"
        self.digest_executed = data.get("digest_executed") or "—"
        self.digest_verified = data.get("digest_verified") or "—"
        self.digest_promoted = data.get("digest_promoted") or "—"

    def render(self) -> str:
        nodes = [
            ("PLANNED", self.state_planned, self.digest_planned),
            ("EXECUTED", self.state_executed, self.digest_executed),
            ("VERIFIED", self.state_verified, self.digest_verified),
            ("PROMOTED", self.state_promoted, self.digest_promoted),
        ]

        out = (
            f"{bold_themed('accent', 'EPISTEMIC MATRIX')}  "
            f"{themed('hint', 'planned ≠ executed ≠ verified ≠ promoted')}\n"
        )

        label_parts: list[str] = []
        digest_parts: list[str] = []
        link_parts: list[str] = []

        for idx, (label, state, digest) in enumerate(nodes):
            lbl, dig = epistemic_node(label, state, digest)
            label_parts.append(lbl)
            digest_parts.append(dig)
            if idx < len(nodes) - 1:
                next_state = nodes[idx + 1][1]
                if state == "completed" and next_state in ("active", "completed"):
                    link_parts.append(bold_themed("pass", " ━━ "))
                elif next_state == "failed":
                    link_parts.append(bold_themed("fail", " ─x "))
                else:
                    link_parts.append(themed("dim", " ── "))

        row_labels = ""
        row_digests = ""
        for i, lbl in enumerate(label_parts):
            row_labels += lbl
            row_digests += digest_parts[i]
            if i < len(link_parts):
                row_labels += link_parts[i]
                row_digests += "     "

        out += f"  {row_labels}\n"
        out += f"  {row_digests}"
        return out


class MechanicalSympathyHud(Static):
    """Low-overhead HUD for unified memory pressure."""

    memory_mb = reactive(0.0)
    memory_total_mb = reactive(16384.0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="mechanical-sympathy", **kwargs)

    def on_mount(self) -> None:
        self.refresh_memory()

    def refresh_memory(self) -> None:
        """Re-read unified memory pressure.

        Previously sampled once at mount and never again, so a "pressure" gauge showed the
        pressure at startup for the rest of the session -- worse than no gauge, because it looks
        live. The console's periodic refresh calls this.
        """
        try:
            import psutil

            mem = psutil.virtual_memory()
            self.memory_mb = mem.used / (1024 * 1024)
            self.memory_total_mb = mem.total / (1024 * 1024)
        except Exception:
            pass

    def render(self) -> str:
        ratio = self.memory_mb / self.memory_total_mb if self.memory_total_mb > 0 else 0
        if ratio < 0.5:
            mem_token = "pass"
        elif ratio < 0.75:
            mem_token = "warn"
        else:
            mem_token = "fail"

        mem_gb = self.memory_mb / 1024
        total_gb = self.memory_total_mb / 1024

        # The MLX segment that used to sit here rendered `token_rate` and `model_loaded`, two
        # reactives nothing ever assigned -- so it read "MLX NO MODEL" permanently, whether or not
        # a model was loaded. A readout that cannot be right is not a readout. Nothing measures
        # local token throughput today; when something does, it can earn its place back.
        return (
            f" {themed('dim', '⚙')}  "
            f"RAM {themed(mem_token, f'{mem_gb:.1f}/{total_gb:.0f}GB')}"
        )


class ThirdDoorGate(Static):
    """Eight authority constraints — vault stays shut until all are True.

    Unevaluated (None) is not pass and not fail — open slot. This class used to promise that in
    this docstring and then contradict it four lines into `render()`, collapsing every non-True
    slot into `VAULT LOCKED`. So a machine that had never been assessed reported the same verdict
    as one that had been assessed and refused, and `docs/CAPABILITY_PROMOTION.md` recorded the
    resulting readout as the truth. The verdict now comes from `third_door_state()`, which is the
    single place the four states are derived.

    It renders. It does not enforce: no caller consults its state to decide anything, which is
    pinned by `test_the_third_door_is_a_readout_not_a_blocker`. If it is ever wired to a lock, that
    lock binds to `third_door_state()`, and it must refuse only on `THIRD_DOOR_LOCKED` — refusing
    on `THIRD_DOOR_UNASSESSED` would enforce the absence of evidence as denial and shut every
    operator out of the surface on every host.
    """

    def __init__(self, view: ThirdDoorView | None = None, **kwargs: Any) -> None:
        super().__init__(id="third-door-gate", **kwargs)
        self._view: ThirdDoorView = view if view is not None else unassessed_third_door()

    def set_view(self, view: ThirdDoorView) -> None:
        """Take a whole projection, not loose constraints.

        `set_constraints(door.constraints)` dropped `door.source` on the floor at both call sites,
        so the widget could not tell "no readiness artifact exists" from "one exists and carries no
        constraint evidence" — two states with different remedies. Passing the view makes losing
        the source impossible rather than merely discouraged.
        """
        self._view = view
        self.refresh()

    @staticmethod
    def _slot(name: str, val: bool | None) -> str:
        if val is True:
            return themed("pass", f"▣ {name:<20}")
        if val is False:
            return themed("fail", f"□ {name:<20}")
        return themed("dim", f"▫ {name:<20}")

    def _verdict(self) -> str:
        """The one line an operator actually reads. It must not overclaim in either direction."""
        constraints = self._view.constraints
        values = [constraints.get(name) for name in THIRD_DOOR_CONSTRAINTS]
        satisfied = sum(1 for v in values if v is True)
        refused = sum(1 for v in values if v is False)
        unassessed = sum(1 for v in values if v is None)
        state = self._view.state

        if state == THIRD_DOOR_UNLOCKED:
            return bold_themed("pass", "VAULT UNLOCKED — all 8 constraints satisfied")
        if state == THIRD_DOOR_LOCKED:
            detail = f"{refused} refused"
            if unassessed:
                detail += f", {unassessed} unassessed"
            return bold_themed("fail", f"VAULT LOCKED — {detail}")
        if state == THIRD_DOOR_INCOMPLETE:
            return bold_themed(
                "warn", f"VAULT INCOMPLETE — {satisfied}/8 satisfied, {unassessed} unassessed · none refused"
            )
        # THIRD_DOOR_UNASSESSED: shut, but nothing has been evaluated. Not a refusal, and saying so
        # is the entire point of this branch existing.
        return bold_themed("hint", "VAULT UNASSESSED — no constraint has been evaluated")

    def _source_note(self) -> str | None:
        """For an unassessed door, say which of the two reasons it is unassessed for.

        "Mint a readiness artifact" and "your readiness artifact carries no recognised evidence"
        are different jobs, and an operator staring at eight open slots cannot tell them apart from
        the grid alone.
        """
        if self._view.state != THIRD_DOOR_UNASSESSED:
            return None
        if self._view.source == "readiness":
            return themed("dim", "  a readiness artifact was found, but carries no recognised constraint evidence")
        return themed("dim", "  no promotion readiness artifact found — compose: builder-promote readiness …")

    def render(self) -> str:
        lines = [f"{bold_themed('warn', 'THE THIRD DOOR')}  {themed('hint', 'authority requires all 8')}\n"]

        # Iterated over the canonical eight rather than over `constraints.keys()`. The grid used to
        # walk whatever keys it was handed and pad to eight with an em-dash, while the verdict below
        # evaluated the canonical eight — so a view with unexpected keys drew one set of slots and
        # judged a different set. Same bug class as the verdict itself: two readers, two rules.
        constraints = self._view.constraints
        for i in range(0, len(THIRD_DOOR_CONSTRAINTS), 2):
            k1 = THIRD_DOOR_CONSTRAINTS[i]
            k2 = THIRD_DOOR_CONSTRAINTS[i + 1]
            lines.append(f"  {self._slot(k1, constraints.get(k1))}  {self._slot(k2, constraints.get(k2))}")

        lines.append("")
        lines.append(f"  {self._verdict()}")
        note = self._source_note()
        if note is not None:
            lines.append(note)

        return "\n".join(lines)
