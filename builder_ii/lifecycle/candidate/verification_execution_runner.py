from __future__ import annotations

import fnmatch
import hashlib
import json as json_lib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.governance.authority import (
    CommandAuthorityDecision,
    CommandAuthorityError,
    check_command_authority,
    enforce_command_authority,
)
from builder_ii.lifecycle.candidate.execution_postflight_records import (
    validate_execution_postflight_record,
    write_execution_postflight_record,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import (
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    B1_1_SUPPORTED_VERIFICATION_PROFILE,
    MAX_TIMEOUT_SECONDS,
    MIN_TIMEOUT_SECONDS,
    TARGET_CODE_EXECUTING_PROFILES,
    plan_timeout_for_profile,
    validate_verification_execution_plan_artifact,
)
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
    write_verification_execution_receipt,
)
from builder_ii.lifecycle.candidate.verification_isolation_backend import IsolationBackendError, get_backend

STDOUT_STDERR_CAPTURE_BYTES = 65536
GIT_STATUS_TIMEOUT_SECONDS = 10

# The directory that contains builder-II's own `builder_ii` package -- i.e. the import root of the
# code that is *doing* the verifying. Every child the runner spawns resolves `builder_ii` here and
# nowhere else, so the repository under verification can never supply the module that audits it.
# Repo root (parent of the builder_ii package). Depth must not assume a flat module layout.
BUILDER_II_IMPORT_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_ARG_TOKENS = ("&&", "||", ";", "|", "`", "$(", "\n", "\r", ">", "<")
SAFE_ENV_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "USER",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "SYSTEMDRIVE",
    "TERM",
)


@dataclass(frozen=True)
class BoundedCommandProfile:
    profile: str
    step_id: str
    # True for builder-II self-verification profiles (platform_status/docs_audit/builder_full)
    # that run builder-II's own checks and are only meaningful when the target IS builder-II;
    # these are refused for non-builder verification profiles. False for target-code profiles
    # (pytest_full) that run the target repository's own suite under any namespace (B4.2 / 1.3).
    builder_self: bool
    argv: tuple[str, ...]
    # Code-level ceiling on the effective timeout. The effective timeout is the plan's
    # per-profile timeout (D7), clamped to this ceiling and to [1, 1800]s -- so even an
    # over-large approved plan can never make a fast profile hang the runner.
    timeout_ceiling_seconds: int
    # Ignore-globs pinned inside the fixed profile (never caller-supplied). Paths matching
    # these that change during the run are recorded as observed byproducts rather than
    # counted as workspace mutation -- but they are always recorded, never hidden.
    byproduct_ignore_globs: tuple[str, ...] = ()


def _effective_command_profile_ref(verification_profile: str, profile_name: str) -> str:
    """Compose the command_profile_ref for a run under a given plan's verification profile.

    The ref namespace tracks the plan's verification_profile (builder_full for builder-II itself,
    generic_basic for a generic target repo, etc.), so a bounded profile like pytest_full runs the
    target's own suite under the correct namespace without a per-namespace table entry.
    """
    return f"verification_profiles.{verification_profile}.{profile_name}"


# pytest leaves cache/bytecode droppings even with -p no:cacheprovider + PYTHONDONTWRITEBYTECODE;
# these are pinned in-profile so a real source mutation is never masked by an over-broad ignore.
# Deliberately narrow: root-anchored `.pytest_cache`/`.coverage` (pytest/coverage write these at
# rootdir only), and bytecode strictly under `__pycache__` or with a `.pyc`/`.pyo` suffix at any
# depth. A same-named directory buried elsewhere (e.g. notes/.pytest_cache/*) is NOT excused.
_PYTEST_BYPRODUCT_IGNORE_GLOBS: tuple[str, ...] = (
    ".pytest_cache",
    ".pytest_cache/*",
    "**/__pycache__/*",
    "**/*.pyc",
    "**/*.pyo",
    ".coverage",
    # Structured-outcome junit artifact written by the pytest entrypoint under artifact root.
    ".builder/artifacts/verification-junit.xml",
)


