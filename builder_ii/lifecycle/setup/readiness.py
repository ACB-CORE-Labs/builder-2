"""Passive, bounded onboarding readiness synthesis."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class Readiness:
    name: str
    status: str
    detail: str
    remediation: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _bounded(value: str, limit: int = 2_000) -> str:
    clean = value.strip()
    return clean[-limit:] if len(clean) > limit else clean


def check_gh() -> Readiness:
    path = shutil.which("gh")
    if not path:
        return Readiness(
            "github-cli",
            "unavailable",
            "gh was not found",
            "Install GitHub CLI and authenticate separately; builder init never does this.",
        )
    try:
        proc = subprocess.run([path, "--version"], shell=False, capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired:
        return Readiness(
            "github-cli",
            "failed",
            "gh version probe timed out after 3 seconds",
            "Run `gh --version` and repair the local installation.",
        )
    except OSError:
        return Readiness(
            "github-cli", "failed", "gh version probe failed", "Run `gh --version` and repair the local installation."
        )
    detail = _bounded(proc.stdout or proc.stderr)
    return Readiness(
        "github-cli", "ready" if proc.returncode == 0 else "failed", detail, "Repair `gh --version` before delivery."
    )


def check_goose(*, state_root: Path) -> Readiness:
    from builder_ii.adapters.goose.goose_compatibility import probe_goose

    try:
        result = probe_goose(state_root=state_root)
    except RuntimeError as exc:
        status = "unavailable" if "not found" in str(exc).lower() else "failed"
        return Readiness(
            "goose-compatibility",
            status,
            _bounded(str(exc)),
            "Install or select a Goose release satisfying >=1.45.0,<1.47.0; builder init never installs or updates it.",
        )
    return Readiness(
        "goose-compatibility", "ready", f"Goose {result.version}; policy {result.policy}", "No remediation required."
    )


def check_deepagents() -> Readiness:
    from builder_ii.adapters.deepagents.deepagents_bridge import deepagents_availability

    result = deepagents_availability()
    ready = result.available and result.create_deep_agent_present
    status = "ready" if ready else "unavailable" if result.import_status == "MISS" else "failed"
    return Readiness(
        "native-deepagents",
        status,
        _bounded(result.detail),
        "Install the declared optional deepagents dependency with create_deep_agent support; builder init never installs it.",
    )


def check_model_backend(*, model_backend: str, model_alias: str) -> Readiness:
    from builder_ii.core.config import load_settings
    from builder_ii.routing.backends import check_health, check_serves_active_model, ensure_backend_supports_model

    settings = replace(load_settings(), backend=model_backend, model_alias=model_alias)
    supported, support_detail = ensure_backend_supports_model(settings)
    if not supported:
        return Readiness(
            "selected-model-backend",
            "failed",
            _bounded(support_detail),
            "Choose a declared model/backend pair in builder init; no provider or model is enabled automatically.",
        )
    health_ok, health_detail = check_health(settings, timeout=3.0)
    if not health_ok:
        return Readiness(
            "selected-model-backend",
            "unavailable",
            _bounded(health_detail),
            "Start or authenticate the selected backend separately, then rerun builder init; builder init never starts or logs in.",
        )
    model_ok, model_detail = check_serves_active_model(settings, timeout=3.0)
    status = "ready" if model_ok else "failed"
    return Readiness(
        "selected-model-backend",
        status,
        _bounded(f"{health_detail}; {model_detail}"),
        "Make the explicitly selected model available on the selected backend; builder init never pulls models.",
    )


def check_repository(*, repository_path: Path) -> Readiness:
    from builder_ii.core.repository_identity import check_repository_identity

    report = check_repository_identity(repository_path=repository_path, timeout=3.0)
    if report.matches:
        return Readiness("repository-identity", "ready", f"origin={report.configured_url}", "No remediation required.")
    status = "unavailable" if report.configured_url is None else "failed"
    return Readiness(
        "repository-identity",
        status,
        _bounded(report.error or "repository identity mismatch"),
        f"Configure origin to {report.canonical_repository}; builder init never changes Git remotes.",
    )


def passive_readiness(
    *,
    root: Path = Path("."),
    state_root: Path | None = None,
    model_backend: str,
    model_alias: str,
) -> tuple[Readiness, ...]:
    isolated_state = (state_root or root / ".builder" / "artifacts" / "onboarding-readiness") / "goose"
    return (
        check_goose(state_root=isolated_state),
        check_deepagents(),
        check_model_backend(model_backend=model_backend, model_alias=model_alias),
        check_gh(),
        check_repository(repository_path=root),
    )


def validate_readiness_evidence(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, list):
        return ["readiness evidence must be a list"]
    expected = {
        "goose-compatibility",
        "native-deepagents",
        "selected-model-backend",
        "github-cli",
        "repository-identity",
    }
    names: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"readiness[{index}] must be an object")
            continue
        name = item.get("name")
        if not isinstance(name, str):
            errors.append(f"readiness[{index}].name is required")
        else:
            names.add(name)
        if item.get("status") not in {"ready", "failed", "unavailable"}:
            errors.append(f"readiness[{index}].status must be ready, failed, or unavailable")
        for field in ("detail", "remediation"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"readiness[{index}].{field} is required")
    if names != expected:
        errors.append(f"readiness detector inventory must be exactly {sorted(expected)}")
    return errors
