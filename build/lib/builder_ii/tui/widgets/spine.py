"""Artifact Spine — living dependency chain (left column).

Density glyphs:
  █  green  = artifact present, no local errors
  ▒  amber  = gate open / HITL required
  ░  dim    = not yet present
  ✗  red    = verification/errors on artifact
  ⊘  gray   = intentionally disabled
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Input, Static

from builder_ii.tui.projections.chain import PIPELINE_STAGES, StageView, project_chain
from builder_ii.tui.projections.render import bold_themed, status_glyph, themed

ArtifactStatus = type("ArtifactStatus", (), {
    "VERIFIED": "verified",
    "GATE_OPEN": "gate",
    "PENDING": "pending",
    "FAILED": "failed",
    "DISABLED": "disabled",
})()


class SpineItem(Static):
    """A single artifact stage in the spine."""

    status = reactive("pending")
    selected = reactive(False)

    def __init__(
        self,
        artifact_id: str,
        label: str,
        status: str = "pending",
        *,
        is_last: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.artifact_id = artifact_id
        self.artifact_label = label
        self.status = status
        self.is_last = is_last
        self.add_class("spine-item")

    def render(self) -> str:
        glyph = status_glyph(self.status)
        indicator = bold_themed("active", "▸") if self.selected else " "
        connector = " " if self.is_last else themed("dim", "│")
        # Two-line density: stage row + connector
        line = f" {indicator} {glyph}  {self.artifact_label}"
        if not self.is_last:
            line += f"\n   {connector}"
        return line

    def watch_status(self, new_status: str) -> None:
        for cls in (
            "artifact-verified",
            "artifact-gate",
            "artifact-pending",
            "artifact-failed",
            "artifact-disabled",
        ):
            self.remove_class(cls)
        css = {
            "verified": "artifact-verified",
            "gate": "artifact-gate",
            "pending": "artifact-pending",
            "failed": "artifact-failed",
            "disabled": "artifact-disabled",
        }.get(new_status, "artifact-pending")
        self.add_class(css)

    def watch_selected(self, selected: bool) -> None:
        if selected:
            self.add_class("-selected")
        else:
            self.remove_class("-selected")


class ArtifactSpine(Vertical):
    """Left column: live artifact chain as a structural field."""

    can_focus = True

    BINDINGS = [
        Binding("up", "move_up", "Up", show=False),
        Binding("k", "move_up", "Up (vim)", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("j", "move_down", "Down (vim)", show=False),
    ]

    selected_index = reactive(0)

    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="spine-container", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._items: list[SpineItem] = []
        self._search_input: Input | None = None
        self._stage_views: tuple[StageView, ...] = ()
        self._on_select: Any = None  # optional callback(stage_dict | None)

    def set_selection_handler(self, handler: Any) -> None:
        self._on_select = handler

    def compose(self) -> ComposeResult:
        yield Static("CHAIN", id="spine-title")
        self._search_input = Input(placeholder="Filter…", id="spine-search")
        self._search_input.display = False
        yield self._search_input
        with ScrollableContainer(id="spine-list"):
            last_i = len(PIPELINE_STAGES) - 1
            for i, stage in enumerate(PIPELINE_STAGES):
                item = SpineItem(
                    artifact_id=stage["id"],
                    label=stage["label"],
                    is_last=i == last_i,
                )
                self._items.append(item)
                yield item
        yield Static(
            f" {bold_themed('active', 'TAB')} cycle  {bold_themed('active', '/')} filter\n"
            f" {bold_themed('active', 'SPC')} pin    {bold_themed('active', 'j/k')} move",
            id="spine-hints",
        )

    def on_mount(self) -> None:
        self._refresh_chain_state()
        if self._items:
            self._items[0].selected = True

    def _refresh_chain_state(self) -> None:
        view = project_chain(self.artifacts_dir)
        self._stage_views = view.stages
        by_id = {s.stage_id: s for s in view.stages}
        for item in self._items:
            stage = by_id.get(item.artifact_id)
            if stage is not None:
                item.status = stage.status

    def action_move_up(self) -> None:
        if self.selected_index > 0:
            self.selected_index -= 1

    def action_move_down(self) -> None:
        if self.selected_index < len(self._items) - 1:
            self.selected_index += 1

    def toggle_search(self) -> None:
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
            item.display = (not query) or (query in item.artifact_label.lower())

    def watch_selected_index(self, new_index: int) -> None:
        for i, item in enumerate(self._items):
            item.selected = i == new_index
        if self._on_select is not None:
            self._on_select(self.get_selected_artifact())

    def get_selected_artifact(self) -> dict[str, str] | None:
        if 0 <= self.selected_index < len(PIPELINE_STAGES):
            return dict(PIPELINE_STAGES[self.selected_index])
        return None

    def get_selected_stage_view(self) -> StageView | None:
        if 0 <= self.selected_index < len(self._stage_views):
            return self._stage_views[self.selected_index]
        return None

    async def refresh_data(self) -> None:
        self._refresh_chain_state()
