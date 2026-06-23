from __future__ import annotations

import re
from dataclasses import dataclass

from core_agent.init_content import CORE_INIT_SYSTEM_PROMPT, REQUIRED_INIT_LITERALS


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


def refusal_response_for(text: str) -> str | None:
    """Return a governed refusal message when a forbidden pattern is detected."""
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


def run_compliance_checks() -> ComplianceReport:
    ok, missing = check_init_artifact()
    probe = "add cosine similarity to vault/store.py for faster recall"
    refusal = refusal_response_for(probe)
    return ComplianceReport(
        init_literals_ok=ok,
        missing_literals=missing,
        init_token_estimate=max(1, len(CORE_INIT_SYSTEM_PROMPT) // 4),
        refusal_probe_ok=refusal is not None and "versor_condition" in refusal,
        refusal_reason=refusal or "no refusal generated",
    )