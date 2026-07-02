from __future__ import annotations

import json as json_lib
import subprocess
from pathlib import Path
from typing import Any

from builder_ii.config import load_settings

def find_rust_validator_binary() -> Path | None:
    settings = load_settings()
    # Check release and debug directories
    release_path = settings.project_root / "builder_ii_validation_rs" / "target" / "release" / "builder_ii_validation_rs"
    debug_path = settings.project_root / "builder_ii_validation_rs" / "target" / "debug" / "builder_ii_validation_rs"
    
    if release_path.exists():
        return release_path
    if debug_path.exists():
        return debug_path
    return None

def validate_via_rust(kind: str, data: dict[str, Any]) -> tuple[bool, list[str]]:
    binary = find_rust_validator_binary()
    if not binary:
        return False, ["Rust validator binary not found. Build it with 'cargo build --release'."]

    input_str = json_lib.dumps(data)
    
    try:
        proc = subprocess.run(
            [str(binary), "--kind", kind],
            input=input_str,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as e:
        return False, [f"Failed to run Rust validator subprocess: {e}"]

    if proc.returncode != 0:
        return False, [f"Rust validator exited with code {proc.returncode}: {proc.stderr}"]

    try:
        output_data = json_lib.loads(proc.stdout)
    except Exception as e:
        return False, [f"Failed to parse Rust validator output: {e}. Output was: {proc.stdout}"]

    errors = output_data.get("errors", [])
    valid = output_data.get("valid", False)
    
    return valid, errors
