from __future__ import annotations

import json as json_lib
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from builder_ii.config import load_settings


@lru_cache(maxsize=1)
def find_rust_validator_binary() -> Path | None:
    settings = load_settings()
    ext = ".exe" if sys.platform == "win32" else ""
    # Check release and debug directories
    release_path = (
        settings.project_root
        / "builder_ii_validation_rs"
        / "target"
        / "release"
        / f"builder_ii_validation_rs{ext}"
    )
    debug_path = (
        settings.project_root
        / "builder_ii_validation_rs"
        / "target"
        / "debug"
        / f"builder_ii_validation_rs{ext}"
    )

    if release_path.exists():
        return release_path
    if debug_path.exists():
        return debug_path
    return None


def validate_via_rust(kind: str, data: dict[str, Any]) -> tuple[bool, list[str]]:
    binary = find_rust_validator_binary()
    if not binary:
        from builder_ii.validation_benchmark import VALIDATORS

        validator = VALIDATORS.get(kind)
        if validator is None:
            return False, ["Rust validator binary not found and no Python fallback validator is registered."]
        errors = validator(data)
        return not errors, errors

    input_bytes = json_lib.dumps(data).encode("utf-8")

    try:
        proc = subprocess.run(
            [str(binary), "--kind", kind],
            input=input_bytes,
            capture_output=True,
            check=False,
        )
    except Exception as e:
        return False, [f"Failed to run Rust validator subprocess: {e}"]

    if proc.returncode != 0:
        stderr_str = proc.stderr.decode("utf-8", errors="replace")
        return False, [f"Rust validator exited with code {proc.returncode}: {stderr_str}"]

    try:
        stdout_str = proc.stdout.decode("utf-8", errors="replace")
        output_data = json_lib.loads(stdout_str)
    except Exception as e:
        stdout_str = proc.stdout.decode("utf-8", errors="replace")
        return False, [f"Failed to parse Rust validator output: {e}. Output was: {stdout_str}"]

    errors = output_data.get("errors", [])
    valid = output_data.get("valid", False)

    return valid, errors
