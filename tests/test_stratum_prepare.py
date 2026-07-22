"""Auto-prep helpers for STRATUM local scaffolding."""

from __future__ import annotations

from pathlib import Path

from builder_ii.lifecycle.setup.stratum_prepare import (
    AUTO_GOOSE_MANIFEST_NAME,
    ensure_builder_scaffold,
    ensure_readonly_goose_manifest,
)


def test_ensure_builder_scaffold(tmp_path: Path) -> None:
    root = tmp_path / ".builder"
    ensure_builder_scaffold(root)
    assert (root / "artifacts").is_dir()
    assert (root / "goose").is_dir()
    assert (root / "receipts").is_dir()
    # Idempotent when dirs already exist
    ensure_builder_scaffold(root)
    assert (root / "goose").is_dir()


def test_ensure_readonly_goose_manifest_creates_when_missing(tmp_path: Path) -> None:
    from builder_ii.core.config import load_settings

    settings = load_settings()
    builder_root = tmp_path / ".builder"
    path, note = ensure_readonly_goose_manifest(settings=settings, builder_root=builder_root)
    assert path is not None, note
    assert path.name == AUTO_GOOSE_MANIFEST_NAME
    assert path.is_file()
    assert "auto-prepared" in note.lower()

    # Second call reuses existing (scaffold already created goose/)
    path2, note2 = ensure_readonly_goose_manifest(settings=settings, builder_root=builder_root)
    assert path2 == path
    assert "existing" in note2.lower()


def test_ensure_readonly_reuses_other_valid_readonly_manifest(tmp_path: Path) -> None:
    """Prefer an operator-minted valid read_only file over minting the auto name."""
    from builder_ii.adapters.goose.goose_session import create_goose_session_manifest, write_goose_session_manifest
    from builder_ii.core.config import load_settings

    settings = load_settings()
    builder_root = tmp_path / ".builder"
    ensure_builder_scaffold(builder_root)
    custom = builder_root / "goose" / "session.json"
    manifest = create_goose_session_manifest(
        settings,
        target_name="builder",
        agent_profile="repo_mapper",
        runtime_mode="read_only",
        task="operator minted",
    )
    write_goose_session_manifest(manifest, custom)

    path, note = ensure_readonly_goose_manifest(settings=settings, builder_root=builder_root)
    assert path == custom
    assert "existing" in note.lower()
    assert not (builder_root / "goose" / AUTO_GOOSE_MANIFEST_NAME).exists()