SUPPORTED_COMMAND_PROFILES: dict[str, BoundedCommandProfile] = {
    "platform_status": BoundedCommandProfile(
        profile="platform_status",
        step_id="platform_status",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "platform-status"),
        timeout_ceiling_seconds=120,
    ),
    "docs_audit": BoundedCommandProfile(
        profile="docs_audit",
        step_id="docs_audit",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "docs-audit"),
        timeout_ceiling_seconds=120,
    ),
    # V.3: validation_only fixed-argv profiles (not TARGET_CODE; no shell; no model).
    "wrp_doctor_backends": BoundedCommandProfile(
        profile="wrp_doctor_backends",
        step_id="wrp_doctor_backends",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "wrp-doctor-backends"),
        timeout_ceiling_seconds=60,
    ),
    "wrp_patterns_prove": BoundedCommandProfile(
        profile="wrp_patterns_prove",
        step_id="wrp_patterns_prove",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "wrp-patterns-prove"),
        timeout_ceiling_seconds=60,
    ),
    "wrp_fleet_fidelity": BoundedCommandProfile(
        profile="wrp_fleet_fidelity",
        step_id="wrp_fleet_fidelity",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "wrp-fleet-fidelity"),
        timeout_ceiling_seconds=60,
    ),
    "semantic_doctor": BoundedCommandProfile(
        profile="semantic_doctor",
        step_id="semantic_doctor",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "semantic-doctor"),
        timeout_ceiling_seconds=120,
    ),
    "semantic_map": BoundedCommandProfile(
        profile="semantic_map",
        step_id="semantic_map",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "semantic-map"),
        timeout_ceiling_seconds=300,
    ),
    "pytest_full": BoundedCommandProfile(
        profile="pytest_full",
        step_id="pytest_full",
        builder_self=False,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "pytest-full"),
        timeout_ceiling_seconds=MAX_TIMEOUT_SECONDS,
        byproduct_ignore_globs=_PYTEST_BYPRODUCT_IGNORE_GLOBS,
    ),
    "builder_full": BoundedCommandProfile(
        profile="builder_full",
        step_id="builder_full",
        builder_self=True,
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "builder-full"),
        timeout_ceiling_seconds=MAX_TIMEOUT_SECONDS,
        byproduct_ignore_globs=_PYTEST_BYPRODUCT_IGNORE_GLOBS,
    ),
}


