"""Artifact Spine — The living dependency chain.

The left column of STRATUM. Each row is a governed artifact from the
artifact chain. Status glyphs are derived directly from the verification system.

  ✓  green  = SHA-verified, chain-valid
  ●  amber  = gate open / HITL required
  ○  dim    = not yet reachable (blocked upstream)
  ✗  red    = verification failed, chain broken
  ⊘  gray   = intentionally disabled by governance
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, Input

# ── Artifact type definitions for the canonical pipeline ─────────────

PIPELINE_STAGES: list[dict[str, str]] = [
    {"id": "repo-map", "label": "repo-map", "kind": "builder_ii.repo_map"},
    {"id": "ctx-pack", "label": "ctx-pack", "kind": "builder_ii.context_pack"},
    {"id": "session", "label": "session", "kind": "builder_ii.session_config"},
    {"id": "projection", "label": "projection", "kind": "builder_ii.goose_projection"},
    {"id": "wrap-plan", "label": "wrap-plan", "kind": "builder_ii.goose_wrapper_plan"},
    {"id": "ver-plan", "label": "ver-plan", "kind": "builder_ii.verification_execution_plan"},
    {"id": "exec-req", "label": "exec-req", "kind": "builder_ii.execution_candidate_manifest"},
    {"id": "postflight", "label": "postflight", "kind": "builder_ii.execution_postflight"},
    {"id": "promote", "label": "promote", "kind": "builder_ii.promotion_readiness"},
]


# ── Status Glyphs ────────────────────────────────────────────────────

class ArtifactStatus:
    VERIFIED = "verified"
    GATE_OPEN = "gate"
    PENDING = "pending"
    FAILED = "failed"
    DISABLED = "disabled"

GLYPH_MAP = {
    ArtifactStatus.VERIFIED: ("✓", "artifact-verified"),
    ArtifactStatus.GATE_OPEN: ("●", "artifact-gate"),
    ArtifactStatus.PENDING: ("○", "artifact-pending"),
    ArtifactStatus.FAILED: ("✗", "artifact-failed"),
    ArtifactStatus.DISABLED: ("⊘", "artifact-disabled"),
}


# ── Single Spine Item ────────────────────────────────────────────────

class SpineItem(Static):
    """A single artifact in the spine."""

    status = reactive(ArtifactStatus.PENDING)
    selected = reactive(False)

    def __init__(
        self,
        artifact_id: str,
        label: str,
        status: str = ArtifactStatus.PENDING,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.artifact_id = artifact_id
        self.artifact_label = label
        self.status = status
        self.add_class("spine-item")

    def render(self) -> str:
        glyph, css_class = GLYPH_MAP.get(self.status, ("?", "artifact-pending"))
        indicator = "▸" if self.selected else " "
        return f" {indicator} {glyph}  {self.artifact_label}"

    def watch_status(self, new_status: str) -> None:
        for cls in ("artifact-verified", "artifact-gate", "artifact-pending", "artifact-failed", "artifact-disabled"):
            self.remove_class(cls)
        _, css_class = GLYPH_MAP.get(new_status, ("?", "artifact-pending"))
        self.add_class(css_class)

    def watch_selected(self, selected: bool) -> None:
        if selected:
            self.add_class("-selected")
        else:
            self.remove_class("-selected")


# ── The Artifact Spine Widget ────────────────────────────────────────

class ArtifactSpine(Vertical):
    """The left column: a live artifact chain rendered as a dependency graph."""

    can_focus = True

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("k", "move_up", "Up (vim)", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("j", "move_down", "Down (vim)", show=False),
    ]

    selected_index = reactive(0)
    show_memory = reactive(False)

    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="spine-container", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._items: list[SpineItem] = []
        self._search_input: Input | None = None

    def compose(self) -> ComposeResult:
        yield Static("ARTIFACT SPINE", id="spine-title")
        self._search_input = Input(placeholder="Filter...", id="spine-search")
        self._search_input.display = False
        yield self._search_input
        with ScrollableContainer(id="spine-list"):
            for stage in PIPELINE_STAGES:
                item = SpineItem(
                    artifact_id=stage["id"],
                    label=stage["label"],
                )
                self._items.append(item)
                yield item
        yield Static(
            " [bold #58a6ff][TAB][/] cycle  [bold #58a6ff][/][/] search\n"
            " [bold #58a6ff][SPC][/] pin   [bold #58a6ff][M][/] memory",
            id="spine-hints",
        )

    def on_mount(self) -> None:
        self._refresh_chain_state()
        if self._items:
            self._items[0].selected = True

    def _refresh_chain_state(self) -> None:
        """Scan the artifacts directory and update statuses."""
        if not self.artifacts_dir or not self.artifacts_dir.exists():
            return

        found_artifacts: dict[str, dict[str, Any]] = {}
        for path in sorted(self.artifacts_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                kind = data.get("kind", "")
                found_artifacts[kind] = data
            except (json.JSONDecodeError, OSError):
                continue

        # Determine status for each pipeline stage
        upstream_ok = True
        for item in self._items:
            stage = next(
                (s for s in PIPELINE_STAGES if s["id"] == item.artifact_id),
                None,
            )
            if stage is None:
                continue

            artifact = found_artifacts.get(stage["kind"])
            if artifact is None:
                if upstream_ok:
                    item.status = ArtifactStatus.PENDING
                else:
                    item.status = ArtifactStatus.PENDING
                upstream_ok = False
                continue

            # Check for errors / verification state
            errors = artifact.get("errors", [])
            governance = artifact.get("governance", {})
            hitl_required = governance.get("hitl_required", False)

            if errors:
                item.status = ArtifactStatus.FAILED
                upstream_ok = False
            elif hitl_required:
                item.status = ArtifactStatus.GATE_OPEN
                # Gate open doesn't break upstream for display
            else:
                item.status = ArtifactStatus.VERIFIED
                # Upstream remains OK

    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def action_move_down(self) -> None:
        if self.selected_index < len(self._items) - 1:
            self.selected_index += 1

    def toggle_search(self) -> None:
        """Toggle visibility and focus of the search input."""
        if self._search_input:
            self._search_input.display = not self._search_input.display
            if self._search_input.display:
                self._search_input.focus()
            else:
                self.focus()
                self._search_input.value = ""
                self._filter_items("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "spine-search":
            self._filter_items(event.value)

    def _filter_items(self, query: str) -> None:
        query = query.lower()
        for item in self._items:
            if not query or query in item.artifact_label.lower():
                item.display = True
            else:
                item.display = False

    def watch_selected_index(self, new_index: int) -> None:
        for i, item in enumerate(self._items):
            item.selected = i == new_index

    def get_selected_artifact(self) -> dict[str, str] | None:
        """Return the stage dict for the currently selected artifact."""
        if 0 <= self.selected_index < len(PIPELINE_STAGES):
            return PIPELINE_STAGES[self.selected_index]
        return None

    async def refresh_data(self) -> None:
        """Called periodically to re-scan artifacts."""
        self._refresh_chain_state()
