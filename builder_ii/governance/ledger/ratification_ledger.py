"""Hash-chained record of every ratification decision: granted, revoked, auto-accepted, typed.

The grant mechanism removes prompts. This ledger is the reason that is not the same as removing
accountability: for any confirmation that did not stop to ask, there is a line here naming the
point, the grant that satisfied it, and when -- and for any confirmation that did stop, a line
saying a human typed it. "What was auto-accepted, under whose delegation" is answerable after
the fact, which is the whole trade the operator is being offered.

CHAIN SHAPE, and why it is this one:

``entry_digest`` covers the entire entry **including** ``prev_digest``, which is what makes the
chain a chain. Digesting the payload alone and storing ``prev_digest`` beside it as a bare link
would leave every digest still verifying after line N was deleted and line N+1 re-pointed at
line N-1 -- a forgeable chain that looks intact. This is the same mistake, and the same fix,
recorded in :mod:`builder_ii.governance.ledger.tui_audit_ledger`.

Unlike a per-run TUI ledger, this file is inherently **shared**: `builder-setup apply` in one
terminal and `builder-govern grant-auto` in another append to the same chain. Concurrent
read-tail-then-append forks it, and a forked chain is indistinguishable from a tampered one, so
:func:`append_ratification_event` holds an exclusive ``flock`` across the whole read-and-append
and refuses to run at all where ``fcntl`` is unavailable. Degrading silently to the unlocked
path would reintroduce the fork on exactly the platform nobody is watching.

RECORDED_ONLY. The same process that takes the action writes the line, so this is a receipt and
never independent proof: it closes "which confirmations were delegated and when", not "was the
operator honest". Its ``governance`` block says so on every entry.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

try:  # pragma: no cover - platform guard, exercised by the RuntimeError branch
    import fcntl
except ImportError:  # pragma: no cover - macOS and Linux both have fcntl
    fcntl = None  # type: ignore[assignment]

from builder_ii.core.canonical_json import canonical_json

RATIFICATION_LEDGER_KIND = "builder_ii.ratification_ledger_event"
RATIFICATION_LEDGER_SCHEMA_VERSION = 1
RATIFICATION_LEDGER_FILENAME = "ratification_ledger.jsonl"

#: `prev_digest` of the first line in a file. A literal marker distinguishes "start of chain"
#: from "link missing", which `None` alone cannot.
GENESIS_PREV_DIGEST = "genesis"

EVENT_GRANT_CREATED = "grant_created"
EVENT_GRANT_REVOKED = "grant_revoked"
EVENT_AUTO_ACCEPTED = "auto_accepted"
EVENT_MANUAL_RATIFIED = "manual_ratified"
EVENT_APPROVAL_MINTED = "approval_minted"
EVENT_APPROVAL_ACCEPTED = "approval_accepted"
EVENT_POLICY_SET = "policy_set"

RATIFICATION_EVENTS: tuple[str, ...] = (
    EVENT_GRANT_CREATED,
    EVENT_GRANT_REVOKED,
    EVENT_AUTO_ACCEPTED,
    EVENT_MANUAL_RATIFIED,
    EVENT_APPROVAL_MINTED,
    EVENT_APPROVAL_ACCEPTED,
    EVENT_POLICY_SET,
)


def ledger_path(root: Path) -> Path:
    return Path(root) / RATIFICATION_LEDGER_FILENAME


def compute_entry_digest(entry: dict[str, Any]) -> str:
    """Digest of the entry excluding ``entry_digest`` itself; commits to ``prev_digest``."""
    core = {key: value for key, value in entry.items() if key != "entry_digest"}
    return hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()


def build_ratification_event(
    *,
    event: str,
    point_id: str,
    command: str,
    seq: int,
    prev_digest: str,
    actor: str,
    because: str,
    grant_digest: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build one chained ledger entry. ``entry_digest`` is computed last and covers everything."""
    entry: dict[str, Any] = {
        "kind": RATIFICATION_LEDGER_KIND,
        "schema_version": RATIFICATION_LEDGER_SCHEMA_VERSION,
        "seq": seq,
        "event": event,
        "point_id": point_id,
        "command": command,
        "grant_digest": grant_digest,
        "actor": actor,
        "because": because,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "governance": {
            "artifact_is_authority": False,
            "independent_observer": False,
            "capability_state": "recorded_only",
        },
        "prev_digest": prev_digest,
    }
    entry["entry_digest"] = compute_entry_digest(entry)
    return entry


