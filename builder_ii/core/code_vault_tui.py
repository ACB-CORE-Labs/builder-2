"""Seam stub for the proprietary CodeVault read-only TUI.

``builder_ii.cli.tui_inspection_cli`` dispatches ``builder code-vault status``
(and frame/recall/lint/context/…) by importing this module and calling its
``main(argv) -> int`` — that name is the dispatch contract, so the stub must
export ``main`` in both install states. With the plugin absent the refusal
prints the upgrade message and exits 1 instead of pretending an inspection ran.
"""

from __future__ import annotations

CODE_VAULT_UPGRADE_MESSAGE = "CodeVault is not installed. Please upgrade."

try:
    from builder_ii_code_vault.code_vault_tui import main
except ImportError:

    def main(argv: list[str] | None = None) -> int:
        print(CODE_VAULT_UPGRADE_MESSAGE)
        return 1
