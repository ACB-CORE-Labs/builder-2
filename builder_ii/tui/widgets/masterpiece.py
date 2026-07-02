"""Masterpiece Widgets — Visualizing the Builder-II Engineering Pillars.

1. EpistemicMatrix (Semantic Rigor)
   Visually enforces the strict progression: Planned -> Executed -> Verified -> Promoted.
   Hashes must align for links to turn green. You cannot conflate states.

2. MechanicalSympathyHud (Mechanical Sympathy)
   Low-overhead HUD showing M1 unified memory pressure and MLX token throughput.
   The system is breathing — you can see it.

3. ThirdDoorGate (The Third Door)
   Every capability that changes authority requires 8 verified constraints.
   The vault stays locked until every constraint is satisfied.
"""

from __future__ import annotations

import os
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static


# ── Epistemic Matrix (Semantic Rigor) ───────────────────────────────

EPISTEMIC_STATES = ("pending", "active", "completed", "failed")


class EpistemicMatrix(Static):
    """Visualizes: Planned -> Executed -> Verified -> Promoted.

    A Vertical container that renders the full pipeline using Rich markup.
    The key insight: this is NOT a progress bar. It's a *proof chain*.
    Each node only lights up when the upstream hash is verified.
    """

    state_planned = reactive("completed")
    state_executed = reactive("active")
    state_verified = reactive("pending")
    state_promoted = reactive("pending")

    digest_planned = reactive("a8b2c4…")
    digest_executed = reactive("—")
    digest_verified = reactive("—")
    digest_promoted = reactive("—")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="epistemic-matrix", **kwargs)

    def render(self) -> str:
        nodes = [
            ("PLANNED", self.state_planned, self.digest_planned),
            ("EXECUTED", self.state_executed, self.digest_executed),
            ("VERIFIED", self.state_verified, self.digest_verified),
            ("PROMOTED", self.state_promoted, self.digest_promoted),
        ]

        # Row 1: Title
        out = "[bold #d2a8ff]THE EPISTEMIC MATRIX[/]  [#484f58]Semantic Rigor · planned ≠ executed ≠ verified ≠ promoted[/]\n"

        # Row 2: Node labels with glyphs and connecting links
        label_parts: list[str] = []
        link_parts: list[str] = []
        digest_parts: list[str] = []

        for idx, (label, state, digest) in enumerate(nodes):
            # Format node glyph + label
            if state == "completed":
                label_parts.append(f"[bold #3fb950]✓ {label:<9}[/]")
                digest_parts.append(f"[#484f58]{digest:<11}[/]")
            elif state == "active":
                label_parts.append(f"[bold #79c0ff]▶ {label:<9}[/]")
                digest_parts.append(f"[#c9d1d9]{digest:<11}[/]")
            elif state == "failed":
                label_parts.append(f"[bold #f85149]✗ {label:<9}[/]")
                digest_parts.append(f"[#f85149]{'MISMATCH':<11}[/]")
            else:  # pending
                label_parts.append(f"[#30363d]○ {label:<9}[/]")
                digest_parts.append(f"[#30363d]{'—':<11}[/]")

            # Format connecting link (except after last node)
            if idx < len(nodes) - 1:
                next_state = nodes[idx + 1][1]
                if state == "completed" and next_state in ("active", "completed"):
                    link_parts.append("[bold #3fb950] ━━ [/]")
                elif next_state == "failed":
                    link_parts.append("[bold #f85149] ─x [/]")
                else:
                    link_parts.append("[#21262d] ── [/]")

        # Assemble rows
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


# ── Mechanical Sympathy HUD ─────────────────────────────────────────

