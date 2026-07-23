"""Projection: the operator verb-stage journey (T1).

Overlays a PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> PROMOTE axis on the artifact
chain, so the operator sees a journey rather than a soup of instruments. Each stage's state is
*derived from real artifacts on disk* via ``project_chain`` -- reached when its representative
pipeline stage is present; VERIFY additionally requires a valid chain. The first not-yet-reached
stage is the active one. Synthesizes nothing: an empty tree makes PREPARE active and the rest
pending.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder_ii.tui.projections.chain import project_chain

# verb -> (instrument key, representative pipeline stage ids)
_STAGE_SPEC: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("PREPARE", "P", ("repo-map", "ctx-pack", "session")),
    ("PLAN", "Y", ("projection", "wrap-plan", "ver-plan")),
    ("APPROVE", "A", ("exec-req",)),
    ("EXECUTE", "L", ("postflight",)),
    ("VERIFY", "E", ("postflight",)),
    ("PROMOTE", "S", ("promote",)),
)
_REACHED_STATUSES = {"present", "verified", "gate"}


@dataclass(frozen=True)
class StageCell:
    verb: str
    key: str
    state: str  # done | active | pending


@dataclass(frozen=True)
class StageAxisView:
    cells: tuple[StageCell, ...]

    @property
    def active_verb(self) -> str:
        for cell in self.cells:
            if cell.state == "active":
                return cell.verb
        return self.cells[-1].verb if self.cells else ""


def project_operator_stages(artifacts_dir: Path | None) -> StageAxisView:
    chain = project_chain(artifacts_dir)
    status_by_id = {stage.stage_id: stage.status for stage in chain.stages}

    def present(stage_id: str) -> bool:
        return status_by_id.get(stage_id) in _REACHED_STATUSES

    reached: dict[str, bool] = {
        verb: any(present(stage_id) for stage_id in ids) for verb, _key, ids in _STAGE_SPEC
    }
    # VERIFY means executed *and* the chain validates, not merely that a postflight exists.
    reached["VERIFY"] = reached["VERIFY"] and bool(chain.chain_valid)

    cells: list[StageCell] = []
    active_assigned = False
    for verb, key, _ids in _STAGE_SPEC:
        if reached[verb]:
            state = "done"
        elif not active_assigned:
            state = "active"
            active_assigned = True
        else:
            state = "pending"
        cells.append(StageCell(verb=verb, key=key, state=state))
    return StageAxisView(cells=tuple(cells))
