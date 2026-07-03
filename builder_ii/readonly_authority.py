from __future__ import annotations

import hashlib
import json as json_lib
import re
import time
from pathlib import Path
from typing import Any

READ_POLICY_KIND = "builder_ii.read_policy"
READ_POLICY_SCHEMA_VERSION = 1

READ_RECEIPT_KIND = "builder_ii.read_receipt"
READ_RECEIPT_SCHEMA_VERSION = 1

CONTENT_READ_RECEIPT_KIND = "builder_ii.content_read_receipt"
CONTENT_READ_RECEIPT_SCHEMA_VERSION = 1
DEFAULT_MAX_CONTENT_READ_FILES = 16
DEFAULT_MAX_BYTES_PER_FILE = 256 * 1024
DEFAULT_MAX_EXCERPT_CHARS = 512

DENIED_READ_KIND = "builder_ii.denied_read"
DENIED_READ_SCHEMA_VERSION = 1

# Common secrets regex patterns or file suffixes
SECRET_PATTERNS = [
    re.compile(r"(?i)(api_key|private_key|password|secret|passwd|token)"),
]
SECRET_FILE_SUFFIXES = {".pem", ".key", ".pkcs12", ".p12", ".env"}


def create_read_policy(
    *,
    target_name: str,
    target_repo: Path,
    allowed_paths: list[str] | None = None,
    denied_paths: list[str] | None = None,
    max_bytes_budget: int = 10 * 1024 * 1024,  # 10MB default
    content_capture_allowed: bool = False,
    operator_note: str = "",
) -> dict[str, Any]:
    return {
        "kind": READ_POLICY_KIND,
        "schema_version": READ_POLICY_SCHEMA_VERSION,
        "target": {
            "name": target_name,
            "repo": str(target_repo.resolve()),
        },
        "allowed_paths": list(allowed_paths or []),
        "denied_paths": denied_paths or [".git/*", ".env*"],
        "max_bytes_budget": max_bytes_budget,
        "content_capture_allowed": content_capture_allowed,
        "operator_note": operator_note,
        "current_state": "OPERATIONALLY_VERIFIED",
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "EXPLICIT_READ_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": True,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_read_policy(policy: Any) -> list[str]:
    errors = []
    if not isinstance(policy, dict):
        return ["Read policy must be a dictionary"]
    if policy.get("kind") != READ_POLICY_KIND:
        errors.append(f"kind must be {READ_POLICY_KIND}")
    if policy.get("schema_version") != READ_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READ_POLICY_SCHEMA_VERSION}")

    target = policy.get("target")
    if not isinstance(target, dict):
        errors.append("target must be a dictionary")
    else:
        if not target.get("name"):
            errors.append("target.name is required")
        if not target.get("repo"):
            errors.append("target.repo is required")

    if not isinstance(policy.get("allowed_paths"), list):
        errors.append("allowed_paths must be a list")
    if not isinstance(policy.get("denied_paths"), list):
        errors.append("denied_paths must be a list")
    if not isinstance(policy.get("max_bytes_budget"), int) or policy.get("max_bytes_budget", -1) < 0:
        errors.append("max_bytes_budget must be a non-negative integer")
    if not isinstance(policy.get("content_capture_allowed"), bool):
        errors.append("content_capture_allowed must be a boolean")

    return errors


def validate_read_policy_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validate_read_policy(data)


def _is_path_allowed(path: Path, root: Path, allowed_patterns: list[str], denied_patterns: list[str]) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()

        # Prevent path traversal
        if not str(resolved).startswith(str(resolved_root)):
            return False

        # Secrets checks: filenames
        if resolved.suffix in SECRET_FILE_SUFFIXES:
            return False

        # Convert path to relative for pattern matching
        rel_path = resolved.relative_to(resolved_root).as_posix()

        # Check against denied patterns (glob matching)
        for pattern in denied_patterns:
            if path.match(pattern) or Path(rel_path).match(pattern):
                return False

        # Check against allowed patterns (glob matching)
        allowed = False
        for pattern in allowed_patterns:
            if pattern == "*" or path.match(pattern) or Path(rel_path).match(pattern):
                allowed = True
                break

        return allowed
    except Exception:
        return False


