from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_compatibility import probe_goose, validate_governed_recipe
from builder_ii.adapters.goose.goose_launcher import find_goose_binary, goose_env, recipe_path
from builder_ii.adapters.goose.goose_receipts import (
    create_goose_close_receipt,
    create_goose_launch_receipt,
    create_no_mutation_postflight,
)
from builder_ii.adapters.goose.goose_session_custody import (
    discard_transcript_export,
    install_transcript_export,
    persist_goose_close,
    persist_goose_launch,
    prepare_transcript_export,
)
from builder_ii.adapters.mcp.governed_services import validate_mcp_service_receipt
from builder_ii.core.config import Settings
from builder_ii.governance.hitl.hitl_patch_apply import (
    compute_digest,
    get_git_head_sha,
    validate_patch_apply_receipt_file,
    validate_post_apply_target_state,
    validate_rollback_bundle_file,
)
from builder_ii.governance.hitl.hitl_patch_ledger import validate_hitl_patch_ledger_record_file
from builder_ii.governance.hitl.hitl_rollback_approval import validate_hitl_rollback_approval_file
from builder_ii.governance.ledger.event_ledger import validate_event_record
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.execution_postflight_records import validate_execution_postflight_record_file
from builder_ii.lifecycle.candidate.rollback_artifacts import (
    validate_rollback_plan_file,
    validate_rollback_receipt_file,
)
from builder_ii.routing.model_router import SessionPlan

_DIGEST_CHUNK_SIZE = 1024 * 1024
_executor = ThreadPoolExecutor(max_workers=4)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_TARGET_PROFILES = {"generic", "builder", "core"}


