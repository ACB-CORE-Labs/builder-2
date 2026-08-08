from __future__ import annotations

import asyncio
import hashlib
import subprocess
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.governed_invocation import (
    GooseCliCapabilities,
    GovernedInvocationError,
    plan_governed_headless_invocation,
)
from builder_ii.adapters.goose.goose_launcher import find_goose_binary, goose_env, recipe_path
from builder_ii.adapters.goose.goose_receipts import (
    create_goose_close_receipt,
    create_goose_launch_receipt,
    create_no_mutation_postflight,
)
from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.core.config import Settings
from builder_ii.governance.ledger.session_ledger import append_session_event
from builder_ii.routing.model_router import SessionPlan

_DIGEST_CHUNK_SIZE = 1024 * 1024
_executor = ThreadPoolExecutor(max_workers=4)


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


def _get_target_files(target_root: Path) -> dict[str, str]:
    """Snapshot target files by content digest, excluding governance/history state."""
    snapshot: dict[str, str] = {}
    for path in target_root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".builder" in path.parts:
            continue
        digest = _file_sha256(path)
        if digest is not None:
            snapshot[str(path)] = digest
    return snapshot


async def _get_target_files_async(target_root: Path) -> dict[str, str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _get_target_files, target_root)


def _bounded_utf8_prefix(text: str, max_bytes: int) -> bytes:
    """Return the longest UTF-8 prefix no larger than ``max_bytes``.

    Raw model output is convenience data, not evidence, but its disk bound is still a
    mechanical invariant.  Avoid cutting a multibyte code point so the resulting log remains
    valid UTF-8 for ordinary inspection.
    """
    if max_bytes <= 0:
        return b""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return encoded
    candidate = encoded[:max_bytes]
    while candidate:
        try:
            candidate.decode("utf-8")
            return candidate
        except UnicodeDecodeError as exc:
            candidate = candidate[: exc.start]
    return b""


