import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.config import Settings

TargetName = Literal["generic", "builder", "core"]

TARGET_PROFILE_ARTIFACT_KIND = "builder_ii.target_profile"
TARGET_PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TargetProfile:
    name: TargetName
    description: str
    repo: Path
    context_defaults: tuple[str, ...]
    verification_hints: tuple[str, ...]
    principles: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def to_artifact_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": TARGET_PROFILE_ARTIFACT_KIND,
            "schema_version": TARGET_PROFILE_SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "repo": str(self.repo),
            "context_defaults": list(self.context_defaults),
            "verification_hints": list(self.verification_hints),
            "principles": list(self.principles),
            "notes": list(self.notes),
            "governance": {
                "capability_state": "target_profile_artifact",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }
        # V.4: CORE-only extension block (isolated; never on generic/builder).
        if self.name == "core":
            from builder_ii.targets.core import core_profile_block

            payload["core_profile"] = core_profile_block()
        return payload


_GENERIC_CONTEXT_DEFAULTS = (
    "README.md",
    "pyproject.toml",
    "package.json",
    "src",
    "tests",
    "docs",
)

_BUILDER_CONTEXT_DEFAULTS = (
    "README.md",
    "docs/ROADMAP.md",
    "docs/TOOLING.md",
    "builder_ii",
    "recipes",
    "tests",
)

_CORE_CONTEXT_DEFAULTS = (
    "README.md",
    "AGENTS.md",
    "GROK.md",
    "CLAUDE.md",
    "docs",
    "tests",
)


def target_names() -> tuple[TargetName, ...]:
    return ("generic", "builder", "core")


def _existing_defaults(repo: Path, defaults: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in defaults if (repo / path).exists())


def build_target_profiles(settings: Settings, *, generic_repo: Path | None = None) -> tuple[TargetProfile, ...]:
    generic_root = (generic_repo or Path.cwd()).resolve()
    builder_root = settings.project_root.resolve()
    core_root = settings.target_repo.resolve()
    return (
        TargetProfile(
            name="generic",
            description="Generic software repository target with no project-specific doctrine.",
            repo=generic_root,
            context_defaults=_existing_defaults(generic_root, _GENERIC_CONTEXT_DEFAULTS),
            verification_hints=("inspect project config", "run the smallest relevant tests"),
            principles=("stay repo-local", "prefer minimal patches", "do not invent project policy"),
        ),
        TargetProfile(
            name="builder",
            description="builder-II self-development target profile.",
            repo=builder_root,
            context_defaults=_existing_defaults(builder_root, _BUILDER_CONTEXT_DEFAULTS),
            verification_hints=(
                "uv run pytest -q",
                "uv run builder-targets list",
                "uv run builder-context pack --target builder --no-repomix",
            ),
            principles=(
                "generic-first platform behavior",
                "no CORE Workbench identity",
                "no autonomous writes by default",
                "deepagents remains optional until proven",
            ),
        ),
        TargetProfile(
            name="core",
            description="AssetOverflow/core target profile. CORE is a target, not builder-II identity.",
            repo=core_root,
            context_defaults=_existing_defaults(core_root, _CORE_CONTEXT_DEFAULTS),
            verification_hints=(
                "builder verify <changed-path>",
                "run focused pytest suites",
                "preserve CORE invariants",
                "use builder-targets doctor core for isolation checks",
            ),
            principles=(
                "treat CORE as target profile only",
                "do not conflate with CORE Workbench/UI",
                "preserve deterministic verification discipline",
                "surface uncertainty and refusal boundaries",
                "CORE invariants/semgrep catalogs stay under builder_ii.targets.core",
            ),
            notes=(
                "CORE-specific behavior must remain isolated in this target profile.",
                "V.4: core_profile block carries invariants, verification routing defaults, "
                "safe path categories, and semgrep rule catalogs (catalog only; not execution).",
            ),
        ),
    )


def target_profile(settings: Settings, name: TargetName, *, generic_repo: Path | None = None) -> TargetProfile:
    profiles = {profile.name: profile for profile in build_target_profiles(settings, generic_repo=generic_repo)}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown target profile: {name}") from exc


