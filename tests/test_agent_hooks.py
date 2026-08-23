from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_builder_bootstrap_has_no_active_self_governing_hooks() -> None:
    assert not (ROOT / ".agents" / "hooks.json").exists()
    assert not (ROOT / ".agents" / "scripts" / "qualification_gate.sh").exists()
    assert not (ROOT / ".agents" / "scripts" / "closure_stop_gate.sh").exists()


def test_rust_cli_rejects_unknown_kind_instead_of_kind_only_acceptance() -> None:
    source = (ROOT / "builder_ii_validation_rs" / "src" / "main.rs").read_text(encoding="utf-8")
    validation = (ROOT / "builder_ii_validation_rs" / "src" / "validation.rs").read_text(encoding="utf-8")
    assert "validation::validate_artifact_core" in source
    assert "unsupported artifact kind" in validation
