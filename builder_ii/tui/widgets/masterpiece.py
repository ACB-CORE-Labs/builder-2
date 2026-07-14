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

from builder_ii.tui.projections.gates import THIRD_DOOR_CONSTRAINTS
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
    token_rate = reactive(0.0)
    model_loaded = reactive(False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id="mechanical-sympathy", **kwargs)

    def on_mount(self) -> None:
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

        if self.model_loaded and self.token_rate > 0:
            tok_display = bold_themed("pass", f"{self.token_rate:.1f} t/s")
        elif self.model_loaded:
            tok_display = themed("hint", "IDLE")
        else:
            tok_display = themed("dim", "NO MODEL")

        return (
            f" {themed('dim', '⚙')}  "
            f"RAM {themed(mem_token, f'{mem_gb:.1f}/{total_gb:.0f}GB')}  "
            f"{themed('dim', '│')}  MLX {tok_display}"
        )


class ThirdDoorGate(Static):
    """Eight authority constraints — vault stays locked until all are True.

    Unevaluated (None) is not pass and not fail — open slot.
    """

    def __init__(self, constraints: dict[str, bool | None] | None = None, **kwargs: Any) -> None:
        super().__init__(id="third-door-gate", **kwargs)
        self._constraints: dict[str, bool | None] = constraints or {
            name: None for name in THIRD_DOOR_CONSTRAINTS
        }

    def set_constraints(self, constraints: dict[str, bool | None]) -> None:
        self._constraints = constraints
        self.refresh()

    def render(self) -> str:
        lines = [
            f"{bold_themed('warn', 'THE THIRD DOOR')}  "
            f"{themed('hint', 'authority requires all 8')}\n"
        ]

        keys = list(self._constraints.keys())
        while len(keys) < 8:
            keys.append("—")

        for i in range(0, 8, 2):
            k1 = keys[i]
            k2 = keys[i + 1] if i + 1 < len(keys) else "—"
            v1 = self._constraints.get(k1)
            v2 = self._constraints.get(k2)

            def slot(name: str, val: bool | None) -> str:
                if val is True:
                    return themed("pass", f"▣ {name:<20}")
                if val is False:
                    return themed("fail", f"□ {name:<20}")
                return themed("dim", f"▫ {name:<20}")

            lines.append(f"  {slot(k1, v1)}  {slot(k2, v2)}")

        evaluated = [self._constraints.get(k) for k in THIRD_DOOR_CONSTRAINTS]
        if all(v is True for v in evaluated):
            lines.append("")
            lines.append(f"  {bold_themed('pass', 'VAULT UNLOCKED — all constraints satisfied')}")
        else:
            missing = sum(1 for v in evaluated if v is not True)
            uneval = sum(1 for v in evaluated if v is None)
            detail = f"{missing} incomplete"
            if uneval:
                detail += f" ({uneval} unevaluated)"
            lines.append("")
            lines.append(f"  {bold_themed('fail', f'VAULT LOCKED — {detail}')}")

        return "\n".join(lines)