def _check_secrets_content(content: bytes) -> bool:
    try:
        text = content.decode("utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return False
        return True
    except Exception:
        return True


def execute_governed_read(
    policy: dict[str, Any],
    file_path: Path,
    current_read_bytes: int = 0,
) -> dict[str, Any]:
    """Execute a governed read operation on a single file, enforcing the read policy.

    Returns a read_receipt or denied_read artifact.
    """
    target_repo = Path(policy["target"]["repo"])
    allowed_paths = policy["allowed_paths"]
    denied_paths = policy["denied_paths"]
    budget = policy["max_bytes_budget"]
    content_capture = policy["content_capture_allowed"]

    # Pre-read metadata
    resolved = file_path.resolve()

    # 1. Path Travel / Allowlist validation
    if not _is_path_allowed(resolved, target_repo, allowed_paths, denied_paths):
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Path not allowed or security policy violation (traversal, .git, secret suffixes)",
        )

    if not resolved.exists():
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="File not found",
        )

    if not resolved.is_file():
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Path is not a file",
        )

    if not allowed_paths:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Read policy has no allowed paths; explicit allowlist is required",
        )

    # Read size check
    file_size = resolved.stat().st_size
    if current_read_bytes + file_size > budget:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason=f"Read budget exceeded (limit: {budget} bytes, requested size: {file_size} bytes)",
        )

    # Verify modification time before read
    mtime_before = resolved.stat().st_mtime

    sha = hashlib.sha256()
    captured_chunks: list[bytes] = []
    binary_detected = False
    secret_detected = False
    try:
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                sha.update(chunk)
                if b"\x00" in chunk:
                    binary_detected = True
                if _check_secrets_content(chunk) is False:
                    secret_detected = True
                if content_capture:
                    captured_chunks.append(chunk)
    except Exception as e:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason=f"Failed to read file: {e}",
        )

    # Verify modification time after read to check for concurrent writes
    mtime_after = resolved.stat().st_mtime
    if mtime_before != mtime_after:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="File was modified during read",
        )

    # Secrets filtering
    if binary_detected:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Security policy violation: binary content is not readable through governed read",
        )

    if secret_detected:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Security policy violation: detected potential secrets in content",
        )

    # Hash calculation
    sha256 = sha.hexdigest()

    # Build receipt
    receipt = {
        "kind": READ_RECEIPT_KIND,
        "schema_version": READ_RECEIPT_SCHEMA_VERSION,
        "policy_ref": policy.get("kind"),
        "target_file": str(resolved),
        "bytes_read": file_size,
        "sha256": sha256,
        "captured_at": int(time.time()),
        "content": b"".join(captured_chunks).decode("utf-8", errors="replace") if content_capture else None,
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "EXPLICIT_READ_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    return receipt


def create_denied_read(
    policy: dict[str, Any],
    file_path: Path,
    reason: str,
) -> dict[str, Any]:
    return {
        "kind": DENIED_READ_KIND,
        "schema_version": DENIED_READ_SCHEMA_VERSION,
        "target_file": str(file_path.resolve()),
        "reason": reason,
        "timestamp": int(time.time()),
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "EXPLICIT_READ_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_read_receipt(receipt: Any) -> list[str]:
    errors = []
    if not isinstance(receipt, dict):
        return ["Read receipt must be a dictionary"]
    if receipt.get("kind") != READ_RECEIPT_KIND:
        errors.append(f"kind must be {READ_RECEIPT_KIND}")
    if receipt.get("schema_version") != READ_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READ_RECEIPT_SCHEMA_VERSION}")
    if not isinstance(receipt.get("target_file"), str) or not receipt.get("target_file"):
        errors.append("target_file must be a non-empty string")
    if not isinstance(receipt.get("bytes_read"), int) or receipt.get("bytes_read", -1) < 0:
        errors.append("bytes_read must be a non-negative integer")
    if not isinstance(receipt.get("sha256"), str) or len(receipt.get("sha256", "")) != 64:
        errors.append("sha256 must be a SHA-256 hex digest")
    return errors


def validate_read_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validate_read_receipt(data)


def _redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def execute_content_read(
    policy: dict[str, Any],
    file_path: Path,
    *,
    max_bytes_per_file: int = DEFAULT_MAX_BYTES_PER_FILE,
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
    current_read_bytes: int = 0,
) -> dict[str, Any]:
    """Bounded content-read lane: explicit paths only, with digest and redacted excerpt."""
    target_repo = Path(policy["target"]["repo"])
    allowed_paths = policy["allowed_paths"]
    denied_paths = policy["denied_paths"]
    budget = policy["max_bytes_budget"]
    resolved = file_path.resolve()

    if resolved.is_symlink():
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Symlink paths are not readable through governed content-read",
        )

    if not _is_path_allowed(resolved, target_repo, allowed_paths, denied_paths):
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Path not allowed or security policy violation (traversal, .git, secret suffixes)",
        )

    if not resolved.exists() or not resolved.is_file():
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="File not found or path is not a file",
        )

    if not allowed_paths:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason="Read policy has no allowed paths; explicit allowlist is required",
        )

    file_size = resolved.stat().st_size
    if current_read_bytes + file_size > budget:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason=f"Read budget exceeded (limit: {budget} bytes, requested size: {file_size} bytes)",
        )
    if file_size > max_bytes_per_file:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason=f"File exceeds max_bytes_per_file limit ({max_bytes_per_file})",
        )

    try:
        raw_bytes = resolved.read_bytes()
        sha = hashlib.sha256(raw_bytes)
    except Exception as exc:
        return create_denied_read(
            policy=policy,
            file_path=file_path,
            reason=f"Failed to read file: {exc}",
        )
    if b"\x00" in raw_bytes:
        return {
            "kind": CONTENT_READ_RECEIPT_KIND,
            "schema_version": CONTENT_READ_RECEIPT_SCHEMA_VERSION,
            "target_file": str(resolved),
            "bytes_read": file_size,
            "sha256": sha.hexdigest(),
            "content_digest": sha.hexdigest(),
            "redacted_excerpt_digest": sha.hexdigest(),
            "redacted_excerpt": "",
            "binary_digest_only": True,
            "captured_at": int(time.time()),
            "governance": {
                "capability_state": "OPERATIONALLY_VERIFIED",
                "runtime_execution": "EXPLICIT_READ_ONLY",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }

    raw_text = raw_bytes.decode("utf-8", errors="replace")
    redacted = _redact_secrets(raw_text)
    excerpt = redacted[:max_excerpt_chars]
    content_digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    excerpt_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()

    return {
        "kind": CONTENT_READ_RECEIPT_KIND,
        "schema_version": CONTENT_READ_RECEIPT_SCHEMA_VERSION,
        "target_file": str(resolved),
        "target_root": str(target_repo.resolve()),
        "bytes_read": file_size,
        "sha256": sha.hexdigest(),
        "content_digest": content_digest,
        "redacted_excerpt_digest": excerpt_digest,
        "redacted_excerpt": excerpt,
        "binary_digest_only": False,
        "captured_at": int(time.time()),
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "EXPLICIT_READ_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_content_read_receipt(receipt: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return ["Content read receipt must be a dictionary"]
    if receipt.get("kind") != CONTENT_READ_RECEIPT_KIND:
        errors.append(f"kind must be {CONTENT_READ_RECEIPT_KIND}")
    if receipt.get("schema_version") != CONTENT_READ_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTENT_READ_RECEIPT_SCHEMA_VERSION}")
    for field in ("target_file", "content_digest", "redacted_excerpt_digest"):
        val = receipt.get(field)
        if not isinstance(val, str) or not val:
            errors.append(f"{field} must be a non-empty string")
    if not isinstance(receipt.get("bytes_read"), int) or receipt.get("bytes_read", -1) < 0:
        errors.append("bytes_read must be a non-negative integer")
    if not isinstance(receipt.get("sha256"), str) or len(receipt.get("sha256", "")) != 64:
        errors.append("sha256 must be a SHA-256 hex digest")
    return errors


def validate_content_read_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validate_content_read_receipt(data)