class MechanicalSympathyHud(Static):
    """Low-overhead HUD for M1 unified memory pressure and MLX throughput.

    Renders as a single compact line docked to the bottom of the signal rail.
    Reads /proc or sysctl-based memory stats when available; falls back to
    a static display otherwise. This widget is intentionally lightweight —
    mechanical sympathy means we don't waste cycles on the monitoring itself.
    """

    memory_mb = reactive(0.0)
    memory_total_mb = reactive(16384.0)  # 16GB M1 default
    token_rate = reactive(0.0)
    model_loaded = reactive(False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="mechanical-sympathy", **kwargs)

    def on_mount(self) -> None:
        """Try to read actual memory usage on mount."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            self.memory_mb = mem.used / (1024 * 1024)
            self.memory_total_mb = mem.total / (1024 * 1024)
        except Exception:
            pass

    def render(self) -> str:
        # Memory pressure color
        ratio = self.memory_mb / self.memory_total_mb if self.memory_total_mb > 0 else 0
        if ratio < 0.5:
            mem_color = "#3fb950"
        elif ratio < 0.75:
            mem_color = "#d29922"
        else:
            mem_color = "#f85149"

        mem_gb = self.memory_mb / 1024
        total_gb = self.memory_total_mb / 1024

        # Token rate display
        if self.model_loaded and self.token_rate > 0:
            tok_display = f"[bold #7ee787]{self.token_rate:.1f} t/s[/]"
        elif self.model_loaded:
            tok_display = "[#8b949e]IDLE[/]"
        else:
            tok_display = "[#484f58]NO MODEL[/]"

        return (
            f" [#484f58]⚙[/]  "
            f"RAM [{mem_color}]{mem_gb:.1f}/{total_gb:.0f}GB[/]  "
            f"[#484f58]│[/]  "
            f"MLX {tok_display}"
        )


# ── Third Door Gate ─────────────────────────────────────────────────

# The canonical 8 constraints from the Builder's Signet
THIRD_DOOR_CONSTRAINTS = (
    "Documentation",
    "Tests",
    "CLI Surface",
    "Failure Mode",
    "Approval Boundary",
    "Output Artifact",
    "Rollback Path",
    "Verification Path",
)


class ThirdDoorGate(Static):
    """Visualizes the 8 required capability constraints before promotion/authority.

    Every capability that changes authority requires:
      docs, tests, a command surface, a failure mode, a human approval boundary,
      an output artifact, a rollback path, and a verification path.

    The vault stays physically locked until all 8 are satisfied.
    """

    def __init__(self, constraints: dict[str, bool] | None = None, **kwargs: Any) -> None:
        super().__init__(id="third-door-gate", **kwargs)
        self._constraints: dict[str, bool] = constraints or {
            name: False for name in THIRD_DOOR_CONSTRAINTS
        }

    def set_constraints(self, constraints: dict[str, bool]) -> None:
        """Update constraint state and re-render."""
        self._constraints = constraints
        self.refresh()

    def render(self) -> str:
        lines = [
            "[bold #ffa657]THE THIRD DOOR[/]  "
            "[#484f58]Every capability that changes authority requires all 8[/]\n"
        ]

        # Draw a 4x2 grid of constraint slots
        keys = list(self._constraints.keys())
        # Pad to 8 if needed
        while len(keys) < 8:
            keys.append("—")

        for i in range(0, 8, 2):
            k1 = keys[i]
            k2 = keys[i + 1] if i + 1 < len(keys) else "—"
            v1 = self._constraints.get(k1, False)
            v2 = self._constraints.get(k2, False)

            c1 = "#3fb950" if v1 else "#f85149"
            g1 = "▣" if v1 else "□"
            c2 = "#3fb950" if v2 else "#f85149"
            g2 = "▣" if v2 else "□"

            lines.append(f"  [{c1}]{g1} {k1:<20}[/]  [{c2}]{g2} {k2}[/]")

        all_ok = all(self._constraints.get(k, False) for k in THIRD_DOOR_CONSTRAINTS)
        if all_ok:
            lines.append("\n  [bold #3fb950]╔════════════════════════════════════════╗[/]")
            lines.append("  [bold #3fb950]║  VAULT UNLOCKED — AUTHORITY GRANTED    ║[/]")
            lines.append("  [bold #3fb950]╚════════════════════════════════════════╝[/]")
        else:
            missing = sum(1 for k in THIRD_DOOR_CONSTRAINTS if not self._constraints.get(k, False))
            lines.append(f"\n  [bold #f85149]╔════════════════════════════════════════╗[/]")
            lines.append(f"  [bold #f85149]║  VAULT LOCKED — {missing} CONSTRAINT{'S' if missing != 1 else ''} MISSING       ║[/]")
            lines.append(f"  [bold #f85149]╚════════════════════════════════════════╝[/]")

        return "\n".join(lines)
