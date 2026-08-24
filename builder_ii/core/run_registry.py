"""Frontend-neutral registry projection for governed runs on disk.

Read-only. A "run" is a session with an event ledger under
``.builder/sessions/<id>/events/`` -- the same ledgers the governed MCP server (G1/G3) and
other governed lanes append to. Each row carries the run id, event count, last event, and the
whole-chain verdict from the canonical validator. Ordered most-recent first. Synthesizes
nothing: no sessions dir, or no ledgered runs, yields an empty roster.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    load_event_records,
    validate_event_chain_integrity,
)


@dataclass(frozen=True)
class RunRegistryEntry:
    run_id: str
    events_dir: str
    event_count: int
    last_event_type: str
    last_recorded_at: str
    chain_valid: bool | None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunRegistryView:
    entries: tuple[RunRegistryEntry, ...]

    @property
    def is_empty(self) -> bool:
        return not self.entries

    @property
    def rows(self) -> tuple[RunRegistryEntry, ...]:
        """One-release compatibility alias for the former TUI roster."""
        return self.entries

    def get(self, run_id: str) -> RunRegistryEntry | None:
        return next((entry for entry in self.entries if entry.run_id == run_id), None)

    def select(self, requested_run_id: str | None = None) -> RunRegistryEntry | None:
        """Select an exact run or the deterministic most-recent run.

        Entries are already ordered by recorded timestamp and then run id, both
        descending. An explicit id never falls back to a different run.
        """
        if requested_run_id is not None:
            return self.get(requested_run_id)
        return self.entries[0] if self.entries else None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "artifact_is_authority": False,
            "entries": [asdict(entry) for entry in self.entries],
            "grants_authority": False,
            "kind": "builder_ii.run_registry_view",
            "schema_version": 1,
        }


def _sessions_root(builder_root: Path | None) -> Path | None:
    if builder_root is None:
        return None
    root = builder_root / "sessions"
    return root if root.is_dir() else None


def _sequence(event: dict) -> int:
    seq = event.get("sequence")
    return seq if isinstance(seq, int) else 10**9


def _event_inventory_errors(events_dir: Path) -> tuple[str, ...]:
    """Expose files the canonical loader would otherwise skip silently."""
    errors: list[str] = []
    json_paths = sorted(events_dir.glob("*.json"))
    for path in json_paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid event JSON: {exc}")
            continue
        if not isinstance(value, dict) or value.get("kind") != EVENT_RECORD_KIND:
            errors.append(f"{path}: foreign artifact in canonical events directory")
    wal_path = events_dir / "events.wal"
    if wal_path.exists():
        try:
            payload = wal_path.read_bytes().rstrip(b"\x00")
            if not payload:
                errors.append(f"{wal_path}: empty event WAL")
            else:
                text = payload.decode("utf-8")
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict) or value.get("kind") != EVENT_RECORD_KIND:
                        errors.append(f"{wal_path}:{line_number}: foreign record in canonical event WAL")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{wal_path}: invalid event WAL: {exc}")
    return tuple(errors)


def project_run_registry(builder_root: Path | None) -> RunRegistryView:
    """Scan ``<builder_root>/sessions/*/events`` for ledgered runs, most-recent first."""
    root = _sessions_root(builder_root)
    if root is None:
        return RunRegistryView(entries=())

    entries: list[RunRegistryEntry] = []
    for session_dir in sorted(root.iterdir()):
        events_dir = session_dir / "events"
        if not events_dir.is_dir():
            continue
        records = load_event_records(events_dir)
        inventory_errors = _event_inventory_errors(events_dir)
        if not records and not inventory_errors:
            continue  # an empty directory is not yet a run
        ordered = sorted(records, key=lambda item: _sequence(item[0]))
        last = ordered[-1][0] if ordered else {}
        integrity = validate_event_chain_integrity(events_dir)
        entries.append(
            RunRegistryEntry(
                run_id=session_dir.name,
                events_dir=str(events_dir),
                event_count=len(ordered),
                last_event_type=str(last.get("event_type") or ""),
                last_recorded_at=str(last.get("recorded_at") or ""),
                chain_valid=bool(integrity.get("valid")) and not inventory_errors and bool(ordered),
                errors=inventory_errors,
            )
        )

    # ISO timestamps sort lexically; most-recent first, then run id for stability.
    entries.sort(key=lambda entry: (entry.last_recorded_at, entry.run_id), reverse=True)
    return RunRegistryView(entries=tuple(entries))


# Compatibility aliases are kept here as well as in the TUI facade so code
# importing a symbol through a dynamic extension does not become a flag-day
# migration. New code uses the registry names above.
RunRow = RunRegistryEntry
RunRosterView = RunRegistryView
project_run_roster = project_run_registry
