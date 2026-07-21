"""Seam stub for the proprietary CodeVault determinism demo loop.

Re-exports the real surface of ``builder_ii_code_vault.code_vault_demo_loop``
when the commercial plugin is installed; otherwise every callable refuses with
an explicit upgrade message. Kind constants stay available in both states:
kind strings are data contracts, and naming an artifact kind must not require
the capability that produces it.
"""

from __future__ import annotations

CODE_VAULT_UPGRADE_MESSAGE = "CodeVault is not installed. Please upgrade."

try:
    from builder_ii_code_vault.code_vault_demo_loop import (
        CODE_VAULT_DEMO_REPORT_KIND,
        create_code_vault_demo_report,
        dumps_code_vault_demo_report,
        run_code_vault_demo_loop,
        validate_code_vault_demo_report,
    )
except ImportError:
    CODE_VAULT_DEMO_REPORT_KIND = "builder_ii.code_vault.determinism_demo_report"

    def _refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError(CODE_VAULT_UPGRADE_MESSAGE)

    create_code_vault_demo_report = _refuse
    dumps_code_vault_demo_report = _refuse
    run_code_vault_demo_loop = _refuse
    validate_code_vault_demo_report = _refuse
