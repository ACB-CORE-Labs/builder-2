"""Validated, non-authoritative onboarding preset configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from builder_ii.governance.ratification_points import RATIFICATION_POINTS, grant_eligibility
from builder_ii.governance.ratification_policy import LEVEL_DELEGABLE, effective_level

PRESET_KIND = "builder_ii.onboarding_preset_configuration"
PRESET_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Preset:
    name: str
    worker_concurrency: int
    confirmation_policy: str
    routing_preference: str
    requires_explicit_model_budget: bool = False
    suggests_eligible_standing_grants: bool = False


PRESETS = {
    "solo-fast": Preset("solo-fast", 2, "eligible-boundaries", "local-first-economical", False, True),
    "solo-strict": Preset("solo-strict", 1, "every-human-boundary", "explicit-only"),
    "team": Preset("team", 2, "explicit-human-boundaries", "explicit-model-budget", True),
}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown onboarding preset: {name}") from exc


def _standing_grant_suggestions(*, root: Path) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    for point in RATIFICATION_POINTS:
        eligibility = grant_eligibility(point)
        policy = effective_level(point.id, root=root)
        if eligibility.eligible and policy.level == LEVEL_DELEGABLE:
            suggestions.append({"point_id": point.id, "because": eligibility.because})
    return suggestions


def preset_artifact(
    name: str,
    *,
    root: Path = Path("."),
    model_backend: str | None = None,
    model_alias: str | None = None,
    budget_usd: float | None = None,
) -> dict[str, Any]:
    preset = get_preset(name)
    if preset.requires_explicit_model_budget:
        if not model_backend or not model_alias:
            raise ValueError("team preset requires explicit model backend and model alias")
        if budget_usd is None or budget_usd <= 0:
            raise ValueError("team preset requires a positive explicit budget")
    data: dict[str, Any] = {
        "kind": PRESET_KIND,
        "schema_version": PRESET_SCHEMA_VERSION,
        **asdict(preset),
        "model_backend": model_backend or "selected-onboarding-decision",
        "model_alias": model_alias or "selected-onboarding-decision",
        "budget_usd": budget_usd,
        "standing_grant_suggestions": (
            _standing_grant_suggestions(root=root) if preset.suggests_eligible_standing_grants else []
        ),
        "authority": "configuration_only",
        "grants_authority": False,
        "promotes": False,
        "enables_forbidden_tools": False,
        "bypasses_budget_policy": False,
    }
    errors = validate_preset_artifact(data)
    if errors:
        raise ValueError("invalid onboarding preset configuration: " + "; ".join(errors))
    return data


def validate_preset_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["onboarding preset must be a JSON object"]
    if data.get("kind") != PRESET_KIND:
        errors.append(f"kind must be {PRESET_KIND}")
    if data.get("schema_version") != PRESET_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PRESET_SCHEMA_VERSION}")
    if data.get("name") not in PRESETS:
        errors.append("name must be solo-fast, solo-strict, or team")
    concurrency = data.get("worker_concurrency")
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or not 1 <= concurrency <= 2:
        errors.append("worker_concurrency must be an integer from 1 through 2")
    if data.get("authority") != "configuration_only":
        errors.append("authority must be configuration_only")
    for field in ("grants_authority", "promotes", "enables_forbidden_tools", "bypasses_budget_policy"):
        if data.get(field) is not False:
            errors.append(f"{field} must be false")
    suggestions = data.get("standing_grant_suggestions")
    if not isinstance(suggestions, list):
        errors.append("standing_grant_suggestions must be a list")
    elif data.get("name") != "solo-fast" and suggestions:
        errors.append("only solo-fast may suggest eligible standing grants")
    elif any(not isinstance(item, dict) or not item.get("point_id") for item in suggestions):
        errors.append("standing_grant_suggestions entries must name a point_id")
    if data.get("name") == "team":
        if data.get("model_backend") in (None, "", "selected-onboarding-decision"):
            errors.append("team model_backend must be explicit")
        if data.get("model_alias") in (None, "", "selected-onboarding-decision"):
            errors.append("team model_alias must be explicit")
        budget = data.get("budget_usd")
        if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget <= 0:
            errors.append("team budget_usd must be positive")
    return errors
