#!/usr/bin/env python3
"""Validator for the TUI audit ledger and its master index.

kind: builder_ii.tui_audit_ledger_event
kind: builder_ii.tui_audit_ledger_index_entry

Re-checks every event's schema, recomputes both digests, and walks the `prev_digest` chain so a
deleted, reordered or rewritten line is reported rather than assumed absent.

Given a directory it also validates the master index (`tui_audit_ledger_index.jsonl`) and
cross-checks every run it anchors, which is the only check that can see a whole run's ledger having
been deleted -- the per-run files cannot miss what is not there. Validating the ledgers alone would
report a directory that had lost half its runs as entirely clean.

This is a plain script rather than a `builder-*` console script, so it adds no entry to
`[project.scripts]` and therefore no `command_authority.py` surface. That is deliberate:
`tests/test_command_authority.py::test_pyproject_scripts_fully_covered` requires every console
script to carry an authority record, and a dev-facing validator should not buy a governed surface
it does not need. Same reasoning `gate_battery_receipt` records for its own `python -m` validator.

The driver writes one ledger per run (`tui_audit_ledger_<run_id>.jsonl`), so a run's file is no
longer at a path anyone can name in advance. This accepts several at once, and accepts the
directory holding them, because "validate the ledgers I just produced" is now a question about a
set of files rather than about one.

Usage:
    uv run python scripts/validate_tui_audit_ledger.py .builder/artifacts/tui_audit_ledger_<run_id>.jsonl
    uv run python scripts/validate_tui_audit_ledger.py .builder/artifacts/   # ledgers + master index
"""
import argparse
import sys
from pathlib import Path

from builder_ii.tui_audit_ledger import MASTER_INDEX_FILENAME, validate_ledger, validate_master_index

#: Matches what `scripts/semantic_tui_driver.py` names its per-run files -- and also the master
#: index, which shares the prefix. The index is excluded by name below rather than by narrowing this
#: pattern: a glob that happened to exclude it (say, by matching only hex) would be relying on a
#: coincidence of spelling, and would silently re-include it the day either name changed. Fed to
#: `validate_ledger` the index reports every field of a perfectly good file as missing.
LEDGER_GLOB = "tui_audit_ledger_*.jsonl"


def _expand(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Split inputs into (per-run ledgers, master indexes); resolve directories to both."""
    ledgers: list[Path] = []
    indexes: list[Path] = []
    for path in paths:
        if path.is_dir():
            ledgers.extend(sorted(p for p in path.glob(LEDGER_GLOB) if p.name != MASTER_INDEX_FILENAME))
            index = path / MASTER_INDEX_FILENAME
            if index.exists():
                indexes.append(index)
        elif path.name == MASTER_INDEX_FILENAME:
            indexes.append(path)
        else:
            ledgers.append(path)
    return ledgers, indexes


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate builder_ii.tui_audit_ledger_event JSONL ledgers.")
    parser.add_argument(
        "ledger_path",
        type=Path,
        nargs="+",
        help=f"Ledger .jsonl file(s), a {MASTER_INDEX_FILENAME}, or a directory holding them.",
    )
    args = parser.parse_args()

    ledgers, indexes = _expand(args.ledger_path)
    if not ledgers and not indexes:
        # A directory holding no ledgers is a failure, not a pass. The module takes the same line
        # on an empty file: "nothing to check" must never be reported as "checked and clean".
        searched = ", ".join(str(p) for p in args.ledger_path)
        print(f"No ledgers found matching {LEDGER_GLOB} in: {searched}")
        sys.exit(1)

    failed = False
    for ledger in ledgers:
        errors = validate_ledger(ledger)
        if errors:
            failed = True
            print(f"Validation failed for {ledger}:")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"Artifact {ledger} is valid.")

    for index in indexes:
        errors = validate_master_index(index)
        if errors:
            failed = True
            print(f"Validation failed for {index}:")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"Master index {index} is valid (every anchored run present and unmodified).")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
