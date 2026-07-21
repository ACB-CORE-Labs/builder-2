from __future__ import annotations

import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from builder_ii.core.config import load_settings


@lru_cache(maxsize=1)
def find_rust_validator_binary() -> Path | None:
    settings = load_settings()
    ext = ".exe" if sys.platform == "win32" else ""
    # Check release and debug directories
    release_path = (
        settings.project_root / "builder_ii_validation_rs" / "target" / "release" / f"builder_ii_validation_rs{ext}"
    )
    debug_path = (
        settings.project_root / "builder_ii_validation_rs" / "target" / "debug" / f"builder_ii_validation_rs{ext}"
    )

    if release_path.exists():
        return release_path
    if debug_path.exists():
        return debug_path
    cargo = shutil.which("cargo")
    manifest = settings.project_root / "builder_ii_validation_rs" / "Cargo.toml"
    if cargo and manifest.exists():
        subprocess.run(
            [cargo, "build", "--manifest-path", str(manifest)],
            cwd=settings.project_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if debug_path.exists():
            return debug_path
    return None


try:
    import builder_ii_validation_rs

    NATIVE_RUST_AVAILABLE = True
except ImportError:
    NATIVE_RUST_AVAILABLE = False


def validate_via_rust(kind: str, data: dict[str, Any]) -> tuple[bool, list[str]]:
    if NATIVE_RUST_AVAILABLE:
        try:
            # Native PyO3 FFI call. Memory boundary is shared; GIL released inside.
            valid, errors = builder_ii_validation_rs.validate_artifact(kind, data)
            # If Rust reports an unsupported kind, fall through to Python validators
            # instead of returning an opaque error.
            if not valid and any("unsupported" in e.lower() for e in errors):
                pass  # fall through below
            else:
                return valid, errors
        except Exception:
            pass  # fall through to Python validators

    # Pure Python fallback validators
    from builder_ii.validation.validation_benchmark import VALIDATORS

    validator = VALIDATORS.get(kind)
    if validator is None:
        return False, ["No validator registered for this kind (Rust extension unavailable or kind unsupported)."]
    errors = validator(data)
    return not errors, errors
