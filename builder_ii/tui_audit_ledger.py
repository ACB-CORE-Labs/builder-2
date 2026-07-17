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

One file per run, anchored by a master index
--------------------------------------------
An earlier revision pointed every run at a single shared ledger and chained across runs. That was
incorrect: two runs sharing one file both read the same chain head and both wrote from it --
measured, two concurrent runs produced four events in which every link after the first was broken.
Concurrency corrupted the ledger, and the corruption was *indistinguishable from tampering*, so the
validator reported deletion or reordering on a file nobody had touched. An evidence artifact whose
integrity check fires on its own normal use trains the reader to ignore it, which is worse than not
having it.

Splitting per run fixed that and cost one property: deleting a whole run's file left no gap, because
there was no longer a longer chain for it to leave a gap in. `append_run_to_index` restores that
property rather than the old bug. On completion a run appends one line to a **master index** naming
its `run_id`, its file, its event count, and its final `entry_digest` -- itself chained. Because a
run's head digest transitively commits to every link before it, one index line binds that run's
entire chain.

The index is the same shared-file shape that broke before, so it does not repeat the mistake by
hoping: `append_run_to_index` holds an exclusive `flock` across read-tail-then-append, which is the
critical section the old code did not have. Naive concurrent appends would fork this chain exactly
as they forked the last one -- the bug moved up a level, not away.

What this closes, precisely
---------------------------
Deletion of a whole run's ledger file (the index still names it, and cross-checking reports it
missing). Truncation or rewriting of any run's events (head digest and event count stop matching).
Deletion or reordering of index lines (the index's own chain breaks).

What this does not close
------------------------
Truncation from the end -- of a run's ledger *and* of the index itself. Any append-only chain can be
cut at the tail and still verify, absent an external anchor recording the expected length or head
digest. The index is that anchor for a run; nothing anchors the index.

A run that crashed before completing has no index line, and that is indistinguishable from one whose
index line was deleted. An unindexed ledger is therefore not reported as tampering -- it is the
normal residue of a crash, and firing on it would be the "integrity check that cries wolf on its own
normal use" failure this file already paid for once.

And nothing here counter-signs anything. The same host, in the same process, writes the events,
computes the digests, and appends the index line. This is tamper-**evident** under *later* editing
by someone else; it is not proof of what happened, and it is emphatically not proof against the
writer. It is a record, never authority -- consistent with `artifact != authority`. It grants
nothing, flips no matrix row, and gates no promotion. "Cryptographic continuity" here means the
chain is checkable, not that the chain is trustworthy on its own.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator

try:  # POSIX only. Guarded so the read-only half of this module still imports where it is absent.
    import fcntl
except ImportError:  # pragma: no cover - the supported targets (macOS, Linux) all have it
    fcntl = None  # type: ignore[assignment]

TUI_AUDIT_LEDGER_EVENT_KIND = "builder_ii.tui_audit_ledger_event"
TUI_AUDIT_LEDGER_SCHEMA_VERSION = 1

TUI_AUDIT_LEDGER_INDEX_KIND = "builder_ii.tui_audit_ledger_index_entry"
TUI_AUDIT_LEDGER_INDEX_SCHEMA_VERSION = 1

#: The master index lives beside the per-run ledgers it anchors. One fixed name, because unlike a
#: run's file this one *must* be nameable in advance -- an anchor nobody can find anchors nothing.
MASTER_INDEX_FILENAME = "tui_audit_ledger_index.jsonl"

_INDEX_REQUIRED_FIELDS = (
    "kind",
    "schema_version",
    "seq",
    "run_id",
    "timestamp",
    "ledger_file",
    "event_count",
    "ledger_head_digest",
    "prev_digest",
    "entry_digest",
)

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


@contextmanager
def _exclusive(handle: IO[str]) -> Iterator[None]:
    """Hold an exclusive advisory lock on `handle` for the duration of the block.

    Advisory is sufficient because only `append_run_to_index` writes this file, and it always takes
    the lock. It is *not* sufficient against an editor or a shell redirect, which is the same
    limitation the rest of this module already has: tamper-evident, not tamper-proof.

    A missing `fcntl` raises rather than proceeding unlocked. Silently degrading to the racy path
    would reintroduce the exact chain fork this lock exists to prevent, on the one platform nobody
    would be watching for it.
    """
    if fcntl is None:  # pragma: no cover - macOS and Linux both have fcntl
        raise RuntimeError(
            "fcntl.flock is unavailable on this platform; refusing to append to the master ledger "
            "index unlocked, because concurrent appends fork the chain and the fork is "
            "indistinguishable from tampering"
        )
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_ledger_summary(path: Path) -> tuple[int, str]:
    """Return `(event_count, head_entry_digest)` for a completed run's ledger.

    The head digest is worth more than it looks: every `entry_digest` commits to its `prev_digest`,
    so the last one transitively binds every event in the file. One index line therefore anchors a
    whole run, and `event_count` catches the one thing a head digest alone cannot -- a tail cut,
    where the remaining prefix still verifies perfectly.
    """
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"{path}: no events; a run that recorded nothing must not be indexed as if it had")

    try:
        last = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: last line is not valid JSON; cannot anchor an unreadable chain") from exc

    digest = last.get("entry_digest")
    if not isinstance(digest, str) or not digest:
        raise ValueError(f"{path}: last event has no entry_digest; nothing to anchor")
    return len(lines), digest


