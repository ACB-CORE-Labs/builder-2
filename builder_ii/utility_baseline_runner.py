"""Seam stub for the proprietary CodeVault U-instrument baseline runner.

Re-exports the real surface of ``builder_ii_code_vault.utility_baseline_runner``
when the commercial plugin is installed; otherwise every callable refuses with
an explicit upgrade message rather than fabricating a baseline arm result.
"""

from __future__ import annotations

CODE_VAULT_UPGRADE_MESSAGE = "CodeVault is not installed. Please upgrade."

try:
    from builder_ii_code_vault.utility_baseline_runner import (
        run_baseline_arm,
        run_context_pack_without_codevault,
        run_grep_arm,
        run_tree_listing,
    )
except ImportError:

    def _refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError(CODE_VAULT_UPGRADE_MESSAGE)

    run_baseline_arm = _refuse
    run_context_pack_without_codevault = _refuse
    run_grep_arm = _refuse
    run_tree_listing = _refuse
