"""Entry point for running the TUI directly."""

from builder_ii.tui.app import StratumApp

if __name__ == "__main__":
    app = StratumApp()
    app.run()