def _current_time_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_sha256(path: Path) -> str | None:
    """Return a streaming SHA-256 digest, or None when the file is unreadable."""
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_DIGEST_CHUNK_SIZE), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def _is_beneath(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _get_target_files(target_root: Path) -> dict[str, str]:
    """Snapshot target files by content digest, not timestamp granularity."""
    snapshot: dict[str, str] = {}
    for p in target_root.rglob("*"):
        if not p.is_file() or ".git" in p.parts or ".builder" in p.parts:
            continue
        digest = _file_sha256(p)
        if digest is not None:
            snapshot[str(p)] = digest
    return snapshot


def _approved_patch_close_evidence(
    evidence: dict[str, Any] | None,
    *,
    session_id: str,
    target_root: Path,
    target_name: str,
    artifact_root: Path | None,
) -> tuple[set[str], dict[str, Any] | None, list[str]]:
    """Validate the exact MCP apply evidence that may authorize target changes at close."""
    if evidence is None:
        return set(), None, []
    if not isinstance(evidence, dict) or evidence.get("status") != "succeeded":
        return set(), None, ["approved patch evidence must be a succeeded MCP result"]
    required = (
        "patch_apply_receipt_ref",
        "postflight_ref",
        "rollback_plan_ref",
        "rollback_bundle_ref",
        "patch_ledger_ref",
        "proposal_ref",
        "approval_ref",
        "verification_receipt_ref",
        "rollback_patch_ref",
    )
    errors: list[str] = []
    refs: dict[str, dict[str, str]] = {}
    for key in required:
        ref = evidence.get(key)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            errors.append(f"missing or invalid {key}")
        else:
            refs[key] = {"path": ref["path"], "sha256": ref["sha256"]}
    if artifact_root is None:
        errors.append("Goose session has no admitted Builder-II artifact root")
    else:
        expected_root = (artifact_root / "sessions" / session_id / "mcp" / "patch-apply").resolve()
        admitted_root = artifact_root.resolve()
        for key, ref in refs.items():
            path = Path(ref["path"])
            try:
                path.resolve().relative_to(
                    expected_root
                    if key not in {"proposal_ref", "approval_ref", "verification_receipt_ref"}
                    else admitted_root
                )
            except ValueError:
                errors.append(f"{key} is not bound to this Goose session artifact namespace")
            if not path.is_file() or path.is_symlink():
                errors.append(f"{key} is missing or is a symlink")
            elif _file_sha256(path) != ref["sha256"]:
                errors.append(f"{key} digest does not match persisted bytes")
    paths = {key: Path(ref["path"]) for key, ref in refs.items()}
    validators = {
        "patch_apply_receipt_ref": validate_patch_apply_receipt_file,
        "postflight_ref": validate_execution_postflight_record_file,
        "rollback_plan_ref": validate_rollback_plan_file,
        "rollback_bundle_ref": validate_rollback_bundle_file,
        "patch_ledger_ref": validate_hitl_patch_ledger_record_file,
    }
    for key, path in paths.items():
        if key in validators and path.is_file() and not path.is_symlink():
            errors.extend(f"{key}: {error}" for error in validators[key](path))
    receipt_path = paths.get("patch_apply_receipt_ref")
    receipt: dict[str, Any] = {}
    if receipt_path and receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"patch apply receipt cannot be reloaded: {exc}")
    target = receipt.get("target") if isinstance(receipt, dict) else None
    if (
        not isinstance(target, dict)
        or target.get("repo") != str(target_root.resolve())
        or target.get("name") != target_name
    ):
        errors.append("patch apply evidence target does not match the Goose target")
    proposal: dict[str, Any] = {}
    approval: dict[str, Any] = {}
    verification: dict[str, Any] = {}
    rollback_plan: dict[str, Any] = {}
    for label, key in (
        ("proposal", "proposal_ref"),
        ("approval", "approval_ref"),
        ("verification", "verification_receipt_ref"),
        ("rollback plan", "rollback_plan_ref"),
    ):
        try:
            value = json.loads(paths[key].read_text(encoding="utf-8"))
            if label == "proposal":
                proposal = value
            elif label == "approval":
                approval = value
            elif label == "verification":
                verification = value
            else:
                rollback_plan = value
        except Exception as exc:
            errors.append(f"{label} cannot be reloaded: {exc}")
    if receipt:
        if receipt.get("proposal_digest") != canonical_digest(proposal):
            errors.append("apply receipt does not bind the persisted proposal")
        if receipt.get("approval_digest") != canonical_digest(approval):
            errors.append("apply receipt does not bind the persisted approval")
        if receipt.get("verification_receipt_digest") != canonical_digest(verification):
            errors.append("apply receipt does not bind the persisted verification receipt")
        if receipt.get("patch_digest") != proposal.get("patch_digest"):
            errors.append("apply receipt patch digest does not match proposal")
    rollback_ref = rollback_plan.get("rollback_patch_ref") if isinstance(rollback_plan, dict) else None
    if (
        not isinstance(rollback_ref, dict)
        or rollback_ref.get("path") != str(paths["rollback_patch_ref"])
        or rollback_ref.get("sha256") != refs["rollback_patch_ref"]["sha256"]
    ):
        errors.append("rollback plan does not bind the persisted forward patch")
    patch_path = paths.get("rollback_patch_ref")
    approved_paths: set[str] = set()
    approved_relative_paths: set[str] = set()
    if patch_path and patch_path.is_file() and not patch_path.is_symlink():
        try:
            patch_text = patch_path.read_text(encoding="utf-8")
            if patch_text != proposal.get("unified_diff"):
                errors.append("bound forward patch does not equal the approved proposal diff")
            if hashlib.sha256(patch_text.encode("utf-8")).hexdigest() != receipt.get("patch_digest"):
                errors.append("bound forward patch does not match the apply receipt patch digest")
            for line in patch_text.splitlines():
                if not line.startswith(("--- ", "+++ ")):
                    continue
                value = line[4:].split("\t", 1)[0]
                if value == "/dev/null":
                    continue
                if not value.startswith(("a/", "b/")):
                    raise ValueError("patch path lacks canonical a/ or b/ prefix")
                rel = value[2:]
                rel_path = Path(rel)
                if not rel or rel_path.is_absolute() or ".." in rel_path.parts or "." in rel_path.parts:
                    raise ValueError("patch path is escaping or non-normalized")
                approved_paths.add(str((target_root / rel_path).resolve()))
                approved_relative_paths.add(rel)
            if not approved_paths:
                raise ValueError("patch contains no canonical file headers")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"bound forward patch is invalid: {exc}")
    else:
        errors.append("digest-bound forward patch is missing from the approved evidence directory")
    expected_path_digests = receipt.get("post_apply_path_digests")
    if not isinstance(expected_path_digests, dict) or set(expected_path_digests) != approved_relative_paths:
        errors.append("apply receipt post-apply path digests do not match approved patch scope")
    errors.extend(validate_post_apply_target_state(target_root, receipt))
    if errors:
        return set(), None, list(dict.fromkeys(errors))
    summary = {
        "session_id": session_id,
        "target_root": str(target_root.resolve()),
        "patch_apply_receipt_ref": evidence["patch_apply_receipt_ref"],
        "postflight_ref": evidence["postflight_ref"],
        "rollback_plan_ref": evidence["rollback_plan_ref"],
        "rollback_bundle_ref": evidence["rollback_bundle_ref"],
        "patch_ledger_ref": evidence["patch_ledger_ref"],
        "rollback_patch_ref": evidence["rollback_patch_ref"],
        "proposal_ref": evidence["proposal_ref"],
        "approval_ref": evidence["approval_ref"],
        "verification_receipt_ref": evidence["verification_receipt_ref"],
    }
    return approved_paths, summary, []


def _discover_session_patch_evidence(
    *, artifact_root: Path | None, session_id: str, target_name: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """Discover one durable successful patch_apply result for this exact MCP session."""
    if artifact_root is None:
        return None, []
    session_root = artifact_root.resolve() / "sessions" / session_id
    receipts = sorted((session_root / "mcp").glob("*_patch_apply_receipt.json"))
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    for receipt_path in receipts:
        if receipt_path.is_symlink() or not receipt_path.is_file():
            errors.append("session patch receipt is missing or a symlink")
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"session patch receipt is unreadable: {exc}")
            continue
        receipt_errors = validate_mcp_service_receipt(receipt)
        if receipt_errors:
            errors.extend(f"session patch receipt: {error}" for error in receipt_errors)
            continue
        if receipt.get("session_id") != session_id or receipt.get("target_profile") != target_name:
            errors.append("session patch receipt identity does not match current Goose session")
            continue
        prefix = receipt_path.name.split("_", 1)[0]
        event_path = session_root / "events" / f"{prefix}_mcp_service.json"
        try:
            event = json.loads(event_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"session patch event is not durable: {exc}")
            continue
        event_errors = validate_event_record(event)
        refs = event.get("subject_refs", []) if isinstance(event, dict) else []
        bound = any(
            isinstance(ref, dict)
            and ref.get("path") == str(receipt_path.resolve())
            and ref.get("sha256") == canonical_digest(receipt)
            for ref in refs
        )
        if event_errors or not bound:
            errors.extend(f"session patch event: {error}" for error in event_errors)
            if not bound:
                errors.append("session patch event does not bind the persisted service receipt")
            continue
        result = receipt.get("result")
        if receipt.get("status") == "succeeded" and isinstance(result, dict) and result.get("status") == "succeeded":
            candidates.append(result)
        else:
            errors.append("session patch outcome is not a durable success")
    if len(candidates) > 1:
        return None, errors + ["session patch evidence is duplicate or ambiguous"]
    return (candidates[0] if candidates else None), errors


