#!/usr/bin/env python3
"""Validator for the TUI audit ledger.

kind: builder_ii.tui_audit_ledger_event

Re-checks every event's schema, recomputes both digests, and walks the `prev_digest` chain so a
deleted, reordered or rewritten line is reported rather than assumed absent.

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
    uv run python scripts/validate_tui_audit_ledger.py .builder/artifacts/      # every ledger in it
"""
import argparse
import sys
from pathlib import Path

from builder_ii.tui_audit_ledger import validate_ledger

#: Matches what `scripts/semantic_tui_driver.py` names its per-run files.
LEDGER_GLOB = "tui_audit_ledger_*.jsonl"


def _expand(paths: list[Path]) -> list[Path]:
    """Resolve directories to the ledgers inside them; leave explicit files alone."""
    resolved: list[Path] = []
    for path in paths:
        if path.is_dir():
            resolved.extend(sorted(path.glob(LEDGER_GLOB)))
        else:
            resolved.append(path)
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate builder_ii.tui_audit_ledger_event JSONL ledgers.")
    parser.add_argument(
        "ledger_path",
        type=Path,
        nargs="+",
        help=f"Ledger .jsonl file(s), or a directory to search for {LEDGER_GLOB}.",
    )
    args = parser.parse_args()

    ledgers = _expand(args.ledger_path)
    if not ledgers:
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

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
