"""Append-only, hash-chained event ledger for governed TUI exploration runs.

`scripts/semantic_tui_driver.py` writes one `builder_ii.tui_audit_ledger_event` per line of
`.builder/artifacts/tui_audit_ledger.jsonl`; `scripts/validate_tui_audit_ledger.py` re-checks the
file. Both import their digest computation from here, because a validator that re-implements the
writer's hashing cannot detect drift between the two -- it would only ever prove that two copies
of the same bug agree.

Two digests, because one field cannot carry both properties
-----------------------------------------------------------
``state_digest`` binds **only** the semantic ``state`` payload. Identical UI states therefore
serialise to identical digests, which is what makes the ledger diffable run-over-run -- the point
of the exercise. A previous revision hashed the whole entry, `uuid4` ``run_id`` and `time.time()`
``timestamp`` included, so two runs of a byte-identical mount produced different digests: the
field answered "which run was this?" and could never answer "did the UI change?".

``entry_digest`` binds the whole entry, ``prev_digest`` included, and is the chain link. Splitting
the roles is load-bearing rather than tidy. If a single state-bound digest were also the chain
link, the chain would be forgeable: the digest would not commit to ``prev_digest``, so deleting
line N and re-pointing line N+1's ``prev_digest`` at line N-1 would leave every digest still
verifying. Committing the link into the hash is what actually makes deletion and reordering
detectable, which is the property this file claims.

The chain spans one **run**, written to one file per run. A run resumes from the last line's
``entry_digest`` (`None` only at genesis), so within a run, deleting or reordering any event
breaks the chain at that point.

One file per run is a deliberate trade, not an oversight
--------------------------------------------------------
An earlier revision pointed every run at a single shared ledger and chained across runs, which
bought one extra property: deleting a whole run's block from a retained file was as detectable as
deleting a single line. That property is gone, and it is worth being exact about what it cost and
what it bought.

It bought correctness. Two runs sharing one file both read the same chain head and both wrote from
it -- measured, two concurrent runs produced four events in which every link after the first was
broken. Concurrency corrupted the ledger, and the corruption was *indistinguishable from tampering*:
the validator reported deletion or reordering on a file nobody had touched. An evidence artifact
whose integrity check fires on its own normal use trains the reader to ignore it, which is worse
than not having it. It also bounds growth to one run rather than to every run a checkout ever made.

It cost little, because the property was already nearly worthless. Nothing counter-signs these
files, so deleting a whole ledger and re-running always produced a fresh chain that validates
clean. Cross-run chaining only ever detected *partial* deletion from a file an attacker chose to
retain -- and an attacker who can edit the file can delete it. What survives is the property that
was doing the real work: within a run, the recorded sequence cannot be altered undetectably.

What this does not close
------------------------
Truncation from the end. Any append-only chain can be cut at the tail and still verify, absent an
external anchor recording the expected length or head digest. Deletion of an entire run's file,
which no longer leaves a gap in a longer chain -- and did not meaningfully do so before, per above.
Nothing here counter-signs anything: the same process that writes the events computes the digests,
so this is tamper-**evident** under later editing, not proof of what happened. It is a record,
never authority -- consistent with `artifact != authority`. It grants nothing, flips no matrix row,
and gates no promotion.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

TUI_AUDIT_LEDGER_EVENT_KIND = "builder_ii.tui_audit_ledger_event"
TUI_AUDIT_LEDGER_SCHEMA_VERSION = 1

#: `prev_digest` of the first line in a file. Distinguishes "start of chain" from "link missing".
GENESIS_PREV_DIGEST: str | None = None

_EVENT_TYPES = ("MOUNT", "ACTION")
_REQUIRED_FIELDS = (
    "kind",
    "schema_version",
    "seq",
    "run_id",
    "timestamp",
    "event",
    "state",
    "state_digest",
    "prev_digest",
    "entry_digest",
)


def canonical_json(value: Any) -> str:
    """Serialise deterministically: sorted keys, no incidental whitespace, unescaped unicode.

    Both digests hash this. `sort_keys` matters because dict ordering is insertion-ordered and the
    writer's insertion order is not a property of the state being recorded; `ensure_ascii=False`
    keeps the glyphs the TUI actually renders (`⚡`, `⊘`) from being re-encoded differently by a
    reader that round-trips the file.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_state_digest(state: Any) -> str:
    """Digest of the semantic payload alone -- no run_id, no timestamp, no chain link."""
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


def compute_entry_digest(entry: dict[str, Any]) -> str:
    """Digest of the entry excluding `entry_digest` itself; commits to `prev_digest`."""
    core = {k: v for k, v in entry.items() if k != "entry_digest"}
    return hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()


