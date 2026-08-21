"""Non-authoritative onboarding presets."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    concurrency: int
    confirmation: str
    routing: str
    standing_grant_suggestion: bool = False


PRESETS = {
    "solo-fast": Preset("solo-fast", 2, "eligible-boundaries", "local-first-economical", True),
    "solo-strict": Preset("solo-strict", 1, "every-human-boundary", "explicit-only"),
    "team": Preset("team", 2, "explicit-human-boundaries", "explicit-model-budget"),
}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown onboarding preset: {name}") from exc


def preset_artifact(name: str) -> dict[str, object]:
    data = asdict(get_preset(name))
    data.update({"authority": "configuration_only", "promotes": False, "enables_forbidden_tools": False})
    return data