@contextmanager
def _exclusive(handle: IO[str]) -> Iterator[None]:
    """Hold an exclusive advisory lock on ``handle`` for the duration of the block.

    Advisory suffices because every writer of this file goes through
    :func:`append_ratification_event`, which always takes the lock. It is not sufficient against
    an editor or a shell redirect -- this ledger is tamper-evident, not tamper-proof.
    """
    if fcntl is None:  # pragma: no cover - macOS and Linux both have fcntl
        raise RuntimeError(
            "fcntl.flock is unavailable on this platform; refusing to append to the ratification "
            "ledger unlocked, because concurrent appends fork the chain and the fork is "
            "indistinguishable from tampering"
        )
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_chain_head(handle: IO[str]) -> tuple[int, str]:
    """Return ``(next_seq, prev_digest)`` from an already-open, already-locked handle.

    Takes the handle rather than the path on purpose: reading the tail in a separate open would
    put the read outside the lock, which is the race this whole function exists inside of.
    """
    handle.seek(0)
    last: str | None = None
    for line in handle:
        if line.strip():
            last = line
    if last is None:
        return 0, GENESIS_PREV_DIGEST
    try:
        entry = json.loads(last)
    except json.JSONDecodeError as exc:
        raise ValueError("ratification ledger: last line is not valid JSON; refusing to fork the chain") from exc
    digest = entry.get("entry_digest")
    seq = entry.get("seq")
    if not isinstance(digest, str) or not isinstance(seq, int):
        raise ValueError("ratification ledger: last line has no usable entry_digest/seq; refusing to fork the chain")
    return seq + 1, digest


def append_ratification_event(
    root: Path,
    *,
    event: str,
    point_id: str,
    command: str,
    actor: str,
    because: str,
    grant_digest: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append one chained event, holding an exclusive lock across read-tail-then-append."""
    if event not in RATIFICATION_EVENTS:
        raise ValueError(f"unknown ratification ledger event: {event!r}")
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        with _exclusive(handle):
            seq, prev_digest = _read_chain_head(handle)
            entry = build_ratification_event(
                event=event,
                point_id=point_id,
                command=command,
                seq=seq,
                prev_digest=prev_digest,
                actor=actor,
                because=because,
                grant_digest=grant_digest,
                timestamp=timestamp,
            )
            handle.seek(0, 2)
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_ratification_events(root: Path) -> list[dict[str, Any]]:
    """Every event in the ledger, in file order. Missing file is an empty history, not an error."""
    path = ledger_path(root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            events.append(entry)
    return events


def validate_ratification_ledger(root: Path) -> list[str]:
    """Chain-integrity errors: recomputed digests, sequence continuity, and link continuity.

    Reports every break rather than the first, so a single run names the whole damaged region
    instead of making the operator re-run after each fix.
    """
    events = read_ratification_events(root)
    errors: list[str] = []
    expected_prev = GENESIS_PREV_DIGEST
    for index, entry in enumerate(events):
        if entry.get("kind") != RATIFICATION_LEDGER_KIND:
            errors.append(f"line {index + 1}: kind must be {RATIFICATION_LEDGER_KIND!r}")
            continue
        if entry.get("seq") != index:
            errors.append(f"line {index + 1}: seq is {entry.get('seq')!r}, expected {index}")
        if entry.get("prev_digest") != expected_prev:
            errors.append(
                f"line {index + 1}: prev_digest is {str(entry.get('prev_digest'))[:12]!r}, "
                f"expected {str(expected_prev)[:12]!r}"
            )
        recomputed = compute_entry_digest(entry)
        if entry.get("entry_digest") != recomputed:
            errors.append(f"line {index + 1}: entry_digest does not match recomputed digest")
        expected_prev = str(entry.get("entry_digest", ""))
    return errors