def build_event(
    *,
    seq: int,
    run_id: str,
    timestamp: float,
    event: str,
    state: dict[str, Any],
    prev_digest: str | None,
    action: str | None = None,
    target: str | None = None,
    status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build one chained ledger event.

    The payload key is always ``state``. A previous revision used ``state`` for MOUNT and
    ``resulting_state`` for ACTION, so a consumer had to know the event type to find the payload
    and every schema check had to branch. One name, one shape.
    """
    if event not in _EVENT_TYPES:
        raise ValueError(f"event must be one of {_EVENT_TYPES}, got {event!r}")

    entry: dict[str, Any] = {
        "kind": TUI_AUDIT_LEDGER_EVENT_KIND,
        "schema_version": TUI_AUDIT_LEDGER_SCHEMA_VERSION,
        "seq": seq,
        "run_id": run_id,
        # Metadata only: deliberately outside `state_digest` so it cannot make identical UI states
        # serialise to different digests. It is inside `entry_digest`, so it cannot be edited
        # after the fact without breaking the chain.
        "timestamp": timestamp,
        "event": event,
        "action": action,
        "target": target,
        "status": status,
        "error": error,
        "state": state,
        "state_digest": compute_state_digest(state),
        "prev_digest": prev_digest,
    }
    entry["entry_digest"] = compute_entry_digest(entry)
    return entry


def read_chain_head(path: Path) -> tuple[int, str | None]:
    """Return `(next_seq, prev_digest)` to continue an existing file's chain.

    A fresh or absent file starts the chain at `(0, GENESIS_PREV_DIGEST)`. A file whose last line
    is unreadable raises rather than silently starting a second, unlinked chain inside it: a
    ledger with two genesis points is one whose gaps cannot be seen.
    """
    if not path.exists() or path.stat().st_size == 0:
        return 0, GENESIS_PREV_DIGEST

    last = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    if last is None:
        return 0, GENESIS_PREV_DIGEST

    try:
        entry = json.loads(last)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: last line is not valid JSON; refusing to fork the chain") from exc

    digest = entry.get("entry_digest")
    seq = entry.get("seq")
    if not isinstance(digest, str) or not isinstance(seq, int):
        raise ValueError(f"{path}: last line has no usable entry_digest/seq; refusing to fork the chain")
    return seq + 1, digest


def append_event(path: Path, entry: dict[str, Any]) -> None:
    """Append one event as a single JSONL line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_ledger(path: Path) -> list[str]:
    """Re-check schema and chain integrity. Returns errors; empty means valid.

    Recomputes both digests rather than trusting them, and walks `prev_digest` link by link. An
    empty file is an error, not a pass: "nothing to check" must never read as "checked and clean".
    """
    if not path.exists():
        return [f"File {path} does not exist"]

    raw = path.read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return [f"{path} contains no events; an empty ledger cannot be reported as valid"]

    errors: list[str] = []
    expected_prev: str | None = GENESIS_PREV_DIGEST

    for index, line in enumerate(lines):
        where = f"line {index + 1}"
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{where}: not valid JSON: {exc}")
            return errors  # the chain cannot be walked past an unreadable link

        if not isinstance(entry, dict):
            errors.append(f"{where}: event must be a JSON object")
            return errors

        missing = [f for f in _REQUIRED_FIELDS if f not in entry]
        if missing:
            errors.append(f"{where}: missing required field(s): {', '.join(missing)}")
            return errors

        if entry["kind"] != TUI_AUDIT_LEDGER_EVENT_KIND:
            errors.append(f"{where}: invalid kind: expected {TUI_AUDIT_LEDGER_EVENT_KIND!r}, got {entry['kind']!r}")
        if entry["schema_version"] != TUI_AUDIT_LEDGER_SCHEMA_VERSION:
            errors.append(
                f"{where}: invalid schema_version: expected {TUI_AUDIT_LEDGER_SCHEMA_VERSION}, "
                f"got {entry['schema_version']!r}"
            )
        if entry["event"] not in _EVENT_TYPES:
            errors.append(f"{where}: invalid event: expected one of {_EVENT_TYPES}, got {entry['event']!r}")
        if entry["seq"] != index:
            errors.append(f"{where}: seq {entry['seq']!r} does not match position {index}; events reordered or dropped")
        if not isinstance(entry["state"], dict):
            errors.append(f"{where}: 'state' must be an object")
        else:
            recomputed_state = compute_state_digest(entry["state"])
            if entry["state_digest"] != recomputed_state:
                errors.append(
                    f"{where}: state_digest does not match the recorded state "
                    f"(recorded {entry['state_digest']!r}, recomputed {recomputed_state!r})"
                )

        if entry["prev_digest"] != expected_prev:
            if index == 0:
                errors.append(f"{where}: first event must have prev_digest {GENESIS_PREV_DIGEST!r}")
            else:
                errors.append(
                    f"{where}: chain broken -- prev_digest {entry['prev_digest']!r} does not match "
                    f"the previous event's entry_digest {expected_prev!r}; an event was deleted, "
                    f"reordered, or rewritten"
                )

        recomputed_entry = compute_entry_digest(entry)
        if entry["entry_digest"] != recomputed_entry:
            errors.append(
                f"{where}: entry_digest does not match the event's contents "
                f"(recorded {entry['entry_digest']!r}, recomputed {recomputed_entry!r})"
            )

        expected_prev = entry["entry_digest"]

    return errors
