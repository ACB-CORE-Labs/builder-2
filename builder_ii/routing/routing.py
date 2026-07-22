"""Phase 3 – Deterministic Harness: Module → Test Suite Router.

This table is the Verifier half of the Proposer/Verifier loop.
When Goose modifies a file, suite_for_module() maps it to the smallest
relevant CORE test suite — preventing wasted compute on unrelated paths.

Local-model additions (Phase 4):
  qwen-coder edits       → cognition  (strict Python formatting validation)
  deepseek-coder edits   → algebra    (repo-level versor sweeps)
  llama31 edits          → smoke      (system-prompt adherence, lighter load)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuiteRoute:
    module_prefix: str
    suite: str
    rationale: str


# Immutable routing table — order matters: first match wins.
MODULE_SUITE_ROUTES: tuple[SuiteRoute, ...] = (
    # CORE domain modules
    SuiteRoute("algebra/", "algebra", "versor/CGA invariants"),
    SuiteRoute("field/", "algebra", "propagation shares algebra lane"),
    SuiteRoute("generate/", "cognition", "intent/graph/realizer"),
    SuiteRoute("core/cognition/", "cognition", "cognitive turn spine"),
    SuiteRoute("vault/", "teaching", "epistemic store + recall"),
    SuiteRoute("teaching/", "teaching", "reviewed teaching lifecycle"),
    SuiteRoute("calibration/", "cognition", "replay calibration"),
    SuiteRoute("ingest/", "runtime", "injection/runtime"),
    SuiteRoute("session/", "runtime", "session turn loop"),
    SuiteRoute("chat/", "runtime", "ChatRuntime"),
    SuiteRoute("sensorium/", "sensorium", "sensorium compilers"),
    SuiteRoute("language_packs/", "packs", "pack ratification"),
    SuiteRoute("workbench/", "runtime", "workbench API/runtime"),
    SuiteRoute("platform/", "smoke", "platform-only changes"),
    SuiteRoute("scripts/", "smoke", "tooling scripts"),
    SuiteRoute("docs/", "smoke", "docs-only"),
    # Local-model adapter paths (Phase 4)
    SuiteRoute("adapters/qwen/", "cognition", "Qwen-Coder: strict Python formatting validation"),
    SuiteRoute("adapters/deepseek/", "algebra", "DeepSeek: repo-level versor_condition sweeps"),
    SuiteRoute("adapters/llama/", "smoke", "Llama 3.1: system-prompt adherence, lighter load"),
)


def suite_for_module(module_path: str) -> str:
    """Return the smallest relevant CORE test suite for a module path."""
    normalized = module_path.replace("\\", "/").lstrip("./")
    for route in MODULE_SUITE_ROUTES:
        if normalized.startswith(route.module_prefix) or normalized == route.module_prefix.rstrip("/"):
            return route.suite
    return "smoke"


def suite_rationale(module_path: str) -> str:
    """Return the rationale string for CLI reporting."""
    normalized = module_path.replace("\\", "/").lstrip("./")
    for route in MODULE_SUITE_ROUTES:
        if normalized.startswith(route.module_prefix) or normalized == route.module_prefix.rstrip("/"):
            return route.rationale
    return "no specific route — fallback to smoke"


def routing_table_text() -> str:
    lines = ["module_prefix → suite  (rationale):"]
    for route in MODULE_SUITE_ROUTES:
        lines.append(f"  {route.module_prefix:<28} → {route.suite:<12}  # {route.rationale}")
    return "\n".join(lines)