def compute_index_entry_digest(entry: dict[str, Any]) -> str:
    """Digest of an index entry excluding `entry_digest` itself; commits to `prev_digest`."""
    core = {k: v for k, v in entry.items() if k != "entry_digest"}
    return hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()


def append_run_to_index(index_path: Path, *, run_id: str, ledger_path: Path, timestamp: float) -> dict[str, Any]:
    """Append one chained line anchoring a completed run. Returns the written entry.

    The whole point is the lock. Read-tail-then-append is a read-modify-write, and two runs
    finishing together would both read the same tail and both chain from it -- forking this index
    exactly as the shared per-event ledger forked before it. The critical section is held across
    *both* halves; taking it only around the write would be decorative.

    `ledger_file` is stored as a bare filename, not a path. The index and the ledgers it anchors
    live in one directory, and an absolute path would bind the record to the checkout that produced
    it -- so moving `.builder/artifacts/`, or validating it from another worktree, would read as
    every run having been deleted at once.
    """
    event_count, head_digest = read_ledger_summary(ledger_path)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a+", encoding="utf-8") as handle:
        with _exclusive(handle):
            # Read *after* acquiring, never before: a tail read outside the lock is the race.
            handle.seek(0)
            lines = [ln for ln in handle.read().splitlines() if ln.strip()]

            seq = 0
            prev_digest: str | None = GENESIS_PREV_DIGEST
            if lines:
                try:
                    last = json.loads(lines[-1])
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{index_path}: last line is not valid JSON; refusing to fork the index") from exc
                last_seq, last_digest = last.get("seq"), last.get("entry_digest")
                if not isinstance(last_seq, int) or not isinstance(last_digest, str):
                    raise ValueError(f"{index_path}: last line has no usable seq/entry_digest; refusing to fork")
                seq, prev_digest = last_seq + 1, last_digest

            entry: dict[str, Any] = {
                "kind": TUI_AUDIT_LEDGER_INDEX_KIND,
                "schema_version": TUI_AUDIT_LEDGER_INDEX_SCHEMA_VERSION,
                "seq": seq,
                "run_id": run_id,
                "timestamp": timestamp,
                "ledger_file": ledger_path.name,
                "event_count": event_count,
                "ledger_head_digest": head_digest,
                "prev_digest": prev_digest,
            }
            entry["entry_digest"] = compute_index_entry_digest(entry)

            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()
            # The index anchors files that survive a crash; an anchor lost to one is no anchor.
            os.fsync(handle.fileno())

    return entry


