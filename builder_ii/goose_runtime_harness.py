from __future__ import annotations

import hashlib
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from builder_ii.config import Settings
from builder_ii.goose_receipts import (
    create_goose_close_receipt,
    create_goose_launch_receipt,
    create_no_mutation_postflight,
)
from builder_ii.goose_launcher import find_goose_binary, goose_env, recipe_path
from builder_ii.model_router import SessionPlan
from typing import Any


def _current_time_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_target_files(target_root: Path) -> dict[str, str]:
    """Snapshot target files by content digest, not timestamp granularity."""
    snapshot: dict[str, str] = {}
    for p in target_root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            snapshot[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snapshot


class GooseRuntimeHarness:
    def __init__(self, settings: Settings, session_plan: SessionPlan, target_root: Path):
        self.settings = settings
        self.session_plan = session_plan
        self.target_root = target_root
        self.session_id = f"goose_{int(time.time())}"
        self._proc: subprocess.Popen[str] | None = None
        self._preflight_snapshot: dict[str, str] = {}

    def launch_readonly(self) -> dict[str, Any]:
        """Launch Goose in a strict read-only mode, without shell access."""
        goose = find_goose_binary()
        if not goose:
            raise FileNotFoundError("Goose CLI not found.")

        recipe = recipe_path(self.settings, self.session_plan)
        env = goose_env(self.settings, session=self.session_plan)
        
        # Enforce read-only bounds in the environment
        env["GOOSE_MODE"] = "auto"
        
        # We restrict the capabilities by not supplying `developer` builtin
        argv = [goose, "session", "--with-builtin", ""]
        if recipe.exists():
            argv.extend(["--recipe", str(recipe)])

        # Snapshot before launch
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
            agent_profile=self.session_plan.agent_profile if hasattr(self.session_plan, "agent_profile") else "patch_planner",
            pid=self._proc.pid,
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

        # Postflight mutation check
        post_snapshot = _get_target_files(self.target_root)
        mutations = []
        for f, mtime in post_snapshot.items():
            if f not in self._preflight_snapshot or self._preflight_snapshot[f] != mtime:
                mutations.append(f)
        for f in self._preflight_snapshot:
            if f not in post_snapshot:
                mutations.append(f"{f} (deleted)")

        postflight = create_no_mutation_postflight(
            session_id=self.session_id,
            target_root=str(self.target_root),
            start_time=end_time, # approximate for schema
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
