from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuiteRoute:
    module_prefix: str
    suite: str
    rationale: str


# Immutable routing table: module path prefix -> CORE CLI suite alias.
MODULE_SUITE_ROUTES: tuple[SuiteRoute, ...] = (
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
)


def suite_for_module(module_path: str) -> str:
    """Return the smallest relevant CORE test suite for a module path."""
    normalized = module_path.replace("\\", "/").lstrip("./")
    for route in MODULE_SUITE_ROUTES:
        if normalized.startswith(route.module_prefix) or normalized == route.module_prefix.rstrip("/"):
            return route.suite
    return "smoke"


def routing_table_text() -> str:
    lines = ["module_prefix -> suite:"]
    for route in MODULE_SUITE_ROUTES:
        lines.append(f"  {route.module_prefix} -> {route.suite}")
    return "\n".join(lines)