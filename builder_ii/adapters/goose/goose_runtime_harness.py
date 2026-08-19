from __future__ import annotations

import asyncio
import hashlib
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
from builder_ii.core.config import Settings
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


async def _get_target_files_async(target_root: Path) -> dict[str, str]:
    """Asynchronously snapshot target files using threadpool executor to avoid GIL blocks."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _get_target_files, target_root)


class GooseRuntimeHarness:
    def __init__(self, settings: Settings, session_plan: SessionPlan, target_root: Path):
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

    def _resolve_governed_target_profile(self) -> str:
        """Resolve target identity through the canonical governed config precedence."""
        from builder_ii.core.config_sources import resolve_config_sources

        project_root = Path(self.settings.project_root).resolve()
        # The target repository is already resolved by the primary builder-start path. Override
        # only that path while letting canonical config precedence resolve active_target_profile.
        resolution = resolve_config_sources(
            project_root=project_root,
            cli_overrides={"target_repo": str(self.target_root.resolve())},
        )
        if resolution.errors:
            raise ValueError("Invalid governed target configuration: " + "; ".join(resolution.errors))
        target_profile = resolution.value("active_target_profile")
        if target_profile not in _TARGET_PROFILES:
            raise ValueError("Invalid governed target profile; expected generic, builder, or core.")
        return target_profile

    def admit_governed(self) -> tuple[Any, str]:
        """Perform governed admission before any backend or Goose spawn."""
        if not self.session_id or not _SESSION_ID_RE.fullmatch(self.session_id):
            raise ValueError("Invalid Goose session identity; use 1-128 path-safe letters, digits, '.', '_' or '-'.")
        if not self.target_root.is_dir():
            raise ValueError(f"Invalid Goose target identity; target directory does not exist: {self.target_root}")
        project_root = Path(self.settings.project_root).resolve()
        if not project_root.is_dir():
            raise ValueError(f"Invalid Builder-II project root for governed MCP configuration: {project_root}")
        target_profile = self._resolve_governed_target_profile()
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
        recipe = self._governed_recipe_path()
        if self._governed_admission is None:
            self.admit_governed()
        compatibility, recipe_digest = self._governed_admission
        target_profile = self._admitted_target_profile
        project_root = self._admitted_project_root
        if target_profile is None or project_root is None:
            raise RuntimeError("Governed Goose admission did not bind MCP target/config identity.")
        if self._resolve_governed_target_profile() != target_profile:
            raise ValueError("Governed target profile changed after admission; refusing to spawn Goose.")
        if Path(self.settings.project_root).resolve() != project_root:
            raise ValueError("Builder-II project root changed after admission; refusing to spawn Goose.")

        goose = compatibility.binary
        env = goose_env(self.settings, session=self.session_plan)
        env["GOOSE_MODE"] = "auto"
        # Scope the MCP server's ledger and bind its target/config identities to this exact
        # admitted launch. The target repository itself remains Popen.cwd below.
        env["BUILDER_MCP_SESSION_ID"] = self.session_id
        env["BUILDER_MCP_TARGET_PROFILE"] = target_profile
        env["BUILDER_MCP_PROJECT_ROOT"] = str(project_root)

        argv = self._governed_argv(goose, recipe)
        self._preflight_snapshot = _get_target_files(self.target_root)

        start_time = _current_time_utc()
        # Keep the final inventory check adjacent to the process boundary: no
        # further recipe-dependent work occurs between this check and Popen.
        current_recipe_digest = validate_governed_recipe(recipe)
        if current_recipe_digest != recipe_digest:
            raise ValueError(
                "Governed Goose recipe changed after admission; refusing to spawn Goose. "
                "Re-admit the unchanged recipe and retry."
            )
        self._proc = subprocess.Popen(
            argv,
            cwd=self.target_root,
            env=env,
        )

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
            },
        )
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

    def close(self, launch_receipt_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Terminate Goose and verify no mutations occurred."""
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

        post_snapshot = _get_target_files(self.target_root)
        mutations: list[str] = []
        for file_path, digest in post_snapshot.items():
            if file_path not in self._preflight_snapshot or self._preflight_snapshot[file_path] != digest:
                mutations.append(file_path)
        for file_path in self._preflight_snapshot:
            if file_path not in post_snapshot:
                mutations.append(f"{file_path} (deleted)")

        postflight = create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root),
            start_time=end_time,  # approximate for schema
            end_time=end_time,
            files_checked=len(post_snapshot),
            mutations_detected=mutations,
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

        # Record goose_session_closed in the event ledger
        from builder_ii.governance.ledger.event_ledger import create_event_record, write_event_record

        event = create_event_record(
            event_id=self.session_id + "_close",
            session_id=self.session_id,
            sequence=0,
            event_type="goose_session_closed",
            stage="verification",
            subject_refs=[
                {
                    "kind": "builder_ii.goose_transcript",
                    "path": transcript_path,
                    "sha256": transcript_digest,
                    "role": "transcript",
                }
            ],
            command_surface="builder_ii",
            policy_snapshot_ref={"kind": "null"},
        )
        ledger_dir = self.target_root / ".builder" / "artifacts" / "events"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        write_event_record(event, ledger_dir / f"event_{event['sequence']:04d}_{event['event_id']}.json")

        return close_receipt, postflight

    async def close_async(self, launch_receipt_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
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

        postflight = create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root),
            start_time=end_time,
            end_time=end_time,
            files_checked=len(post_snapshot),
            mutations_detected=mutations,
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

        # Record goose_session_closed in the event ledger
        from builder_ii.governance.ledger.event_ledger import create_event_record, write_event_record

        event = create_event_record(
            event_id=self.session_id + "_close",
            session_id=self.session_id,
            sequence=0,
            event_type="goose_session_closed",
            stage="verification",
            subject_refs=[
                {
                    "kind": "builder_ii.goose_transcript",
                    "path": transcript_path,
                    "sha256": transcript_digest,
                    "role": "transcript",
                }
            ],
            command_surface="builder_ii",
            policy_snapshot_ref={"kind": "null"},
        )
        ledger_dir = self.target_root / ".builder" / "artifacts" / "events"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        write_event_record(event, ledger_dir / f"event_{event['sequence']:04d}_{event['event_id']}.json")

        return close_receipt, postflight
