"""Seam stub for the proprietary CodeVault receipt bridge.

Re-exports the real surface of ``builder_ii_code_vault.code_vault_receipt_bridge``
when the commercial plugin is installed; otherwise every callable refuses with
an explicit upgrade message. The re-export list must name the plugin's real
public API — a guessed name would make this stub fall back to refusal even with
the plugin installed (the plugin suite's seam-drift test pins this).

Kind constants stay available in both states: kind strings are data contracts,
and naming an artifact kind must not require the capability that produces it.
"""

from __future__ import annotations

CODE_VAULT_UPGRADE_MESSAGE = "CodeVault is not installed. Please upgrade."

try:
    from builder_ii_code_vault.code_vault_receipt_bridge import (
        CODE_VAULT_CORROBORATION_RECORD_KIND,
        CODE_VAULT_CORROBORATION_RECORD_SCHEMA_VERSION,
        build_code_vault_corroboration_record,
        dumps_code_vault_corroboration_record,
        validate_code_vault_corroboration_record,
        validate_code_vault_corroboration_record_against_sources,
        validate_code_vault_corroboration_record_file,
        write_code_vault_corroboration_record,
    )
except ImportError:
    CODE_VAULT_CORROBORATION_RECORD_KIND = "builder_ii.code_vault_corroboration_record"
    CODE_VAULT_CORROBORATION_RECORD_SCHEMA_VERSION = 1

    def _refuse(*args: object, **kwargs: object) -> None:
        raise RuntimeError(CODE_VAULT_UPGRADE_MESSAGE)

    build_code_vault_corroboration_record = _refuse
    dumps_code_vault_corroboration_record = _refuse
    validate_code_vault_corroboration_record = _refuse
    validate_code_vault_corroboration_record_against_sources = _refuse
    validate_code_vault_corroboration_record_file = _refuse
    write_code_vault_corroboration_record = _refuse
