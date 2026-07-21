from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from builder_ii.governance.authority.role_gates import (
    CAPABILITY_DIRECT_ASK,
    CAPABILITY_FILE_EDITING,
    CAPABILITY_GOOSE_TOOL_EXECUTION,
    CAPABILITY_HEAVY_MODEL_ROUTING,
    CAPABILITY_RUNTIME_SWITCH,
    gate_for,
)
from builder_ii.governance.authority.roles import builder_roles
from builder_ii.lifecycle.setup.lane_guides import get_guide, render_guide

CheckStatus = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class LaneCheckResult:
    role: str
    guide: str
    check: str
    status: CheckStatus
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class LaneCheckReport:
    results: tuple[LaneCheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)

    @property
    def failures(self) -> tuple[LaneCheckResult, ...]:
        return tuple(result for result in self.results if not result.ok)


def _pass(role: str, guide: str, check: str, detail: str) -> LaneCheckResult:
    return LaneCheckResult(role, guide, check, "PASS", detail)


def _fail(role: str, guide: str, check: str, detail: str) -> LaneCheckResult:
    return LaneCheckResult(role, guide, check, "FAIL", detail)


def check_role_lane_pair(
    role_name: str, guide_name: str, *, sample_context: str = "offline lane check context"
) -> tuple[LaneCheckResult, ...]:
    role = next(role for role in builder_roles() if role.name == role_name)
    guide = get_guide(guide_name)
    prompt = render_guide(guide_name, context=sample_context)
    results: list[LaneCheckResult] = []

    if guide_name in role.lane_guides:
        results.append(_pass(role_name, guide_name, "role references guide", "role declares the guide"))
    else:
        results.append(_fail(role_name, guide_name, "role references guide", "role does not declare the guide"))

    if role.model_alias == guide.model_alias:
        results.append(_pass(role_name, guide_name, "model alignment", role.model_alias))
    else:
        results.append(
            _fail(role_name, guide_name, "model alignment", f"role={role.model_alias} guide={guide.model_alias}")
        )

    if sample_context in prompt:
        results.append(_pass(role_name, guide_name, "prompt renders context", "sample context rendered"))
    else:
        results.append(_fail(role_name, guide_name, "prompt renders context", "sample context missing"))

    if role.output_contract.split(",")[0].strip() in prompt or role.output_contract.split(".")[0].strip() in prompt:
        results.append(_pass(role_name, guide_name, "contract visible", "role contract appears in rendered prompt"))
    else:
        results.append(_fail(role_name, guide_name, "contract visible", "role contract not visible in rendered prompt"))

    if gate_for(role_name, CAPABILITY_DIRECT_ASK).status == "ALLOWED":
        results.append(_pass(role_name, guide_name, "direct ask gate", "direct ask is allowed"))
    else:
        results.append(_fail(role_name, guide_name, "direct ask gate", "direct ask is not allowed"))

    if gate_for(role_name, CAPABILITY_GOOSE_TOOL_EXECUTION).status == "UNSUPPORTED":
        results.append(_pass(role_name, guide_name, "tool execution gate", "tool execution remains unsupported"))
    else:
        results.append(
            _fail(role_name, guide_name, "tool execution gate", "tool execution is not explicitly unsupported")
        )

    if gate_for(role_name, CAPABILITY_HEAVY_MODEL_ROUTING).status == "FORBIDDEN":
        results.append(_pass(role_name, guide_name, "heavy routing gate", "heavy routing remains forbidden"))
    else:
        results.append(_fail(role_name, guide_name, "heavy routing gate", "heavy routing is not forbidden"))

    if role_name in {"failure_reviewer", "invariant_auditor", "diff_summarizer"}:
        expected = "FORBIDDEN"
    else:
        expected = "OPERATOR_ONLY"
    actual = gate_for(role_name, CAPABILITY_FILE_EDITING).status
    if actual == expected:
        results.append(_pass(role_name, guide_name, "file edit gate", actual))
    else:
        results.append(_fail(role_name, guide_name, "file edit gate", f"expected={expected} actual={actual}"))

    if role_name in {"invariant_auditor", "lane_router"}:
        expected_runtime = "FORBIDDEN"
    else:
        expected_runtime = "OPERATOR_ONLY"
    actual_runtime = gate_for(role_name, CAPABILITY_RUNTIME_SWITCH).status
    if actual_runtime == expected_runtime:
        results.append(_pass(role_name, guide_name, "runtime switch gate", actual_runtime))
    else:
        results.append(
            _fail(role_name, guide_name, "runtime switch gate", f"expected={expected_runtime} actual={actual_runtime}")
        )

    return tuple(results)


def run_lane_checks() -> LaneCheckReport:
    results: list[LaneCheckResult] = []
    for role in builder_roles():
        for guide_name in role.lane_guides:
            results.extend(check_role_lane_pair(role.name, guide_name))
    return LaneCheckReport(tuple(results))