def _read_json_object(path: Path) -> Any:
    return json_lib.loads(path.read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(value: str, limit: int = STDOUT_STDERR_CAPTURE_BYTES) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    clipped = encoded[:limit].decode("utf-8", errors="replace")
    return clipped, True


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_output_path(*, output: Path, target_repo: Path, artifact_root: Path) -> list[str]:
    errors: list[str] = []
    resolved_output = output.expanduser().resolve()
    if resolved_output.exists() and resolved_output.is_dir():
        errors.append("output path must be a file path, not a directory")
    if not _path_is_relative_to(resolved_output, artifact_root) or resolved_output == artifact_root:
        errors.append("output path must be under the configured artifact root inside target_repo")
    if not _path_is_relative_to(artifact_root, target_repo):
        errors.append("artifact_root must resolve inside target_repo")
    return errors


def _minimal_env(target_repo: Path, *, allow_target_repo_imports: bool) -> dict[str, str]:
    """Compose the child environment. `allow_target_repo_imports` is deliberately required.

    The runner spawns children with `cwd=target_repo`. Python then puts the target repository at
    `sys.path[0]`, and the old unconditional `PYTHONPATH=target_repo` put it there a second time.
    Two consequences, both confirmed by running them:

    - the target's `sitecustomize.py` is imported by `site` at interpreter startup, before `main()`;
    - the target's `builder_ii/` package shadows builder-II's own, so
      `-m builder_ii.verification_runner_entrypoints` dispatches the *target's* module.

    So `platform_status` and `docs_audit` -- the two profiles documented as running builder-II's own
    checks and never the target's code -- executed target code. The repository under verification
    supplied the auditor that cleared it. `VERIFICATION_ISOLATION_RFC.md` names the shape: "there is
    nothing an isolated run can evidence that an unisolated run could not forge."

    `PYTHONSAFEPATH` removes `sys.path[0]`, and `BUILDER_II_IMPORT_ROOT` always precedes the target,
    so every child resolves `builder_ii` to the verifying code. A target-code profile still gets the
    target on the path -- it runs the target's suite by design (D7) -- but it can no longer replace
    the runner's own dispatch module on the way there.

    The caller derives this flag from `TARGET_CODE_EXECUTING_PROFILES`, the same constant that makes
    the approval demand an execution-risk acknowledgement. One list, two consequences: a profile the
    operator must knowingly accept target-code risk for is exactly a profile allowed to import target
    code. A second, independent flag here would be a second place to forget.
    """
    env = {key: value for key, value in os.environ.items() if key in SAFE_ENV_KEYS}
    import_roots = [str(BUILDER_II_IMPORT_ROOT)]
    if allow_target_repo_imports:
        import_roots.append(str(target_repo))
    env.update(
        {
            "CORE_REPO_PATH": ".",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": os.pathsep.join(import_roots),
            # Drop `sys.path[0]` (the cwd, i.e. the target repo). Without this, PYTHONPATH ordering
            # is irrelevant: cwd precedes it and the target shadows `builder_ii` anyway.
            "PYTHONSAFEPATH": "1",
            # Suppress __pycache__/*.pyc so a pytest run does not create bytecode byproducts
            # that would otherwise register as workspace changes.
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def _validate_fixed_profile(profile: BoundedCommandProfile, verification_profile: str) -> list[str]:
    errors: list[str] = []
    if profile.profile not in SUPPORTED_COMMAND_PROFILES:
        errors.append("unsupported verification command profile")
    if profile.step_id != profile.profile:
        errors.append("step_id must match fixed profile id")
    # A builder-II self-verification profile (it runs builder-II's own matrix/docs checks) is only
    # meaningful when the target IS builder-II; refuse it under any non-builder verification profile.
    if profile.builder_self and verification_profile != B1_1_SUPPORTED_VERIFICATION_PROFILE:
        errors.append(
            f"profile {profile.profile} runs builder-II's own checks and requires "
            f"verification_profile={B1_1_SUPPORTED_VERIFICATION_PROFILE}"
        )
    if not profile.argv or not all(isinstance(item, str) and item for item in profile.argv):
        errors.append("fixed argv must be a non-empty tuple of non-empty strings")
        return errors
    for index, item in enumerate(profile.argv):
        lowered = item.lower()
        for token in FORBIDDEN_ARG_TOKENS:
            if token in lowered:
                errors.append(f"fixed argv[{index}] contains forbidden shell token {token!r}")
    if any(item in {"-c", "--command"} for item in profile.argv):
        errors.append("fixed argv must not use python -c or command-string forms")
    if profile.timeout_ceiling_seconds <= 0:
        errors.append("timeout_ceiling_seconds must be positive")
    return errors


def _git_commit_identity(target_repo: Path) -> tuple[str | None, str | None]:
    """Return (head_sha, branch) for the target repo, or (None, None) if not a git repo.

    A single `git rev-parse HEAD --abbrev-ref HEAD` yields the full HEAD SHA on line 1 and
    the branch short-name (or "HEAD" when detached) on line 2. Failures degrade to None so a
    non-git target still produces a valid receipt (with null commit identity) rather than
    crashing the runner.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD", "--abbrev-ref", "HEAD"],
            cwd=target_repo,
            env=_minimal_env(target_repo, allow_target_repo_imports=False),
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT_SECONDS,
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None, None
    if result.returncode != 0:
        return None, None
    lines = result.stdout.splitlines()
    head_sha = lines[0].strip() if lines else ""
    branch = lines[1].strip() if len(lines) > 1 else ""
    return (head_sha or None), (branch or None)


def _git_state(target_repo: Path, label: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=target_repo,
            env=_minimal_env(target_repo, allow_target_repo_imports=False),
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "state_label": label,
            "captured": False,
            "error": "git status timed out",
        }
    except OSError as exc:
        return {
            "state_label": label,
            "captured": False,
            "error": f"git status failed: {exc}",
        }
    head_sha, branch = _git_commit_identity(target_repo)
    return {
        "state_label": label,
        "captured": result.returncode == 0,
        "returncode": result.returncode,
        "porcelain_sha256": _sha256_text(result.stdout),
        "porcelain_lines": result.stdout.splitlines(),
        "clean": result.returncode == 0 and not result.stdout.splitlines(),
        "stderr_sha256": _sha256_text(result.stderr),
        "head_sha": head_sha,
        "branch": branch,
    }


def _is_non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _porcelain_line_path(line: str) -> str:
    """Extract the file path from a `git status --porcelain=v1` line (handles renames/quoting)."""
    if len(line) < 4:
        return line.strip().strip('"')
    status = line[:2]
    remainder = line[3:]
    # git only emits 'ORIG -> NEW' for rename/copy status codes (R/C). Gating on the status
    # prevents an attacker-named untracked file like `evil.py -> shadow.pyc` from being
    # mis-parsed down to its post-arrow segment.
    if ("R" in status or "C" in status) and " -> " in remainder:
        remainder = remainder.split(" -> ", 1)[1]
    return remainder.strip().strip('"')


def _path_matches_glob(path: str, glob: str) -> bool:
    normalized = path.strip().strip('"')
    pure = PurePosixPath(normalized)
    if glob.startswith("**/"):  # match the tail at any depth
        tail = glob[3:]
        return any(fnmatch.fnmatch("/".join(pure.parts[index:]), tail) for index in range(len(pure.parts)))
    if "/" in glob:  # root-anchored directory prefix, e.g. ".pytest_cache/*"
        return fnmatch.fnmatch(normalized, glob)
    # bare token: match only a single-segment entry at the repo root, never a same-named
    # component buried at depth (so `notes/.pytest_cache/backdoor.py` is a mutation, not a byproduct).
    return "/" not in normalized and fnmatch.fnmatch(normalized, glob)


def _is_ignored_byproduct(path: str, ignore_globs: tuple[str, ...]) -> bool:
    return any(_path_matches_glob(path, glob) for glob in ignore_globs)


def _head_changed(preflight: dict[str, Any], postflight: dict[str, Any]) -> bool:
    pre = preflight.get("head_sha")
    post = postflight.get("head_sha")
    # A None (non-git target, or capture failure) must never fabricate a mutation.
    if pre is None or post is None:
        return False
    return pre != post


def _partition_workspace_changes(
    preflight: dict[str, Any], postflight: dict[str, Any], ignore_globs: tuple[str, ...]
) -> tuple[list[str], list[str], bool]:
    """Split the pre/post porcelain delta into recorded byproducts vs. real mutations.

    Returns (observed_byproducts, mutation_paths, head_changed). A byproduct matches the
    profile's pinned ignore-globs; anything else is a genuine workspace mutation. A HEAD
    SHA change (a commit made during the run) is always a mutation, never ignorable.
    """
    pre_lines = set(preflight.get("porcelain_lines") or [])
    post_lines = set(postflight.get("porcelain_lines") or [])
    changed_lines = (post_lines - pre_lines) | (pre_lines - post_lines)
    changed_paths = sorted({path for line in changed_lines if (path := _porcelain_line_path(line))})
    byproducts = [path for path in changed_paths if _is_ignored_byproduct(path, ignore_globs)]
    mutations = [path for path in changed_paths if not _is_ignored_byproduct(path, ignore_globs)]
    return byproducts, mutations, _head_changed(preflight, postflight)


def _resolve_effective_timeout(plan: dict[str, Any], profile: BoundedCommandProfile) -> tuple[int, list[str]]:
    """Resolve the effective subprocess timeout from the approved plan (D7), fail-closed on drift.

    The timeout is the plan's per-profile declaration, range-checked to [1, 1800]s and then
    clamped to the profile's code-level ceiling. There is no silent default: a missing or
    out-of-range plan timeout is an error that blocks execution.
    """
    declared = plan_timeout_for_profile(plan, profile.profile)
    if declared is None:
        return 0, [f"plan does not declare a timeout_seconds for profile {profile.profile}"]
    if declared < MIN_TIMEOUT_SECONDS or declared > MAX_TIMEOUT_SECONDS:
        return 0, [
            f"plan timeout_seconds for profile {profile.profile} must be within "
            f"[{MIN_TIMEOUT_SECONDS}, {MAX_TIMEOUT_SECONDS}] seconds"
        ]
    return min(declared, profile.timeout_ceiling_seconds), []


def _count_from_pytest_summary(text: str, label: str) -> int:
    import re

    match = re.search(rf"(\d+)\s+{label}", text)
    return int(match.group(1)) if match else 0


def _parse_junit_structured_outcome(junit_path: Path) -> dict[str, Any] | None:
    if not junit_path.is_file():
        return None
    try:
        raw = junit_path.read_bytes()
    except OSError:
        return None
    # defusedxml hardens JUnit parsing against XML entity/DTD attacks (billion-laughs, XXE) even
    # though the target repo is D7-trusted; a subprocess-produced file is still external input.
    from defusedxml.common import DefusedXmlException
    from defusedxml.ElementTree import ParseError, fromstring

    try:
        root = fromstring(raw)
    except ParseError:
        return {
            "source": "junit_xml",
            "path": junit_path.as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "parse_error": "invalid junit xml",
        }
    except DefusedXmlException:
        # Forbidden construct (entity/DTD/external reference — EntitiesForbidden and friends are
        # ValueError subclasses, not ParseError): refuse the content but keep this parser's
        # never-raise degradation contract, so the execution receipt is still written.
        return {
            "source": "junit_xml",
            "path": junit_path.as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "parse_error": "forbidden xml construct refused (entities/DTD/external references)",
        }
    # junit may be <testsuite> or <testsuites><testsuite ...>
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites and root.tag.endswith("testsuite"):
        suites = [root]
    passed = failed = skipped = errors = 0
    tests = 0
    for suite in suites:
        suite_tests = int(suite.attrib.get("tests") or 0)
        suite_failures = int(suite.attrib.get("failures") or 0)
        suite_errors = int(suite.attrib.get("errors") or 0)
        suite_skipped = int(suite.attrib.get("skipped") or 0)
        tests += suite_tests
        failed += suite_failures
        errors += suite_errors
        skipped += suite_skipped
        passed += max(suite_tests - suite_failures - suite_errors - suite_skipped, 0)
    return {
        "source": "junit_xml",
        "path": junit_path.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "tests": tests,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
    }


def _structured_outcome_for_profile(
    *,
    profile: BoundedCommandProfile,
    completed: subprocess.CompletedProcess[str],
    target_repo: Path | None,
) -> dict[str, Any] | None:
    """Machine-readable pass/fail/skip evidence for pytest-bearing profiles."""
    if profile.profile not in {"pytest_full", "builder_full"}:
        return None
    junit_path = (target_repo / ".builder" / "artifacts" / "verification-junit.xml") if target_repo else None
    if junit_path is not None:
        from_junit = _parse_junit_structured_outcome(junit_path)
        if from_junit is not None:
            return from_junit
    combined = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    return {
        "source": "pytest_summary",
        "passed": _count_from_pytest_summary(combined, "passed"),
        "failed": _count_from_pytest_summary(combined, "failed"),
        "skipped": _count_from_pytest_summary(combined, "skipped"),
        "errors": _count_from_pytest_summary(combined, "error"),
    }


def _process_result_from_completed(
    *,
    profile: BoundedCommandProfile,
    completed: subprocess.CompletedProcess[str],
    effective_timeout: int,
    command_profile_ref: str,
    timed_out: bool = False,
    target_repo: Path | None = None,
) -> dict[str, Any]:
    stdout_excerpt, stdout_truncated = _excerpt(completed.stdout or "")
    stderr_excerpt, stderr_truncated = _excerpt(completed.stderr or "")
    status = "success" if completed.returncode == 0 else "non_zero_exit"
    if timed_out:
        status = "timeout"
    argv = list(profile.argv)
    if argv and argv[0] == sys.executable:
        argv[0] = "python"
    result: dict[str, Any] = {
        "step_id": profile.step_id,
        "profile": profile.profile,
        "command_profile_ref": command_profile_ref,
        "status": status,
        "returncode": completed.returncode,
        "timeout_seconds": effective_timeout,
        "shell": False,
        # Exact fixed argv (code-defined, token-scanned) — not just the digest — so a receipt
        # is self-describing without binding to a particular builder-II source revision.
        "argv": argv,
        "argv_digest": _sha256_text(json_lib.dumps(argv, sort_keys=True)),
        "stdout_sha256": _sha256_text(completed.stdout or ""),
        "stderr_sha256": _sha256_text(completed.stderr or ""),
        "stdout_excerpt": stdout_excerpt,
        "stderr_excerpt": stderr_excerpt,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }
    structured = _structured_outcome_for_profile(
        profile=profile, completed=completed, target_repo=target_repo
    )
    if structured is not None:
        result["structured_outcome"] = structured
    return result


def _blocked_process_result(*, profile: str, step_id: str, reason: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "profile": profile,
        "status": "blocked_before_execution",
        "reason": reason,
        "shell": False,
    }


def _maybe_write_blocked_receipt(
    *,
    receipt: dict[str, Any],
    output: Path,
    target_repo: Path | None,
    artifact_root: Path | None,
) -> None:
    if target_repo is None or artifact_root is None:
        return
    if _validate_output_path(output=output, target_repo=target_repo, artifact_root=artifact_root):
        return
    write_verification_execution_receipt(receipt, output)


def _receipt_for_block(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    plan_path: Path,
    approval_path: Path,
    output: Path,
    target_repo: Path | None,
    artifact_root: Path | None,
    requested_profile: str,
    errors: list[str],
    authority_decision: CommandAuthorityDecision | None = None,
) -> dict[str, Any]:
    profile = SUPPORTED_COMMAND_PROFILES.get(requested_profile)
    process_result = _blocked_process_result(
        profile=requested_profile,
        step_id=profile.step_id if profile else requested_profile,
        reason="; ".join(errors),
    )
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        receipt_status="BLOCKED_BEFORE_EXECUTION",
        executed_steps=[],
        skipped_steps=[
            {
                "step_id": process_result["step_id"],
                "status": "blocked_before_execution",
                "reason": process_result["reason"],
            }
        ],
        process_results=[process_result],
        preflight_git_state={"state_label": "preflight", "captured": False, "errors": errors},
        postflight_git_state={"state_label": "postflight", "captured": False, "errors": errors},
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt["errors"] = list(dict.fromkeys(list(receipt.get("errors") or []) + errors))
    receipt["valid"] = False
    if authority_decision is None:
        try:
            authority_decision = enforce_command_authority(
                "builder-verify run-approved",
                requested_effects=("artifact_writes", "readonly_subprocess"),
                capability_ref="HITL-approved verification execution",
                hitl_bound=False,
            )
        except CommandAuthorityError:
            authority_decision = check_command_authority(
                "builder-verify run-approved",
                requested_effects=("artifact_writes", "readonly_subprocess"),
                capability_ref="HITL-approved verification execution",
                hitl_bound=False,
            )
    receipt["command_authority_decision"] = authority_decision.to_evidence()
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    _maybe_write_blocked_receipt(
        receipt=receipt,
        output=output,
        target_repo=target_repo,
        artifact_root=artifact_root,
    )
    return receipt


def create_verification_runner_postflight(
    *, receipt: dict[str, Any], receipt_path: Path, plan_path: Path, approval_path: Path
) -> dict[str, Any]:
    postflight: dict[str, Any] = {
        "kind": "builder_ii.execution_postflight_record",
        "schema_version": 1,
        "target": {
            "name": receipt.get("target_profile"),
            "repo": receipt.get("target_repo"),
            "description": "verification runner target",
        },
        "request_ref": str(plan_path),
        "receipt_ref": str(receipt_path),
        "preflight_ref": "receipt.preflight_git_state",
        "approval_ref": str(approval_path),
        "expected_outcome": "bounded verification command completes without workspace mutation",
        "observed_state_ref": "receipt.postflight_git_state",
        "postflight_state": "RUN_COMPLETE",
        "performed_actions": [
            "validated receipt linkage",
            "compared preflight and postflight git fingerprints",
            "recorded no-mutation or mutation evidence",
        ],
        "receipt_digest": receipt.get("verification_execution_receipt_digest"),
        "workspace_mutation_detected": receipt.get("workspace_mutation_detected"),
        "preflight_git_state": receipt.get("preflight_git_state"),
        "postflight_git_state": receipt.get("postflight_git_state"),
        "artifact_is_authority": False,
        "governance": {
            "runtime_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "git_mutation": "DISABLED",
            "network_access": "DISABLED",
            "goose_runtime_activation": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
        "valid": True,
        "errors": [],
    }
    if receipt.get("workspace_mutation_detected") is True:
        postflight["valid"] = False
        postflight["errors"] = ["postflight detected workspace mutation"]
    errors = validate_execution_postflight_record(postflight)
    if errors:
        postflight["valid"] = False
        postflight["errors"] = list(dict.fromkeys(list(postflight.get("errors") or []) + errors))
    postflight["postflight_digest"] = digest_jsonable(postflight, digest_key="postflight_digest")
    return postflight


def run_approved_verification(
    *,
    plan_path: Path,
    approval_path: Path,
    output: Path,
    requested_profile: str = "platform_status",
) -> dict[str, Any]:
    plan_data = _read_json_object(plan_path)
    approval_data = _read_json_object(approval_path)
    plan = plan_data if isinstance(plan_data, dict) else {}
    approval = approval_data if isinstance(approval_data, dict) else {}
    profile = SUPPORTED_COMMAND_PROFILES.get(requested_profile)
    # The ref namespace tracks the plan's verification_profile (builder_full for builder-II, or a
    # generic/core profile for a target repo); the effective ref is computed from it (B4.2 / 1.3).
    verification_profile = str(plan.get("verification_profile") or "")
    effective_command_profile_ref = (
        _effective_command_profile_ref(verification_profile, profile.profile) if profile is not None else ""
    )
    errors: list[str] = []

    errors.extend(validate_verification_execution_plan_artifact(plan_data))
    errors.extend(validate_verification_execution_approval_artifact(approval_data))
    if isinstance(plan_data, dict) and plan_data.get("valid") is not True:
        errors.append("referenced verification execution plan must be valid (valid=true)")
    if isinstance(approval_data, dict) and approval_data.get("valid") is not True:
        errors.append("referenced verification execution approval must be valid (valid=true)")
    if not errors:
        errors.extend(validate_verification_execution_approval_against_plan(approval, plan))

    try:
        authority_decision = enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_writes", "readonly_subprocess"),
            capability_ref="HITL-approved verification execution",
            approval_ref=str(approval_path),
            subject_digest=plan.get("verification_execution_plan_digest"),
        )
    except CommandAuthorityError as e:
        authority_decision = check_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_writes", "readonly_subprocess"),
            capability_ref="HITL-approved verification execution",
            approval_ref=str(approval_path),
            subject_digest=plan.get("verification_execution_plan_digest"),
        )
        errors.append(str(e))
    if not authority_decision.allowed:
        errors.append(f"command authority denied: {authority_decision.reason}")
    if profile is None:
        errors.append("unsupported verification command profile")
    else:
        errors.extend(_validate_fixed_profile(profile, verification_profile))

    target_repo = Path(str(plan.get("target_repo", "."))).expanduser().resolve()
    artifact_root_value = str(plan.get("artifact_root", ".builder/verification"))
    artifact_root_path = Path(artifact_root_value).expanduser()
    artifact_root = (
        artifact_root_path.resolve()
        if artifact_root_path.is_absolute()
        else (target_repo / artifact_root_path).resolve()
    )

    if not target_repo.exists() or not target_repo.is_dir():
        errors.append("target_repo must exist and be a directory")
    if not _path_is_relative_to(artifact_root, target_repo):
        errors.append("artifact_root must resolve inside target_repo")
    errors.extend(_validate_output_path(output=output, target_repo=target_repo, artifact_root=artifact_root))

    approved_profiles = approval.get("approved_command_profiles", [])
    approved_steps = approval.get("approved_step_ids", [])
    if profile is not None:
        if not isinstance(approved_profiles, list) or profile.profile not in approved_profiles:
            errors.append("requested command profile is not approved by approval artifact")
        if not isinstance(approved_steps, list) or profile.step_id not in approved_steps:
            errors.append("requested step id is not approved by approval artifact")

    # D7 execution-risk acknowledgment + plan-sourced timeout. Both are resolved before any
    # subprocess is spawned; a target-code profile without an acknowledged approval, or a
    # missing/out-of-range plan timeout, blocks fail-closed.
    effective_timeout = 0
    if profile is not None:
        if profile.profile in TARGET_CODE_EXECUTING_PROFILES and (
            approval.get("execution_risk_acknowledged") is not True
            or not _is_non_empty(approval.get("acknowledged_risk"))
        ):
            errors.append(
                f"execution-risk acknowledgment required before running target-code profile "
                f"{profile.profile}: the approval must set execution_risk_acknowledged=true with a "
                "non-empty acknowledged_risk statement"
            )
        effective_timeout, timeout_errors = _resolve_effective_timeout(plan, profile)
        errors.extend(timeout_errors)

    if errors or profile is None:
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=list(dict.fromkeys(errors)),
            authority_decision=authority_decision,
        )

    preflight = _git_state(target_repo, "preflight")
    if not preflight.get("captured"):
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=["git preflight state could not be captured"],
            authority_decision=authority_decision,
        )

    # The approval subject is the exact source state named by the plan.  Check this
    # before isolation/backend construction and, critically, before spawning target
    # code.  Postflight drift remains a second defence; it cannot repair execution
    # that already happened against the wrong commit.
    plan_head_sha = plan.get("target_head_sha")
    if preflight.get("head_sha") != plan_head_sha:
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=["preflight HEAD SHA does not match approved plan target_head_sha"],
            authority_decision=authority_decision,
        )
    if profile.profile in TARGET_CODE_EXECUTING_PROFILES:
        if plan.get("tree_clean") is not True:
            return _receipt_for_block(
                plan=plan,
                approval=approval,
                plan_path=plan_path,
                approval_path=approval_path,
                output=output,
                target_repo=target_repo,
                artifact_root=artifact_root,
                requested_profile=requested_profile,
                errors=["target-code verification requires plan.tree_clean=true"],
                authority_decision=authority_decision,
            )
        if preflight.get("porcelain_lines"):
            return _receipt_for_block(
                plan=plan,
                approval=approval,
                plan_path=plan_path,
                approval_path=approval_path,
                output=output,
                target_repo=target_repo,
                artifact_root=artifact_root,
                requested_profile=requested_profile,
                errors=["target-code verification requires a clean preflight working tree"],
                authority_decision=authority_decision,
            )

    try:
        isolation_policy = plan.get("isolation_policy")
        isolation_backend = get_backend(str(target_repo), isolation_policy)

        if isolation_backend.name != "none":
            policy_digest = isolation_policy.get("verification_isolation_policy_digest") if isolation_policy else None
            if not policy_digest or len(policy_digest) != 64 or not all(c in "0123456789abcdef" for c in policy_digest):
                raise IsolationBackendError("isolation policy digest is missing or invalid")

        run_argv, run_env = isolation_backend.wrap_command(
            list(profile.argv),
            _minimal_env(
                target_repo,
                allow_target_repo_imports=profile.profile in TARGET_CODE_EXECUTING_PROFILES,
            ),
        )
    except IsolationBackendError as exc:
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=[f"isolation backend blocked execution: {exc}"],
            authority_decision=authority_decision,
        )

    try:
        completed = subprocess.run(
            run_argv,
            cwd=target_repo,
            env=run_env,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            shell=False,
        )
        process_result = _process_result_from_completed(
            profile=profile,
            completed=completed,
            effective_timeout=effective_timeout,
            command_profile_ref=effective_command_profile_ref,
            target_repo=target_repo,
        )
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            args=list(profile.argv),
            returncode=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "verification command timed out",
        )
        process_result = _process_result_from_completed(
            profile=profile,
            completed=completed,
            effective_timeout=effective_timeout,
            command_profile_ref=effective_command_profile_ref,
            timed_out=True,
            target_repo=target_repo,
        )

    postflight = _git_state(target_repo, "postflight")
    # A postflight git-state that could not be captured is itself evidence the run damaged the
    # repository (target code can delete/corrupt .git); treat it as a mutation, never fail-open.
    postflight_capture_failed = postflight.get("captured") is not True
    observed_byproducts, mutation_paths, head_changed = _partition_workspace_changes(
        preflight, postflight, profile.byproduct_ignore_globs
    )
    head_sha_mismatch = bool(plan_head_sha) and (postflight.get("head_sha") != plan_head_sha)
    workspace_mutation_detected = bool(mutation_paths) or head_changed or postflight_capture_failed or head_sha_mismatch
    receipt_status = "EXECUTED" if process_result["status"] == "success" else "FAILED"
    receipt_kwargs = dict(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        receipt_status=receipt_status,
        executed_steps=[
            {
                "step_id": profile.step_id,
                "status": process_result["status"],
                "profile": profile.profile,
            }
        ],
        skipped_steps=[],
        process_results=[process_result],
        preflight_git_state=preflight,
        postflight_git_state=postflight,
        workspace_mutation_detected=workspace_mutation_detected,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
        target_commit=preflight.get("head_sha"),
        target_branch=preflight.get("branch"),
        observed_byproducts=observed_byproducts,
        execution_risk_acknowledged=bool(approval.get("execution_risk_acknowledged")),
        acknowledged_risk=(
            approval.get("acknowledged_risk") if isinstance(approval.get("acknowledged_risk"), str) else None
        ),
    )
    isolation_policy = plan.get("isolation_policy")
    receipt_kwargs["isolation_backend"] = isolation_backend.name
    receipt_kwargs["isolation_status"] = "applied" if isolation_backend.name != "none" else "not_applied"
    receipt_kwargs["isolation_policy_digest"] = (
        isolation_policy.get("verification_isolation_policy_digest")
        if isolation_backend.name != "none" and isolation_policy else None
    )

    receipt = finalize_verification_execution_receipt(**receipt_kwargs)
    receipt["command_authority_decision"] = authority_decision.to_evidence()
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    if workspace_mutation_detected:
        detail_parts = list(mutation_paths)
        if head_changed:
            detail_parts.append("HEAD changed")
        if head_sha_mismatch:
            detail_parts.append("postflight HEAD SHA does not match plan target_head_sha")
        if postflight_capture_failed:
            detail_parts.append("postflight git state could not be captured")
        detail = "; ".join(detail_parts) or "unspecified change"
        receipt["errors"] = list(
            dict.fromkeys(list(receipt.get("errors") or []) + [f"workspace mutation detected: {detail}"])
        )
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")

    validation_errors = validate_verification_execution_receipt_artifact(receipt)
    validation_errors.extend(validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval))
    if validation_errors:
        receipt["errors"] = list(dict.fromkeys(list(receipt.get("errors") or []) + validation_errors))
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")

    postflight_path = output.with_name(output.stem + "-postflight.json")
    receipt["postflight_ref"] = {
        "path": str(postflight_path),
        "kind": "builder_ii.execution_postflight_record",
    }
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    write_verification_execution_receipt(receipt, output)

    postflight_record = create_verification_runner_postflight(
        receipt=receipt,
        receipt_path=output,
        plan_path=plan_path,
        approval_path=approval_path,
    )
    write_execution_postflight_record(postflight_record, postflight_path)
    return receipt
