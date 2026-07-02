from __future__ import annotations

import os
import re
from dataclasses import dataclass

from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT, REQUIRED_INIT_LITERALS

# NOTE: This module is a narrow refusal-probe helper (specifically for refusal testing
# of CORE-specific patterns in vault/store.py and related invariants). It is NOT a
# comprehensive security or compliance engine for the entire platform.

FORBIDDEN_PROPOSAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "cosine_in_vault",
        re.compile(r"cosine\s+similar", re.IGNORECASE),
    ),
    (
        "hnsw_recall",
        re.compile(r"\bHNSW\b|\bANN\b", re.IGNORECASE),
    ),
    (
        "hot_path_normalization",
        re.compile(
            r"normalize.*vault/store\.py|vault/store\.py.*normalize",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class ComplianceReport:
    init_literals_ok: bool
    missing_literals: tuple[str, ...]
    init_token_estimate: int
    refusal_probe_ok: bool
    refusal_reason: str


def check_init_artifact(text: str = CORE_INIT_SYSTEM_PROMPT) -> tuple[bool, tuple[str, ...]]:
    missing = tuple(lit for lit in REQUIRED_INIT_LITERALS if lit not in text)
    return len(missing) == 0, missing


def refusal_response_for(text: str, target_profile: str | None = None) -> str | None:
    """Return a governed refusal message when a forbidden pattern is detected.

    CORE-specific rules are isolated and only run when target_profile is "core".
    """
    if target_profile is None:
        target_profile = os.environ.get("BUILDER_TARGET_PROFILE", "generic")

    if target_profile != "core":
        return None

    # CORE-specific checks
    if re.search(r"cosine\s+similar", text, re.IGNORECASE) and "vault" in text.lower():
        return (
            "REFUSE: cosine similarity in vault/store.py violates the exact-recall "
            "invariant. Vault recall must use cga_inner only; versor_condition(F) < 1e-6 "
            "must hold. No ANN/HNSW/cosine approximate recall in runtime paths."
        )
    for _name, pattern in FORBIDDEN_PROPOSAL_PATTERNS:
        if pattern.search(text):
            return (
                "REFUSE: proposal matches a forbidden CORE pattern. "
                "See AGENTS.md invariants and versor_condition(F) < 1e-6."
            )
    return None


def run_compliance_checks(target_profile: str | None = None) -> ComplianceReport:
    ok, missing = check_init_artifact()
    probe = "add cosine similarity to vault/store.py for faster recall"
    # To check that the refusal engine is operational, we probe with target_profile="core"
    refusal = refusal_response_for(probe, target_profile="core")
    return ComplianceReport(
        init_literals_ok=ok,
        missing_literals=missing,
        init_token_estimate=max(1, len(CORE_INIT_SYSTEM_PROMPT) // 4),
        refusal_probe_ok=refusal is not None and "versor_condition" in refusal,
        refusal_reason=refusal or "no refusal generated",
    )