def validate_target_profiles(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    profiles = build_target_profiles(settings)
    seen: set[str] = set()
    for profile in profiles:
        if profile.name in seen:
            errors.append(f"duplicate target profile: {profile.name}")
        seen.add(profile.name)
        if not profile.description:
            errors.append(f"target profile {profile.name} missing description")
        if not profile.principles:
            errors.append(f"target profile {profile.name} missing principles")
        if profile.name in {"builder", "core"} and not profile.repo.exists():
            errors.append(f"target profile {profile.name} repo missing: {profile.repo}")
    for expected in target_names():
        if expected not in seen:
            errors.append(f"missing target profile: {expected}")
    return tuple(errors)


def render_target_profile(profile: TargetProfile) -> str:
    lines = [
        f"# Target profile: {profile.name}",
        "",
        profile.description,
        "",
        "## Repository",
        "",
        f"`{profile.repo}`",
        "",
        "## Context defaults",
        "",
    ]
    lines.extend(f"- `{path}`" for path in profile.context_defaults) if profile.context_defaults else lines.append(
        "(none found)"
    )
    lines.extend(["", "## Verification hints", ""])
    lines.extend(f"- {hint}" for hint in profile.verification_hints)
    lines.extend(["", "## Principles", ""])
    lines.extend(f"- {principle}" for principle in profile.principles)
    if profile.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in profile.notes)
    if profile.name == "core":
        from builder_ii.targets.core import core_profile_block

        block = core_profile_block()
        lines.extend(
            [
                "",
                "## CORE profile (V.4 isolation)",
                "",
                f"- isolation: `{block['isolation']}`",
                f"- workbench_coupling: `{block['workbench_coupling']}`",
                f"- grants_runtime_authority: `{block['grants_runtime_authority']}`",
                f"- platform_identity: `{block['platform_identity']}`",
                f"- promotion_state: `{block['promotion_state']}`",
                "",
                "### Invariants",
                "",
            ]
        )
        for inv in block["invariants"]:
            lines.append(f"- `{inv['id']}`: {inv['statement']}")
        lines.extend(["", "### Verification routing defaults", ""])
        routing = block["verification_routing_defaults"]
        lines.append(f"- default_verification_profile: `{routing['default_verification_profile']}`")
        for cmd in routing["preferred_commands"]:
            lines.append(f"- preferred: {cmd}")
        lines.extend(["", "### Safe file path categories", ""])
        for cat, paths in block["safe_file_path_categories"].items():
            lines.append(f"- **{cat}**: {', '.join(f'`{p}`' for p in paths)}")
        lines.extend(
            [
                "",
                "### Semgrep rules catalog (not executed by this profile)",
                "",
            ]
        )
        for rule in block["semgrep_rules_catalog"]:
            lines.append(f"- `{rule['id']}` ({rule['severity']}): {rule['intent']}")
    lines.append("")
    return "\n".join(lines)


def dumps_target_profile_artifact(profile: TargetProfile) -> str:
    return json_lib.dumps(profile.to_artifact_dict(), indent=2, sort_keys=True) + "\n"


def write_target_profile_artifact(profile: TargetProfile, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_target_profile_artifact(profile), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_target_profile_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["target profile artifact must be a JSON object"]
    if data.get("kind") != TARGET_PROFILE_ARTIFACT_KIND:
        errors.append(f"kind must be {TARGET_PROFILE_ARTIFACT_KIND}")
    if data.get("schema_version") != TARGET_PROFILE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {TARGET_PROFILE_SCHEMA_VERSION}")
    if data.get("name") not in target_names():
        errors.append("name must be a known target profile")

    for field in ("description", "repo"):
        if not isinstance(data.get(field), str) or not data.get(field):
            errors.append(f"{field} must be a non-empty string")

    for list_field in ("context_defaults", "verification_hints", "principles", "notes"):
        errors.extend(_string_list_errors(data.get(list_field), field=list_field))

    governance = data.get("governance")

    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "target_profile_artifact":
            errors.append("governance.capability_state must be target_profile_artifact")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    # V.4: CORE artifacts must carry the isolated core_profile block; others must not.
    if data.get("name") == "core":
        from builder_ii.targets.core import validate_core_profile_block

        if "core_profile" not in data:
            errors.append("core target profile artifact requires core_profile block")
        else:
            errors.extend(validate_core_profile_block(data.get("core_profile")))
    elif "core_profile" in data:
        errors.append("core_profile is only valid on the core target profile")
    return errors


def validate_target_profile_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_target_profile_artifact(data)