def validate_master_index(index_path: Path, *, cross_check: bool = True) -> list[str]:
    """Re-check the index chain and, by default, every run it anchors. Empty means valid.

    `cross_check` walks out to each named ledger and re-derives its head digest and event count.
    That is where the restored property actually lives: the chain alone proves the index was not
    edited, and says nothing about whether the runs it names still exist.

    Ledgers on disk with no index line are deliberately not reported. That is what a crashed run
    leaves behind, and an integrity check that fires on ordinary crashes is one nobody reads.
    """
    if not index_path.exists():
        return [f"File {index_path} does not exist"]

    lines = [ln for ln in index_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return [f"{index_path} contains no entries; an empty index cannot be reported as valid"]

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
            errors.append(f"{where}: index entry must be a JSON object")
            return errors

        missing = [f for f in _INDEX_REQUIRED_FIELDS if f not in entry]
        if missing:
            errors.append(f"{where}: missing required field(s): {', '.join(missing)}")
            return errors

        if entry["kind"] != TUI_AUDIT_LEDGER_INDEX_KIND:
            errors.append(f"{where}: invalid kind: expected {TUI_AUDIT_LEDGER_INDEX_KIND!r}, got {entry['kind']!r}")
        if entry["schema_version"] != TUI_AUDIT_LEDGER_INDEX_SCHEMA_VERSION:
            errors.append(
                f"{where}: invalid schema_version: expected {TUI_AUDIT_LEDGER_INDEX_SCHEMA_VERSION}, "
                f"got {entry['schema_version']!r}"
            )
        if entry["seq"] != index:
            errors.append(f"{where}: seq {entry['seq']!r} does not match position {index}; entries reordered or dropped")

        if entry["prev_digest"] != expected_prev:
            if index == 0:
                errors.append(f"{where}: first entry must have prev_digest {GENESIS_PREV_DIGEST!r}")
            else:
                errors.append(
                    f"{where}: index chain broken -- prev_digest {entry['prev_digest']!r} does not "
                    f"match the previous entry's entry_digest {expected_prev!r}; a run record was "
                    f"deleted, reordered, or rewritten"
                )

        recomputed = compute_index_entry_digest(entry)
        if entry["entry_digest"] != recomputed:
            errors.append(
                f"{where}: entry_digest does not match the entry's contents "
                f"(recorded {entry['entry_digest']!r}, recomputed {recomputed!r})"
            )

        if cross_check:
            errors.extend(_cross_check_run(index_path, entry, where))

        expected_prev = entry["entry_digest"]

    return errors


def _cross_check_run(index_path: Path, entry: dict[str, Any], where: str) -> list[str]:
    """Re-derive one anchored run's head digest and event count from the file itself."""
    ledger = index_path.parent / str(entry["ledger_file"])
    if not ledger.exists():
        return [
            f"{where}: run {entry['run_id']!r} is indexed but its ledger {entry['ledger_file']!r} "
            f"is missing -- a whole run's record was deleted"
        ]

    try:
        event_count, head_digest = read_ledger_summary(ledger)
    except ValueError as exc:
        return [f"{where}: run {entry['run_id']!r} has an unreadable ledger: {exc}"]

    errors: list[str] = []
    if head_digest != entry["ledger_head_digest"]:
        errors.append(
            f"{where}: run {entry['run_id']!r} head digest does not match the index "
            f"(indexed {entry['ledger_head_digest']!r}, on disk {head_digest!r}); its events were "
            f"rewritten after the run completed"
        )
    if event_count != entry["event_count"]:
        errors.append(
            f"{where}: run {entry['run_id']!r} has {event_count} events but the index recorded "
            f"{entry['event_count']}; events were added or truncated after the run completed"
        )
    return errors


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
