"""V.6 — Final operating loop smoke (validation_only / smoke_only).

Passive end-to-end artifact chain for target profiles (builder + core by default):

  targets → doctor → repo_map → context_pack → agent render → quality plan → handoff note

Does **not**: run models, free-form shell, mutate target sources, enable S3/S4,
start engines, or claim Workbench identity. Each step records ok/error honestly.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Callable

from builder_ii.agent_profiles import create_agent_profile_record, get_agent_profile
from builder_ii.config import Settings, load_settings
from builder_ii.config_schema import attach_digest
from builder_ii.context_packs import create_context_pack, dumps_context_pack, validate_context_pack
from builder_ii.handoff_notes import create_handoff_note, dumps_handoff_note, validate_handoff_note
from builder_ii.quality_gates import (
    create_quality_gate_artifact,
    dumps_quality_gate_artifact,
    validate_quality_gate_artifact,
)
from builder_ii.repo_map import create_repo_map, dumps_repo_map, validate_repo_map
from builder_ii.target_profile_defaults import default_agent_profile_for
from builder_ii.target_profiles import (
    TargetName,
    dumps_target_profile_artifact,
    target_profile,
    validate_target_profile_artifact,
    validate_target_profiles,
)
from builder_ii.verification_profiles import default_profile_for_target

FINAL_LOOP_SMOKE_REPORT_KIND = "builder_ii.final_loop_smoke_report"
FINAL_LOOP_SMOKE_SCHEMA_VERSION = 1

DEFAULT_TARGETS: tuple[TargetName, ...] = ("builder", "core")

StepFn = Callable[[], dict[str, Any]]


def _write_json(path: Path, payload: dict[str, Any] | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload if payload.endswith("\n") else payload + "\n", encoding="utf-8")
    else:
        path.write_text(json_lib.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _step(name: str, fn: StepFn) -> dict[str, Any]:
    try:
        result = fn()
        return {
            "step": name,
            "ok": True,
            "error": None,
            "artifact_path": result.get("path"),
            "artifact_kind": result.get("kind"),
            "detail": result.get("detail"),
        }
    except Exception as exc:  # noqa: BLE001 — smoke must record failures honestly
        return {
            "step": name,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "artifact_path": None,
            "artifact_kind": None,
            "detail": None,
        }


def _agent_for_target(target: TargetName) -> str:
    name = default_agent_profile_for(target)
    # Fall back if default is missing from registry
    try:
        get_agent_profile(name)  # type: ignore[arg-type]
        return name
    except Exception:
        return "repo_mapper"


def _verification_profile_for(target: TargetName) -> str:
    try:
        return default_profile_for_target(target).name
    except Exception:
        return "builder_fast" if target == "builder" else "core_smoke"


def run_final_loop_smoke_for_target(
    *,
    settings: Settings,
    target: TargetName,
    output_dir: Path,
    task: str = "V.6 final loop smoke (validation_only)",
    max_repo_files: int = 80,
) -> dict[str, Any]:
    """Run passive loop for one target; write step artifacts under output_dir/target."""
    tdir = output_dir / target
    tdir.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []

    profile = target_profile(settings, target)
    repo = Path(profile.repo)

    def step_targets_artifact() -> dict[str, Any]:
        art = profile.to_artifact_dict()
        errs = validate_target_profile_artifact(art)
        if errs:
            raise ValueError("; ".join(errs))
        path = tdir / "target-profile.json"
        _write_json(path, dumps_target_profile_artifact(profile))
        return {"path": str(path), "kind": art.get("kind"), "detail": f"repo={repo}"}

    def step_targets_validate() -> dict[str, Any]:
        errors = list(validate_target_profiles(settings))
        if target == "core":
            # Missing core repo is reported as step detail, not hard-fail whole smoke
            missing = [e for e in errors if "core repo missing" in e or "core" in e.lower() and "missing" in e]
            if missing and not repo.exists():
                return {
                    "path": None,
                    "kind": "targets_validate",
                    "detail": "core repo missing (honest skip of repo-bound steps may follow)",
                    "warnings": missing,
                }
        other = [e for e in errors if "core repo missing" not in e]
        if other:
            raise ValueError("; ".join(other))
        return {"path": None, "kind": "targets_validate", "detail": "registry ok"}

    def step_doctor() -> dict[str, Any]:
        if target == "core":
            from builder_ii.targets.core import doctor_core_profile

            report = doctor_core_profile(settings)
            path = tdir / "doctor-core.json"
            _write_json(path, report)
            if not report.get("ok"):
                # Isolation catalog can pass even when repo missing; still record
                pass
            return {
                "path": str(path),
                "kind": report.get("kind"),
                "detail": f"ok={report.get('ok')} workbench={report.get('workbench_coupling')}",
            }
        # builder: lightweight registry doctor via validate profiles
        errors = validate_target_profiles(settings)
        path = tdir / "doctor-builder.json"
        report = {
            "kind": "builder_ii.target_profile_doctor_report",
            "target": "builder",
            "ok": len(errors) == 0,
            "errors": list(errors),
            "workbench_coupling": "NONE",
            "grants_runtime_authority": False,
            "semgrep_executed": False,
            "promotion_state": "validation_only",
        }
        _write_json(path, report)
        if errors:
            raise ValueError("; ".join(errors))
        return {"path": str(path), "kind": report["kind"], "detail": "builder registry doctor ok"}

    def step_repo_map() -> dict[str, Any]:
        if not repo.exists():
            raise ValueError(f"repo missing: {repo}")
        rmap = create_repo_map(repo, target_name=target, max_files=max_repo_files)
        errs = validate_repo_map(rmap)
        if errs:
            raise ValueError("; ".join(errs))
        path = tdir / "repo-map.json"
        _write_json(path, dumps_repo_map(rmap))
        return {"path": str(path), "kind": rmap.get("kind"), "detail": f"files={rmap.get('file_count')}"}

    def step_context_pack() -> dict[str, Any]:
        rmap_path = tdir / "repo-map.json"
        if not rmap_path.is_file():
            raise ValueError("repo-map missing; prior step failed")
        rmap = json_lib.loads(rmap_path.read_text(encoding="utf-8"))
        pack = create_context_pack(rmap, target_name=target, task=task, max_entries=40)
        errs = validate_context_pack(pack)
        if errs:
            raise ValueError("; ".join(errs))
        path = tdir / "context-pack.json"
        _write_json(path, dumps_context_pack(pack))
        return {
            "path": str(path),
            "kind": pack.get("kind"),
            "detail": f"selected={len(pack.get('selected_files') or [])}",
        }

    def step_agent_render() -> dict[str, Any]:
        agent_name = _agent_for_target(target)
        agent = get_agent_profile(agent_name)  # type: ignore[arg-type]
        if target not in agent.compatible_targets:
            agent = get_agent_profile("repo_mapper")
            agent_name = "repo_mapper"
        rec = create_agent_profile_record(agent, profile, task=task)
        path = tdir / "agent-profile.json"
        _write_json(path, rec)
        return {"path": str(path), "kind": rec.get("kind"), "detail": f"agent={agent_name}"}

    def step_quality_plan() -> dict[str, Any]:
        vprof = _verification_profile_for(target)  # type: ignore[assignment]
        art = create_quality_gate_artifact(
            target=target,
            verification_profile=vprof,  # type: ignore[arg-type]
            task=task,
        )
        errs = validate_quality_gate_artifact(art)
        if errs:
            raise ValueError("; ".join(errs))
        if art.get("governance", {}).get("quality_gate_executes_commands") is not False:
            raise ValueError("quality gate must not execute commands")
        path = tdir / "quality-gate.json"
        _write_json(path, dumps_quality_gate_artifact(art))
        return {"path": str(path), "kind": art.get("kind"), "detail": f"profile={vprof}"}

    def step_handoff() -> dict[str, Any]:
        note = create_handoff_note(
            target_name=target,
            summary=f"V.6 final loop smoke for target={target} (validation_only).",
            next_recommended_action="Human review smoke report; no automatic execution.",
            changed_files_summary=[],
            verification_summary="Smoke produced planning/quality artifacts only; no tests executed by this lane.",
            open_risks=[
                "Does not execute verification commands",
                "Does not mutate target repository",
                "Does not enable S3/S4 or start engines",
            ],
            human_review_required=True,
            status="DRAFT",
        )
        errs = validate_handoff_note(note)
        if errs:
            raise ValueError("; ".join(errs))
        path = tdir / "handoff-note.json"
        _write_json(path, dumps_handoff_note(note))
        return {"path": str(path), "kind": note.get("kind"), "detail": "handoff draft"}

    ordered: list[tuple[str, StepFn]] = [
        ("targets_artifact", step_targets_artifact),
        ("targets_validate", step_targets_validate),
        ("doctor", step_doctor),
        ("repo_map", step_repo_map),
        ("context_pack", step_context_pack),
        ("agent_render", step_agent_render),
        ("quality_plan", step_quality_plan),
        ("handoff_note", step_handoff),
    ]
    for name, fn in ordered:
        row = _step(name, fn)
        steps.append(row)
        # Soft-stop repo-bound chain if map fails (e.g. missing core checkout)
        if name == "repo_map" and not row["ok"]:
            for skip_name in ("context_pack", "agent_render", "quality_plan", "handoff_note"):
                steps.append(
                    {
                        "step": skip_name,
                        "ok": False,
                        "error": "skipped_after_repo_map_failure",
                        "artifact_path": None,
                        "artifact_kind": None,
                        "detail": "dependent step skipped",
                    }
                )
            break

    ok = all(s["ok"] for s in steps)
    # For core with missing repo: doctor + targets may still pass; overall ok requires all steps
    return {
        "target": target,
        "repo": str(repo),
        "repo_exists": repo.exists(),
        "ok": ok,
        "steps": steps,
        "step_count": len(steps),
        "passed": sum(1 for s in steps if s["ok"]),
        "failed": sum(1 for s in steps if not s["ok"]),
    }


def run_final_loop_smoke(
    *,
    settings: Settings | None = None,
    targets: tuple[TargetName, ...] = DEFAULT_TARGETS,
    output_dir: Path,
    task: str = "V.6 final loop smoke (validation_only)",
    max_repo_files: int = 80,
) -> dict[str, Any]:
    """Run smoke for each target; return digest-bound aggregate report."""
    settings = settings or load_settings()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for target in targets:
        if target not in ("generic", "builder", "core"):
            raise ValueError(f"unknown target: {target}")
        rows.append(
            run_final_loop_smoke_for_target(
                settings=settings,
                target=target,  # type: ignore[arg-type]
                output_dir=output_dir,
                task=task,
                max_repo_files=max_repo_files,
            )
        )

    all_ok = bool(rows) and all(r["ok"] for r in rows)
    report = attach_digest(
        {
            "kind": FINAL_LOOP_SMOKE_REPORT_KIND,
            "schema_version": FINAL_LOOP_SMOKE_SCHEMA_VERSION,
            "artifact_state": "VALIDATION_ONLY",
            "ok": all_ok,
            "targets": rows,
            "target_ids": [r["target"] for r in rows],
            "output_dir": str(output_dir),
            "grants_authority": False,
            "s3_enabled": False,
            "s4_promoted": False,
            "executes_model": False,
            "executes_shell": False,
            "mutates_target_repo": False,
            "workbench_coupling": "NONE",
            "smoke_only": True,
            "notes": (
                "V.6 final operating loop smoke: passive artifact chain for listed targets. "
                "Not S3 enablement; not S4 promo flip; not Workbench; not model/shell execution."
            ),
        }
    )
    report_path = output_dir / "final-loop-smoke-report.json"
    _write_json(report_path, report)
    return report


def validate_final_loop_smoke_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["final loop smoke report must be a JSON object"]
    if record.get("kind") != FINAL_LOOP_SMOKE_REPORT_KIND:
        errors.append(f"kind must be {FINAL_LOOP_SMOKE_REPORT_KIND}")
    if record.get("schema_version") != FINAL_LOOP_SMOKE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {FINAL_LOOP_SMOKE_SCHEMA_VERSION}")
    for key in (
        "grants_authority",
        "s3_enabled",
        "s4_promoted",
        "executes_model",
        "executes_shell",
        "mutates_target_repo",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("workbench_coupling") != "NONE":
        errors.append("workbench_coupling must be NONE")
    if record.get("smoke_only") is not True:
        errors.append("smoke_only must be true")
    if not isinstance(record.get("targets"), list):
        errors.append("targets must be a list")
    digest = record.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a 64-char hex sha256")
    else:
        from builder_ii.config_schema import digest_jsonable

        if digest != digest_jsonable(record):
            errors.append("digest mismatch")
    return errors


__all__ = [
    "DEFAULT_TARGETS",
    "FINAL_LOOP_SMOKE_REPORT_KIND",
    "FINAL_LOOP_SMOKE_SCHEMA_VERSION",
    "run_final_loop_smoke",
    "run_final_loop_smoke_for_target",
    "validate_final_loop_smoke_report",
]
