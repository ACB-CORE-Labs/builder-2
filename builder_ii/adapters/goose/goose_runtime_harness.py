from __future__ import annotations

import asyncio
import hashlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
        argv = [goose, "session", "--with-builtin", ""]
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
        )

    # Recipe whose sole extension is the builder-II governed MCP server (G2). Unlike
    # launch_readonly (which strips builtins so Goose has *no* tools), this gives Goose one
    # tool surface -- our server -- so its tool calls flow through the governed ceremony.
    GOVERNED_RECIPE_NAME = "governed-readonly.yaml"

    def _governed_recipe_path(self) -> Path:
        return self.settings.project_root / "recipes" / self.GOVERNED_RECIPE_NAME

    @staticmethod
    def _governed_argv(goose: str, recipe: Path) -> list[str]:
        """Goose argv for a governed session: no builtins, our recipe as the tool surface."""
        argv = [goose, "session", "--with-builtin", ""]
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
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = self._governed_recipe_path()
        env = goose_env(self.settings, session=self.session_plan)
        env["GOOSE_MODE"] = "auto"
        # Scope the MCP server's ledger to this run so its events land under this session.
        env["BUILDER_MCP_SESSION_ID"] = self.session_id

        argv = self._governed_argv(goose, recipe)
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
        )

    async def launch_readonly_async(self) -> dict[str, Any]:
        """Launch Goose asynchronously in strict read-only mode, avoiding loop blockage."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = goose_env(self.settings, session=self.session_plan)
        env["GOOSE_MODE"] = "auto"

        argv = [goose, "session", "--with-builtin", ""]
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

        transcript_path = str(Path.home() / ".config" / "goose" / "sessions" / self.session_id)

        close_receipt = create_goose_close_receipt(
            session_id=self.session_id,
            launch_receipt_digest=launch_receipt_digest,
            postflight_digest=postflight["digest"],
            transcript_path=transcript_path,
            end_time=end_time,
            exit_code=exit_code,
        )

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

        transcript_path = str(Path.home() / ".config" / "goose" / "sessions" / self.session_id)

        close_receipt = create_goose_close_receipt(
            session_id=self.session_id,
            launch_receipt_digest=launch_receipt_digest,
            postflight_digest=postflight["digest"],
            transcript_path=transcript_path,
            end_time=end_time,
            exit_code=exit_code,
        )

        return close_receipt, postflight
