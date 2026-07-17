"""Entry point for running the TUI directly."""

import sys

from builder_ii.tui.app import StratumApp, run_tui

if __name__ == "__main__":
    sys.exit(run_tui(StratumApp()))
