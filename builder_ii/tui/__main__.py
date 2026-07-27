"""Entry point for running the TUI directly."""

from __future__ import annotations

import sys


def main() -> int:
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.tui.app import StratumApp, run_tui

    enforce_command_authority("builder stratum")
    return run_tui(StratumApp())


if __name__ == "__main__":
    sys.exit(main())