class GooseRuntimeHarness:
    """Governed Goose process wrapper.

    The harness is deliberately not an authority source.  It assumes the CLI boundary has
    already performed command-authority/ratification checks, then enforces runtime mechanics:
    exact tool-surface shape, pre/post snapshots, mandatory lifecycle evidence, bounded raw
    output, wrapper-owned stop semantics, and close receipts.
    """

    GOVERNED_RECIPE_NAME = "governed-readonly.yaml"
    RUN_LOG_MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, settings: Settings, session_plan: SessionPlan, target_root: Path):
        self.settings = settings
        self.session_plan = session_plan
        self.target_root = Path(target_root)
        # Kept stable in this hardening slice for compatibility; Phase identity hardening
        # replaces timestamp-only identity with a collision-resistant run context.
        self.session_id = f"goose_{int(time.time())}"
        self._proc: subprocess.Popen[str] | None = None
        self._async_proc: asyncio.subprocess.Process | None = None
        self._preflight_snapshot: dict[str, str] = {}
        self._last_invocation_capabilities: GooseCliCapabilities | None = None
        self._last_governed_recipe_sha256: str | None = None
        self._last_task_sha256: str | None = None

    @property
    def builder_root(self) -> Path:
        """The event/evidence root shared by harness and governed MCP server."""
        return self.target_root / ".builder"

    def _export_transcript(self, transcript_path: str) -> None:
        """Best-effort convenience export; never substitutes for receipts/postflight."""
        goose = find_goose_binary()
        if not goose:
            return
        try:
            subprocess.run(
                [
                    goose,
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
        except OSError:
            return

    def _append_lifecycle_event(
        self,
        event_type: str,
        *,
        message: str,
        subject_refs: list[dict[str, Any]] | None = None,
        decision_result: str = "recorded",
    ) -> Path:
        """Persist one mandatory lifecycle event.

        Lifecycle evidence is constitutive of a governed run.  A start event that cannot be
        persisted means no child may start; a completion/close event that cannot be persisted
        means the wrapper must surface failure rather than silently claiming a governed close.
        """
        return append_session_event(
            builder_root=self.builder_root,
            session_id=self.session_id,
            event_type=event_type,
            command_surface="builder-goose",
            policy=build_read_only_policy(),
            subject_refs=subject_refs,
            message=message,
            decision_result=decision_result,
            event_id_prefix="evt_goose",
        )

    def launch_readonly(self) -> dict[str, Any]:
        """Launch the legacy strict read-only Goose session (no governed MCP tools)."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = dict(goose_env(self.settings, session=self.session_plan))
        env["GOOSE_MODE"] = "auto"

        argv = [goose, "session", "--with-builtin", "", "--name", self.session_id]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])

        self._preflight_snapshot = _get_target_files(self.target_root)
        self._append_lifecycle_event(
            "goose_readonly_started",
            message="read-only Goose session started with no builtins",
        )

        start_time = _current_time_utc()
        self._proc = subprocess.Popen(argv, cwd=self.target_root, env=env)
        return self._launch_receipt(start_time)

    def _governed_recipe_path(self) -> Path:
        return Path(self.settings.project_root) / "recipes" / self.GOVERNED_RECIPE_NAME

    def _governed_argv(self, goose: str, recipe: Path) -> list[str]:
        """Interactive governed argv; recipe interposition is mandatory, never optional."""
        if not recipe.is_file():
            raise GovernedInvocationError(
                f"governed recipe not found: {recipe}; refusing to start without MCP interposition"
            )
        return [
            goose,
            "session",
            "--with-builtin",
            "",
            "--name",
            self.session_id,
            "--recipe",
            str(recipe),
        ]

    def launch_governed(self) -> dict[str, Any]:
        """Launch interactive Goose with builder-II MCP as its only tool surface."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = self._governed_recipe_path()
        argv = self._governed_argv(goose, recipe)
        env = dict(goose_env(self.settings, session=self.session_plan))
        env["GOOSE_MODE"] = "auto"
        env["BUILDER_MCP_SESSION_ID"] = self.session_id

        self._preflight_snapshot = _get_target_files(self.target_root)
        # Mandatory evidence is written before the process exists.
        self._append_lifecycle_event(
            "goose_readonly_started",
            message=f"governed Goose session started under {self.GOVERNED_RECIPE_NAME}",
        )

        start_time = _current_time_utc()
        self._proc = subprocess.Popen(argv, cwd=self.target_root, env=env)
        return self._launch_receipt(start_time)

    @staticmethod
    def _goose_run_help(goose: str) -> str:
        """Observed ``goose run --help`` text, or empty when it cannot be inspected."""
        try:
            proc = subprocess.run(
                [goose, "run", "--help"], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return (proc.stdout or "") + "\n" + (proc.stderr or "")

    def _governed_run_argv(
        self, goose: str, recipe: Path, task: str, help_text: str
    ) -> list[str]:
        """Compatibility projection of advertised flags.

        Kept for existing diagnostics/tests.  The executing path does **not** use this
        best-effort projection; :meth:`run_governed_streaming` uses the strict planner below.
        """
        argv = [goose, "run"]
        if "--recipe" in help_text:
            argv.extend(["--recipe", str(recipe)])
        if "--name" in help_text:
            argv.extend(["--name", self.session_id])
        if "--with-builtin" in help_text:
            argv.extend(["--with-builtin", ""])
        if task and "--text" in help_text:
            argv.extend(["--text", task])
        return argv

    def supports_headless_run(self, goose: str) -> bool:
        """True only when the installed CLI can satisfy the *whole* governed contract."""
        help_text = self._goose_run_help(goose)
        return bool(help_text) and GooseCliCapabilities.from_run_help(
            help_text
        ).supports_governed_headless

    def run_governed_streaming(
        self,
        task: str,
        *,
        log_path: Path,
        on_line: Callable[[str], None] | None = None,
        child_env_overrides: Mapping[str, str] | None = None,
    ) -> tuple[dict[str, Any], int]:
        """Run a governed task headlessly under a complete, observed CLI contract."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        help_text = self._goose_run_help(goose)
        recipe = self._governed_recipe_path()
        invocation = plan_governed_headless_invocation(
            goose_binary=goose,
            recipe_path=recipe,
            task=task,
            session_id=self.session_id,
            help_text=help_text,
        )
        self._last_invocation_capabilities = invocation.capabilities
        self._last_governed_recipe_sha256 = invocation.recipe_sha256
        self._last_task_sha256 = invocation.task_sha256

        env = dict(goose_env(self.settings, session=self.session_plan))
        env["GOOSE_MODE"] = "auto"
        env["BUILDER_MCP_SESSION_ID"] = self.session_id
        if child_env_overrides:
            env.update({str(key): str(value) for key, value in child_env_overrides.items()})

        self._preflight_snapshot = _get_target_files(self.target_root)
        # Do not put raw task text in the evidence chain.  The task digest is sufficient to
        # identify this invocation until Phase identity introduces a dedicated task artifact.
        self._append_lifecycle_event(
            "goose_run_started",
            message=f"headless governed run started; task_sha256={invocation.task_sha256}",
        )

        start_time = _current_time_utc()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._proc = subprocess.Popen(
            list(invocation.argv),
            cwd=self.target_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        written = 0
        with log_path.open("wb") as log:
            if self._proc.stdout is not None:
                for line in self._proc.stdout:
                    remaining = self.RUN_LOG_MAX_BYTES - written
                    if remaining > 0:
                        chunk = _bounded_utf8_prefix(line, remaining)
                        if chunk:
                            log.write(chunk)
                            log.flush()
                            written += len(chunk)
                    if on_line is not None:
                        on_line(line.rstrip("\n"))
        exit_code = self._proc.wait()

        receipt = self._launch_receipt(start_time)
        self._append_lifecycle_event(
            "goose_run_completed",
            message=f"headless governed run exited with code {exit_code}",
            decision_result="recorded" if exit_code == 0 else "failed",
        )
        return receipt, exit_code

    def request_stop(self) -> bool:
        """Record stop intent first, then TERM -> bounded wait -> KILL the child if needed."""
        self._append_lifecycle_event(
            "run_stop_requested", message="operator requested stop", decision_result="stopped"
        )
        if self._proc is None or self._proc.poll() is not None:
            return False
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        return True

    async def launch_readonly_async(self) -> dict[str, Any]:
        """Launch the legacy read-only session asynchronously."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = dict(goose_env(self.settings, session=self.session_plan))
        env["GOOSE_MODE"] = "auto"
        argv = [goose, "session", "--with-builtin", "", "--name", self.session_id]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])

        self._preflight_snapshot = await _get_target_files_async(self.target_root)
        self._append_lifecycle_event(
            "goose_readonly_started",
            message="read-only Goose session started with no builtins",
        )

        start_time = _current_time_utc()
        self._async_proc = await asyncio.create_subprocess_exec(
            *argv, cwd=self.target_root, env=env
        )
        return create_goose_launch_receipt(
            session_id=self.session_id,
            target_profile=self._target_profile(),
            agent_profile=self._agent_profile(),
            pid=self._async_proc.pid,
            start_time=start_time,
        )

    def _target_profile(self) -> str:
        return (
            self.session_plan.target_name
            if hasattr(self.session_plan, "target_name")
            else "builder"
        )

    def _agent_profile(self) -> str:
        return (
            self.session_plan.agent_profile
            if hasattr(self.session_plan, "agent_profile")
            else "patch_planner"
        )

    def _launch_receipt(self, start_time: str) -> dict[str, Any]:
        if self._proc is None:
            raise RuntimeError("cannot create launch receipt before a child process exists")
        return create_goose_launch_receipt(
            session_id=self.session_id,
            target_profile=self._target_profile(),
            agent_profile=self._agent_profile(),
            pid=self._proc.pid,
            start_time=start_time,
        )

    def _postflight(self, *, end_time: str, post_snapshot: dict[str, str]) -> dict[str, Any]:
        mutations: list[str] = []
        for file_path, digest in post_snapshot.items():
            if (
                file_path not in self._preflight_snapshot
                or self._preflight_snapshot[file_path] != digest
            ):
                mutations.append(file_path)
        for file_path in self._preflight_snapshot:
            if file_path not in post_snapshot:
                mutations.append(f"{file_path} (deleted)")
        return create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root),
            start_time=end_time,
            end_time=end_time,
            files_checked=len(post_snapshot),
            mutations_detected=mutations,
        )

    def _close_receipt_and_event(
        self,
        *,
        launch_receipt_digest: str,
        postflight: dict[str, Any],
        exit_code: int,
        end_time: str,
    ) -> dict[str, Any]:
        transcript_path_obj = (
            self.target_root / ".builder" / "artifacts" / f"{self.session_id}.jsonl"
        )
        transcript_path_obj.parent.mkdir(parents=True, exist_ok=True)
        transcript_path = str(transcript_path_obj)
        self._export_transcript(transcript_path)
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
        refs = (
            [
                {
                    "kind": "builder_ii.goose_transcript",
                    "path": transcript_path,
                    "sha256": transcript_digest,
                    "role": "transcript",
                    "name": "session transcript",
                    "required": False,
                }
            ]
            if transcript_digest
            else []
        )
        self._append_lifecycle_event(
            "goose_readonly_closed",
            message=f"governed Goose session closed with exit code {exit_code}",
            subject_refs=refs,
            decision_result="recorded" if postflight["valid"] else "mutation_detected",
        )
        return close_receipt

    def close(self, launch_receipt_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Terminate the synchronous child, verify target state, and close the evidence chain."""
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
            exit_code = int(self._proc.returncode or 0)

        postflight = self._postflight(
            end_time=end_time, post_snapshot=_get_target_files(self.target_root)
        )
        close_receipt = self._close_receipt_and_event(
            launch_receipt_digest=launch_receipt_digest,
            postflight=postflight,
            exit_code=exit_code,
            end_time=end_time,
        )
        return close_receipt, postflight

    async def close_async(
        self, launch_receipt_digest: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Terminate the async child, verify target state, and close the evidence chain."""
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
            exit_code = int(self._async_proc.returncode or 0)

        postflight = self._postflight(
            end_time=end_time, post_snapshot=await _get_target_files_async(self.target_root)
        )

        # Async launch receipts use the same schema; close receipt/event creation is sync I/O
        # over local evidence files and is intentionally shared with the sync path.
        transcript_path_obj = (
            self.target_root / ".builder" / "artifacts" / f"{self.session_id}.jsonl"
        )
        transcript_path_obj.parent.mkdir(parents=True, exist_ok=True)
        transcript_path = str(transcript_path_obj)
        self._export_transcript(transcript_path)
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
        refs = (
            [
                {
                    "kind": "builder_ii.goose_transcript",
                    "path": transcript_path,
                    "sha256": transcript_digest,
                    "role": "transcript",
                    "name": "session transcript",
                    "required": False,
                }
            ]
            if transcript_digest
            else []
        )
        self._append_lifecycle_event(
            "goose_readonly_closed",
            message=f"governed Goose session closed with exit code {exit_code}",
            subject_refs=refs,
            decision_result="recorded" if postflight["valid"] else "mutation_detected",
        )
        return close_receipt, postflight
