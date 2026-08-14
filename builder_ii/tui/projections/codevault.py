"""Opaque availability projection for the optional commercial plugin."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodeVaultView:
    is_installed: bool
    command: str
    note: str


def project_code_vault(*, artifacts_dir: Path | None, project_root: Path | None = None) -> CodeVaultView:
    _ = artifacts_dir, project_root

    try:
        import builder_ii_code_vault  # noqa: F401

        is_installed = True
        note = "CodeVault commercial plugin detected."
    except ImportError:
        is_installed = False
        note = "CodeVault is not installed. Install the separately licensed plugin to enable it."

    return CodeVaultView(
        is_installed=is_installed,
        command="uv run builder-code-vault --help" if is_installed else "",
        note=note,
    )
