from __future__ import annotations

import hashlib
import json as json_lib
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from builder_ii.approval_records import validate_approval_record_file
from builder_ii.config import Settings, load_settings
from builder_ii.goose_command_proposal import validate_goose_command_proposal_file
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_RECEIPT_SCHEMA_VERSION,
    _GOVERNANCE_DENIED_KEYS,
    validate_hitl_execution_request_file,
    write_hitl_execution_receipt,
)

# Commands strictly forbidden in the first tier of the HITL execution phase.
FORBIDDEN_COMMANDS = {
    "rm",
    "git push",
    "git commit",
    "git reset",
    "mv",
    "chmod",
    "chown",
    "sudo",
    "su",
    "docker exec",
    "curl",
    "wget",
    "nc",
}


def _validate_safety(command_str: str) -> None:
    try:
        tokens = shlex.split(command_str)
    except ValueError as e:
        raise ValueError(f"Could not parse command string: {e}")

    if not tokens:
        raise ValueError("Empty command string")

    # Super basic static analysis to prevent gross violations.
    # The true authority is the operator's cryptographic approval, but
    # defense-in-depth is the builder-II way.
    tokens_lower = [token.lower() for token in tokens]
    for forbidden in FORBIDDEN_COMMANDS:
        forbidden_tokens = [token.lower() for token in shlex.split(forbidden)]
        if tokens_lower[: len(forbidden_tokens)] == forbidden_tokens:
            raise ValueError(f"Command '{forbidden}' is forbidden by the execution gateway.")

    if "git" in tokens_lower and "push" in tokens_lower:
        raise ValueError("git push is forbidden by the execution gateway.")


def execute_hitl_command(
    request_path: Path,
    proposal_path: Path,
    approval_path: Path,
    output_dir: Path,
    settings: Settings | None = None,
) -> None:
    """
    Executes a governed command based on a fully approved HITL chain.
    """
    if settings is None:
        settings = load_settings()

    # 1. Validate all input artifacts
    req_errors = validate_hitl_execution_request_file(request_path)
    if req_errors:
        raise ValueError(f"Invalid execution request: {req_errors}")

    prop_errors = validate_goose_command_proposal_file(proposal_path)
    if prop_errors:
        raise ValueError(f"Invalid command proposal: {prop_errors}")

    app_errors = validate_approval_record_file(approval_path)
    if app_errors:
        raise ValueError(f"Invalid approval record: {app_errors}")

    req_data = json_lib.loads(request_path.read_text(encoding="utf-8"))
    prop_data = json_lib.loads(proposal_path.read_text(encoding="utf-8"))
    app_data = json_lib.loads(approval_path.read_text(encoding="utf-8"))

    # 2. Cryptographic and semantic binding checks
    # The approval MUST reference the exact proposal digest
    raw_prop = json_lib.dumps(prop_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proposal_digest = hashlib.sha256(raw_prop).hexdigest()

    # Extract decision from the nested structure
    decision_block = app_data.get("decision", {})
    decision_val = decision_block.get("value")

    # Extract digest from the nested proposal struct
    proposal_block = app_data.get("proposal", {})
    recorded_digest = proposal_block.get("sha256")

    if recorded_digest != proposal_digest:
        raise ValueError(
            f"Approval record digest '{recorded_digest}' does not match command proposal digest '{proposal_digest}'"
        )

    if decision_val != "approved":
        raise ValueError("Approval record does not contain an 'approved' decision.")

    # The command string must match the one proposed
    command_str = prop_data.get("command")
    if not command_str:
        raise ValueError("Command proposal contains no command string.")

    # Check for safety
    _validate_safety(command_str)

    # 3. Execution
    target_repo = Path(req_data["target"]["repo"])
    if not target_repo.exists() or not target_repo.is_dir():
        raise ValueError(f"Target repository {target_repo} does not exist or is not a directory.")

    started_at = int(time.time())

    try:
        # We use shell=False and shlex to prevent accidental shell injection bypasses.
        args = shlex.split(command_str)
        result = subprocess.run(
            args,
            cwd=target_repo,
            capture_output=True,
            check=False,
        )
        exit_code = result.returncode
        stdout_txt = result.stdout.decode("utf-8", errors="replace")
        stderr_txt = result.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        exit_code = -1
        stdout_txt = ""
        stderr_txt = str(e)

    completed_at = int(time.time())

    # Write output to files
    stdout_file = output_dir / "stdout.log"
    stderr_file = output_dir / "stderr.log"
    output_dir.mkdir(parents=True, exist_ok=True)

    stdout_file.write_text(stdout_txt, encoding="utf-8")
    stderr_file.write_text(stderr_txt, encoding="utf-8")

    # 4. Generate Executed Receipt
    receipt = {
        "kind": HITL_EXECUTION_RECEIPT_KIND,
        "schema_version": HITL_EXECUTION_RECEIPT_SCHEMA_VERSION,
        "target": req_data["target"],
        "request_ref": str(request_path),
        "execution_state": "EXECUTED",
        "exit_code": exit_code,
        "stdout_ref": str(stdout_file),
        "stderr_ref": str(stderr_file),
        "started_at": started_at,
        "completed_at": completed_at,
        "performed_actions": ["execute_command"],
        "current_state": "EXECUTION_COMPLETE",
        "artifact_is_authority": True,
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "OPERATIONALLY_VERIFIED",
            **{key: "DISABLED" for key in _GOVERNANCE_DENIED_KEYS if key != "command_execution"},
            "command_execution": "OPERATIONALLY_VERIFIED",
            "artifact_is_authority": True,
            "core_workbench_coupling": "NONE",
        },
    }

    receipt_file = output_dir / "hitl_execution_receipt.json"
    write_hitl_execution_receipt(receipt, receipt_file)