def _discover_session_rollback_evidence(*, artifact_root: Path | None, session_id: str, target_name: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Discover one durable successful terminal rollback result for this session."""
    if artifact_root is None:
        return None, []
    root = artifact_root.resolve() / "sessions" / session_id
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    outer_root = root / "mcp"
    events_root = root / "events"
    for path in sorted(outer_root.glob("*_rollback_receipt.json")):
        try:
            if path.is_symlink() or not path.is_file() or path.parent != outer_root:
                errors.append("rollback outer receipt is missing, a symlink, or outside the session MCP namespace")
                continue
            record = json.loads(path.read_text(encoding="utf-8"))
            errors_here = validate_mcp_service_receipt(record)
            if errors_here:
                errors.extend(errors_here); continue
            if record.get("session_id") != session_id or record.get("target_profile") != target_name:
                errors.append("rollback receipt identity does not match session"); continue
            prefix = path.name.split("_", 1)[0]
            event_path = events_root / f"{prefix}_mcp_service.json"
            if event_path.is_symlink() or not event_path.is_file() or event_path.parent != events_root:
                errors.append("rollback outer event is missing, a symlink, or outside the session event namespace")
                continue
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event_errors = validate_event_record(event)
            if not isinstance(event, dict):
                errors.append("rollback event must be a JSON object")
                continue
            bound = any(
                isinstance(ref, dict)
                and ref.get("path") == str(path.resolve())
                and ref.get("sha256") == canonical_digest(record)
                for ref in event.get("subject_refs", [])
            )
            if not bound:
                event_errors.append("rollback event does not bind the exact outer MCP receipt")
            if event_errors:
                errors.extend(event_errors); continue
            result = record.get("result")
            if record.get("status") == "succeeded" and isinstance(result, dict) and result.get("status") == "succeeded":
                candidates.append(result)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"rollback evidence is not durable: {exc}")
    if len(candidates) > 1:
        errors.append("rollback evidence is duplicate or ambiguous")
    return (candidates[0] if candidates else None), errors


def _validated_rollback_close_evidence(
    result: dict[str, Any], *, artifact_root: Path | None, session_id: str, target_root: Path, target_name: str
) -> tuple[set[str], dict[str, Any] | None, list[str]]:
    """Revalidate rollback bytes and derive close scope solely from its bound reverse patch."""
    errors: list[str] = []
    if artifact_root is None:
        errors.append("Goose session has no admitted Builder-II artifact root")
    rollback_root = (artifact_root / "sessions" / session_id / "mcp" / "rollback").resolve() if artifact_root else None
    session_root = (artifact_root / "sessions" / session_id).resolve() if artifact_root else None
    refs: dict[str, Path] = {}
    for key in ("rollback_receipt_ref", "rollback_ledger_ref", "rollback_plan_ref", "rollback_approval_ref", "rollback_reverse_patch_ref"):
        ref = result.get(key)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            errors.append(f"rollback result has invalid {key}")
        else:
            path = Path(ref["path"])
            refs[key] = path
            if key in {"rollback_receipt_ref", "rollback_ledger_ref"} and (
                rollback_root is None or not _is_beneath(path, rollback_root)
            ):
                errors.append(f"rollback {key} is outside the session rollback namespace")
            if key in {"rollback_plan_ref", "rollback_approval_ref", "rollback_reverse_patch_ref"} and (
                session_root is None or not _is_beneath(path, artifact_root.resolve())
            ):
                errors.append(f"rollback {key} is outside the admitted Builder-II artifact root")
            if path.is_symlink() or not path.is_file():
                errors.append(f"rollback {key} is missing or a symlink")
            elif _file_sha256(path) != ref["sha256"]:
                errors.append(f"rollback {key} digest changed")
    validators = {
        "rollback_receipt_ref": validate_rollback_receipt_file,
        "rollback_ledger_ref": validate_hitl_patch_ledger_record_file,
        "rollback_plan_ref": validate_rollback_plan_file,
        "rollback_approval_ref": validate_hitl_rollback_approval_file,
    }
    for key, validator in validators.items():
        path = refs.get(key)
        if path and path.is_file() and not path.is_symlink():
            errors.extend(f"{key}: {error}" for error in validator(path))
    loaded: dict[str, Any] = {}
    for key in validators:
        path = refs.get(key)
        if path and path.is_file():
            try:
                loaded[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{key} cannot be reloaded: {exc}")
    plan = loaded.get("rollback_plan_ref")
    receipt = loaded.get("rollback_receipt_ref")
    ledger = loaded.get("rollback_ledger_ref")
    approval = loaded.get("rollback_approval_ref")
    target = {"name": target_name, "repo": str(target_root.resolve())}
    for label, artifact in (("receipt", receipt), ("ledger", ledger), ("plan", plan), ("approval", approval)):
        artifact_target = artifact.get("target") if isinstance(artifact, dict) else None
        if not isinstance(artifact_target, dict) or artifact_target.get("name") != target["name"] or Path(str(artifact_target.get("repo", ""))).resolve() != target_root.resolve():
            errors.append(f"rollback {label} target is not bound to Goose target")
    reverse = refs.get("rollback_reverse_patch_ref")
    plan_ref = plan.get("rollback_patch_ref") if isinstance(plan, dict) else None
    result_reverse_ref = result.get("rollback_reverse_patch_ref")
    result_reverse_digest = result_reverse_ref.get("sha256") if isinstance(result_reverse_ref, dict) else None
    if not isinstance(result_reverse_ref, dict):
        errors.append("rollback result reverse-patch reference must be an object")
    if not isinstance(plan_ref, dict) or not reverse or plan_ref.get("path") != str(reverse) or plan_ref.get("sha256") != result_reverse_digest:
        errors.append("rollback plan does not bind the exact supplied reverse patch")
    if isinstance(receipt, dict):
        if receipt.get("rollback_plan_ref") != str(refs.get("rollback_plan_ref")):
            errors.append("rollback receipt plan reference changed")
        if receipt.get("rollback_approval_digest") != canonical_digest(approval):
            errors.append("rollback receipt approval digest changed")
        if receipt.get("rollback_patch_ref") != plan_ref:
            errors.append("rollback receipt reverse-patch reference changed")
        if receipt.get("rollback_state") != "EXECUTED" or receipt.get("current_state") != "OPERATIONALLY_VERIFIED" or receipt.get("rollback_equivalence_verified") is not True:
            errors.append("rollback receipt does not prove restored state")
        try:
            if get_git_head_sha(target_root) != plan.get("pre_head"):
                errors.append("restored target HEAD does not match rollback pre-HEAD")
            status = subprocess.run(["git", "status", "--porcelain"], cwd=target_root, check=True, capture_output=True, text=True).stdout.splitlines()
            if compute_digest("\n".join(status)) != receipt.get("post_rollback_status_digest"):
                errors.append("restored target status does not match rollback receipt")
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"restored target state cannot be verified: {exc}")
    if isinstance(ledger, dict):
        ledger_target = ledger.get("target") if isinstance(ledger, dict) else None
        plan_target = plan.get("target") if isinstance(plan, dict) else None
        expected_ledger_target = (
            {"name": plan_target.get("name"), "repo": plan_target.get("repo")}
            if isinstance(plan_target, dict)
            else None
        )
        if ledger_target != expected_ledger_target or not isinstance(plan, dict) or ledger.get("patch_digest") != plan.get("patch_digest") or ledger.get("pre_head") != plan.get("pre_head"):
            errors.append("rollback ledger target, patch digest, or pre-HEAD changed")
        expected_roles = {"rollback_plan": refs.get("rollback_plan_ref"), "rollback_approval": refs.get("rollback_approval_ref"), "rollback_reverse_patch": reverse, "rollback_receipt": refs.get("rollback_receipt_ref")}
        observed = {r.get("role"): r for r in ledger.get("subject_refs", []) if isinstance(r, dict)}
        for role, path in expected_roles.items():
            ref = observed.get(role)
            expected_digest = _file_sha256(path) if path else None
            if not isinstance(ref, dict) or ref.get("path") != str(path) or ref.get("sha256") != expected_digest or ref.get("required") is not True:
                errors.append(f"rollback ledger subject {role} is not exact")
    approved_paths: set[str] = set()
    if reverse and reverse.is_file():
        try:
            for line in reverse.read_text(encoding="utf-8").splitlines():
                if line.startswith(("--- ", "+++ ")):
                    value = line[4:].split("\t", 1)[0]
                    if value != "/dev/null" and value.startswith(("a/", "b/")):
                        rel = Path(value[2:])
                        if rel.is_absolute() or ".." in rel.parts or "." in rel.parts:
                            raise ValueError("reverse patch path is not normalized")
                        approved_paths.add(str((target_root / rel).resolve()))
            if not approved_paths:
                errors.append("rollback reverse patch has no canonical paths")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"rollback reverse patch is invalid: {exc}")
    if errors:
        return set(), None, list(dict.fromkeys(errors))
    return approved_paths, {
        "session_id": session_id,
        "target_root": str(target_root.resolve()),
        **{key: result[key] for key in result if key.endswith("_ref")},
    }, []


async def _get_target_files_async(target_root: Path) -> dict[str, str]:
    """Asynchronously snapshot target files using threadpool executor to avoid GIL blocks."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _get_target_files, target_root)


class GooseRuntimeHarness:
    def __init__(
        self,
        settings: Settings,
        session_plan: SessionPlan,
        target_root: Path,
        *,
        model_gateway_context: Any | None = None,
    ):
        self.settings = settings
        self.session_plan = session_plan
        self.target_root = target_root
        self.session_id = f"goose_{int(time.time())}"
        self._proc: subprocess.Popen[str] | None = None
        self._async_proc: asyncio.subprocess.Process | None = None
        self._preflight_snapshot: dict[str, str] = {}
        self._governed_admission: tuple[Any, str] | None = None
        self._admitted_target_profile: str | None = None
        self._admitted_project_root: Path | None = None
        self._admitted_artifact_root: Path | None = None
        self._admitted_allow_artifact_root_inside_target = False
        self._model_gateway_context = model_gateway_context
        self._model_gateway_adapter: Any | None = None
        self._canonical_launch_receipt: dict[str, Any] | None = None

    def _resolve_governed_identity(self) -> tuple[str, Path, bool]:
        """Resolve target and artifact identities through canonical config precedence."""
        from builder_ii.core.config_sources import resolve_config_sources

        project_root = Path(self.settings.project_root).resolve()
        # The target repository is already resolved by the primary builder-start path. Override
        # only that path while letting canonical config precedence resolve active_target_profile.
        platform_resolution = resolve_config_sources(
            project_root=project_root,
            cli_overrides={"target_repo": str(self.target_root.resolve())},
        )
        if platform_resolution.errors:
            raise ValueError("Invalid governed target configuration: " + "; ".join(platform_resolution.errors))
        target_profile = platform_resolution.value("active_target_profile")
        if target_profile not in _TARGET_PROFILES:
            raise ValueError("Invalid governed target profile; expected generic, builder, or core.")
        target_resolution = resolve_config_sources(
            project_root=self.target_root.resolve(),
            cli_overrides={"target_repo": str(self.target_root.resolve())},
            builder_config_file=platform_resolution.builder_config_path,
        )
        if target_resolution.errors:
            raise ValueError("Invalid governed artifact configuration: " + "; ".join(target_resolution.errors))
        if target_resolution.value("active_target_profile") != target_profile:
            raise ValueError("Governed target profile differs between platform and target configuration contexts.")
        artifact_root = Path(target_resolution.value("platform_artifact_root")).resolve(strict=False)
        allow_inside = target_resolution.raw_value("allow_artifact_root_inside_target") is True
        from builder_ii.core.config_sources import admit_platform_artifact_root

        admitted_root = admit_platform_artifact_root(
            artifact_root,
            self.target_root,
            allow_inside_target=allow_inside,
        )
        return target_profile, admitted_root, allow_inside

    def _resolve_governed_target_profile(self) -> str:
        """Compatibility projection for callers that need only the admitted profile."""
        return self._resolve_governed_identity()[0]

    def admit_governed(self) -> tuple[Any, str]:
        """Perform governed admission before any backend or Goose spawn."""
        if not self.session_id or not _SESSION_ID_RE.fullmatch(self.session_id):
            raise ValueError("Invalid Goose session identity; use 1-128 path-safe letters, digits, '.', '_' or '-'.")
        if not self.target_root.is_dir():
            raise ValueError(f"Invalid Goose target identity; target directory does not exist: {self.target_root}")
        project_root = Path(self.settings.project_root).resolve()
        if not project_root.is_dir():
            raise ValueError(f"Invalid Builder-II project root for governed MCP configuration: {project_root}")
        target_profile, artifact_root, allow_inside = self._resolve_governed_identity()
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError(
                "Goose CLI not found. Install a tested Goose release manually; no automatic update is performed."
            )
        recipe_digest = validate_governed_recipe(self._governed_recipe_path())
        compatibility = probe_goose(goose, self.target_root / ".builder" / "goose-compatibility")
        self._governed_admission = (compatibility, recipe_digest)
        self._admitted_target_profile = target_profile
        self._admitted_project_root = project_root
        self._admitted_artifact_root = artifact_root
        self._admitted_allow_artifact_root_inside_target = allow_inside
        return self._governed_admission

    def launch_readonly(self) -> dict[str, Any]:
        """Launch Goose in a strict read-only mode, without shell access."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = goose_env(self.settings, session=self.session_plan)

        # Enforce read-only bounds in the environment.
        env["GOOSE_MODE"] = "auto"

        # We restrict the capabilities by not supplying `developer` builtin.
        argv = [goose, "session", "--with-builtin", "", "--name", self.session_id]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])

        self._preflight_snapshot = _get_target_files(self.target_root)

        start_time = _current_time_utc()
        self._proc = subprocess.Popen(
            argv,
            cwd=self.target_root,
            env=env,
        )

        return create_goose_launch_receipt(
            session_id=self.session_id,
            target_profile=self.session_plan.target_name if hasattr(self.session_plan, "target_name") else "builder",
            agent_profile=self.session_plan.agent_profile
            if hasattr(self.session_plan, "agent_profile")
            else "patch_planner",
            pid=self._proc.pid,
            start_time=start_time,
            evidence={"runtime": "goose_readonly"},
        )

    # Recipe whose sole extension is the builder-II governed MCP server (G2). Unlike
    # launch_readonly (which strips builtins so Goose has *no* tools), this gives Goose one
    # tool surface -- our server -- so its tool calls flow through the governed ceremony.
    GOVERNED_RECIPE_NAME = "governed-readonly.yaml"

    def _governed_recipe_path(self) -> Path:
        return self.settings.project_root / "recipes" / self.GOVERNED_RECIPE_NAME

    def _governed_argv(self, goose: str, recipe: Path) -> list[str]:
        """Goose argv for a governed session: no builtins, our recipe as the tool surface."""
        argv = [goose, "session", "--with-builtin", "", "--name", self.session_id]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])
        return argv

    def launch_governed(self) -> dict[str, Any]:
        """Launch Goose with the builder-II governed MCP server as its only tool surface.

        Points Goose at ``recipes/governed-readonly.yaml``, whose sole extension is
        ``builder-mcp serve`` -- so every Goose tool call flows through the governed
        envelope -> receipt -> ledger ceremony instead of a native builtin. Still no
        developer/shell builtins (``--with-builtin ""``), still preflight-snapshotted and
        no-mutation-postflighted on close. The in-loop refusal gate for mutating tool
        classes arrives in G3; G2's exposed tools are read-only, so ``GOOSE_MODE`` stays
        ``auto`` and the governance boundary lives in the MCP tool, not in Goose's prompt.
        """
        if self._model_gateway_context is None:
            raise ValueError(
                "canonical governed Goose launch requires a validated WRP ModelExecutionGateway context"
            )
        recipe = self._governed_recipe_path()
        if self._governed_admission is None:
            self.admit_governed()
        compatibility, recipe_digest = self._governed_admission
        target_profile = self._admitted_target_profile
        project_root = self._admitted_project_root
        artifact_root = self._admitted_artifact_root
        if target_profile is None or project_root is None or artifact_root is None:
            raise RuntimeError("Governed Goose admission did not bind MCP target/config identity.")
        current_profile, current_artifact_root, current_allow_inside = self._resolve_governed_identity()
        if current_profile != target_profile:
            raise ValueError("Governed target profile changed after admission; refusing to spawn Goose.")
        if (
            current_artifact_root != artifact_root
            or current_allow_inside != self._admitted_allow_artifact_root_inside_target
        ):
            raise ValueError("Governed artifact root changed after admission; refusing to spawn Goose.")
        if Path(self.settings.project_root).resolve() != project_root:
            raise ValueError("Builder-II project root changed after admission; refusing to spawn Goose.")

        # Keep the final recipe check before starting the loopback model adapter,
        # so a spawn-boundary refusal leaves no listening runtime behind.
        current_recipe_digest = validate_governed_recipe(recipe)
        if current_recipe_digest != recipe_digest:
            raise ValueError(
                "Governed Goose recipe changed after admission; refusing to spawn Goose. "
                "Re-admit the unchanged recipe and retry."
            )

        goose = compatibility.binary
        from builder_ii.adapters.goose.goose_launcher import derive_goose_environment
        from builder_ii.adapters.goose.model_gateway_adapter import GooseModelGatewayAdapter

        self._model_gateway_adapter = GooseModelGatewayAdapter(self._model_gateway_context)
        self._model_gateway_adapter.start()
        env, gateway_report = derive_goose_environment(
            self.settings,
            session=self.session_plan,
            model_gateway_url=self._model_gateway_adapter.base_url,
            model_gateway_credential=self._model_gateway_context.local_credential,
            route_model_id=self._model_gateway_context.route.selected_candidate.model_id,
        )
        env["GOOSE_MODE"] = "auto"
        # Scope the MCP server's ledger and bind its target/config identities to this exact
        # admitted launch. The target repository itself remains Popen.cwd below.
        env["BUILDER_MCP_SESSION_ID"] = self.session_id
        env["BUILDER_MCP_TARGET_PROFILE"] = target_profile
        env["BUILDER_MCP_PROJECT_ROOT"] = str(project_root)
        env["BUILDER_ARTIFACT_ROOT"] = str(artifact_root)
        env["BUILDER_ALLOW_ARTIFACT_ROOT_INSIDE_TARGET"] = (
            "true" if self._admitted_allow_artifact_root_inside_target else "false"
        )

        argv = self._governed_argv(goose, recipe)
        self._preflight_snapshot = _get_target_files(self.target_root)

        start_time = _current_time_utc()
        try:
            self._proc = subprocess.Popen(argv, cwd=self.target_root, env=env)
        except Exception:
            self._model_gateway_adapter.close()
            self._model_gateway_adapter = None
            raise

        receipt = create_goose_launch_receipt(
            session_id=self.session_id,
            target_profile=target_profile,
            agent_profile=self.session_plan.agent_profile
            if hasattr(self.session_plan, "agent_profile")
            else "patch_planner",
            pid=self._proc.pid,
            start_time=start_time,
            evidence={
                "goose_compatibility": {
                    "binary": compatibility.binary,
                    "version": compatibility.version,
                    "policy": compatibility.policy,
                },
                "recipe_sha256": recipe_digest,
                "model_gateway": gateway_report,
                "route_digest": self._model_gateway_context.route.route_digest,
                "target_root": str(self.target_root.resolve()),
            },
        )
        try:
            persist_goose_launch(
                artifact_root=artifact_root,
                session_id=self.session_id,
                launch_receipt=receipt,
            )
        except Exception:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            self._model_gateway_adapter.close()
            self._model_gateway_adapter = None
            raise
        self._canonical_launch_receipt = receipt
        return receipt

    def wait_for_exit(self) -> int:
        """Wait for the canonical governed Goose process without exposing process state."""
        if self._proc is None:
            raise RuntimeError("Canonical governed Goose launch did not produce a process.")
        return self._proc.wait()

    async def launch_readonly_async(self) -> dict[str, Any]:
        """Launch Goose asynchronously in strict read-only mode, avoiding loop blockage."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = goose_env(self.settings, session=self.session_plan)
        env["GOOSE_MODE"] = "auto"

        argv = [goose, "session", "--with-builtin", "", "--name", self.session_id]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])

        self._preflight_snapshot = await _get_target_files_async(self.target_root)

        start_time = _current_time_utc()
        self._async_proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=self.target_root,
            env=env,
        )

        return create_goose_launch_receipt(
            session_id=self.session_id,
            target_profile=self.session_plan.target_name if hasattr(self.session_plan, "target_name") else "builder",
            agent_profile=self.session_plan.agent_profile
            if hasattr(self.session_plan, "agent_profile")
            else "patch_planner",
            pid=self._async_proc.pid,
            start_time=start_time,
            evidence={"runtime": "goose_readonly_async"},
        )

    def close(
        self,
        launch_receipt_digest: str,
        *,
        approved_patch_evidence: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Terminate Goose and verify no mutations except an exact approved patch."""
        end_time = _current_time_utc()
        exit_code = 0
        if self._proc:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            exit_code = self._proc.returncode
        if getattr(self, "_model_gateway_adapter", None) is not None:
            self._model_gateway_adapter.close()
            self._model_gateway_adapter = None

        post_snapshot = _get_target_files(self.target_root)
        mutations: list[str] = []
        for file_path, digest in post_snapshot.items():
            if file_path not in self._preflight_snapshot or self._preflight_snapshot[file_path] != digest:
                mutations.append(file_path)
        for file_path in self._preflight_snapshot:
            if file_path not in post_snapshot:
                mutations.append(f"{file_path} (deleted)")

        discovered, discovery_errors = (
            _discover_session_patch_evidence(
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                target_name=getattr(self.session_plan, "target_name", "builder"),
            )
            if approved_patch_evidence is None
            else (approved_patch_evidence, [])
        )
        rollback_discovered, rollback_errors = _discover_session_rollback_evidence(
            artifact_root=self._admitted_artifact_root,
            session_id=self.session_id,
            target_name=getattr(self.session_plan, "target_name", "builder"),
        )
        approved_paths, evidence_summary, evidence_errors = _approved_patch_close_evidence(
            discovered,
            session_id=self.session_id,
            target_root=self.target_root,
            target_name=getattr(self.session_plan, "target_name", "builder"),
            artifact_root=self._admitted_artifact_root,
        )
        if rollback_discovered is not None:
            # Rollback is terminal, but its reverse patch is the only authority for the
            # changed-path scope. Revalidate the restored target before classifying deltas.
            approved_paths, evidence_summary, evidence_errors = _validated_rollback_close_evidence(
                rollback_discovered,
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                target_root=self.target_root,
                target_name=getattr(self.session_plan, "target_name", "builder"),
            )
            evidence_errors = rollback_errors + evidence_errors
            discovery_errors = []
        if mutations:
            evidence_errors = discovery_errors + evidence_errors
        approved_mutations = [
            mutation for mutation in mutations if mutation.removesuffix(" (deleted)") in approved_paths
        ]
        unexplained_mutations = [mutation for mutation in mutations if mutation not in approved_mutations]
        if evidence_errors:
            unexplained_mutations = list(mutations) + ["approved patch evidence invalid: " + "; ".join(evidence_errors)]

        postflight = create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root.resolve()),
            start_time=end_time,  # approximate for schema
            end_time=end_time,
            files_checked=len(post_snapshot),
            mutations_detected=mutations,
            approved_mutations=approved_mutations,
            unexplained_mutations=unexplained_mutations,
            mutation_mode="approved_hitl_rollback" if rollback_discovered is not None else (
                "approved_hitl_patch" if evidence_summary else "no_mutation"
            ),
            approved_mutation_evidence=evidence_summary,
        )

        # Export the actual transcript to a JSON log instead of timestamp guessing
        canonical_close = self._admitted_artifact_root is not None and self._canonical_launch_receipt is not None
        transcript_export = (
            prepare_transcript_export(self._admitted_artifact_root, self.session_id)
            if canonical_close and self._admitted_artifact_root is not None
            else None
        )
        transcript_path_obj = (
            transcript_export.child_path
            if transcript_export is not None
            else self.target_root / ".builder" / "artifacts" / f"{self.session_id}.jsonl"
        )
        transcript_path_obj.parent.mkdir(parents=True, exist_ok=True)
        transcript_export_path = str(transcript_path_obj)
        export_binary = (
            self._governed_admission[0].binary
            if self._governed_admission is not None
            else "goose"
        )
        try:
            export_result = subprocess.run(
                [
                    export_binary,
                    "session",
                    "export",
                    "--name",
                    self.session_id,
                    "--format",
                    "json",
                    "--output",
                    transcript_export_path,
                ],
                check=False,
                pass_fds=(transcript_export.file_fd,) if transcript_export is not None else (),
            )
        except Exception:
            if transcript_export is not None:
                discard_transcript_export(transcript_export)
            raise
        if canonical_close and export_result.returncode != 0:
            assert transcript_export is not None
            discard_transcript_export(transcript_export)
            raise RuntimeError(
                f"Goose transcript export failed with status {export_result.returncode}; close custody was not recorded"
            )
        if canonical_close:
            assert self._admitted_artifact_root is not None
            transcript_path_obj = install_transcript_export(
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                export=transcript_export,
            )
        transcript_path = str(transcript_path_obj)
        transcript_digest = _file_sha256(transcript_path_obj) or ""

        close_receipt = create_goose_close_receipt(
            session_id=self.session_id,
            launch_receipt_digest=launch_receipt_digest,
            postflight_digest=postflight["digest"],
            transcript_path=transcript_path,
            transcript_digest=transcript_digest,
            end_time=end_time,
            exit_code=exit_code,
        )

        if canonical_close:
            assert self._admitted_artifact_root is not None
            assert self._canonical_launch_receipt is not None
            persist_goose_close(
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                launch_receipt=self._canonical_launch_receipt,
                close_receipt=close_receipt,
                postflight=postflight,
            )

        return close_receipt, postflight

    async def close_async(
        self,
        launch_receipt_digest: str,
        *,
        approved_patch_evidence: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Asynchronously terminate Goose and check filesystem changes."""
        end_time = _current_time_utc()
        exit_code = 0
        if self._async_proc:
            if self._async_proc.returncode is None:
                self._async_proc.terminate()
                try:
                    await asyncio.wait_for(self._async_proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._async_proc.kill()
                    await self._async_proc.wait()
            exit_code = self._async_proc.returncode

        post_snapshot = await _get_target_files_async(self.target_root)

        mutations: list[str] = []
        for file_path, digest in post_snapshot.items():
            if file_path not in self._preflight_snapshot or self._preflight_snapshot[file_path] != digest:
                mutations.append(file_path)
        for file_path in self._preflight_snapshot:
            if file_path not in post_snapshot:
                mutations.append(f"{file_path} (deleted)")

        discovered, discovery_errors = (
            _discover_session_patch_evidence(
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                target_name=getattr(self.session_plan, "target_name", "builder"),
            )
            if approved_patch_evidence is None
            else (approved_patch_evidence, [])
        )
        approved_paths, evidence_summary, evidence_errors = _approved_patch_close_evidence(
            discovered,
            session_id=self.session_id,
            target_root=self.target_root,
            target_name=getattr(self.session_plan, "target_name", "builder"),
            artifact_root=self._admitted_artifact_root,
        )
        rollback_discovered, rollback_errors = _discover_session_rollback_evidence(
            artifact_root=self._admitted_artifact_root,
            session_id=self.session_id,
            target_name=getattr(self.session_plan, "target_name", "builder"),
        )
        if rollback_discovered is not None:
            approved_paths, evidence_summary, evidence_errors = _validated_rollback_close_evidence(
                rollback_discovered,
                artifact_root=self._admitted_artifact_root,
                session_id=self.session_id,
                target_root=self.target_root,
                target_name=getattr(self.session_plan, "target_name", "builder"),
            )
            evidence_errors = rollback_errors + evidence_errors
            discovery_errors = []
        if mutations:
            evidence_errors = discovery_errors + evidence_errors
        approved_mutations = [
            mutation for mutation in mutations if mutation.removesuffix(" (deleted)") in approved_paths
        ]
        unexplained_mutations = [mutation for mutation in mutations if mutation not in approved_mutations]
        if evidence_errors:
            unexplained_mutations = list(mutations) + ["approved patch evidence invalid: " + "; ".join(evidence_errors)]

        postflight = create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root),
            start_time=end_time,
            end_time=end_time,
            files_checked=len(post_snapshot),
            mutations_detected=mutations,
            approved_mutations=approved_mutations,
            unexplained_mutations=unexplained_mutations,
            mutation_mode="approved_hitl_rollback" if rollback_discovered is not None else (
                "approved_hitl_patch" if evidence_summary else "no_mutation"
            ),
            approved_mutation_evidence=evidence_summary,
        )

        # Export the actual transcript to a JSON log instead of timestamp guessing
        transcript_path_obj = self.target_root / ".builder" / "artifacts" / f"{self.session_id}.jsonl"
        transcript_path_obj.parent.mkdir(parents=True, exist_ok=True)
        transcript_path = str(transcript_path_obj)
        subprocess.run(
            [
                "goose",
                "session",
                "export",
                "--name",
                self.session_id,
                "--format",
                "json",
                "--output",
                transcript_path,
            ],
            check=False,
        )
        transcript_digest = _file_sha256(transcript_path_obj) or ""

        close_receipt = create_goose_close_receipt(
            session_id=self.session_id,
            launch_receipt_digest=launch_receipt_digest,
            postflight_digest=postflight["digest"],
            transcript_path=transcript_path,
            transcript_digest=transcript_digest,
            end_time=end_time,
            exit_code=exit_code,
        )

        return close_receipt, postflight
