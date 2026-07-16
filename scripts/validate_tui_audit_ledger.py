#!/usr/bin/env python3
"""Validator for the TUI audit ledger.

kind: builder_ii.tui_audit_ledger_event

Re-checks every event's schema, recomputes both digests, and walks the `prev_digest` chain so a
deleted, reordered or rewritten line is reported rather than assumed absent. Sibling of
`scripts/validate_tui_exploration.py`, which validates `builder_ii.tui_exploration_report`; like
that one this is a plain script rather than a `builder-*` console script, so it adds no entry to
`[project.scripts]` and therefore no `command_authority.py` surface -- the same reasoning
`gate_battery_receipt` records for its own `python -m` validator.

Usage:
    uv run python scripts/validate_tui_audit_ledger.py .builder/artifacts/tui_audit_ledger.jsonl
"""
import argparse
import sys
from pathlib import Path

from builder_ii.tui_audit_ledger import validate_ledger


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a builder_ii.tui_audit_ledger_event JSONL ledger.")
    parser.add_argument("ledger_path", type=Path, help="Path to the .jsonl ledger file.")
    args = parser.parse_args()

    errors = validate_ledger(args.ledger_path)
    if errors:
        print(f"Validation failed for {args.ledger_path}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"Artifact {args.ledger_path} is valid.")
    sys.exit(0)


if __name__ == "__main__":
    main()
