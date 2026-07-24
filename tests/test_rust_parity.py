from __future__ import annotations

import pytest

from builder_ii.validation.rust_validator import find_rust_validator_binary, validate_via_rust
from builder_ii.validation.validation_benchmark import VALIDATORS, generate_mock_artifacts


def test_rust_binary_or_fail_closed_python_fallback_exists() -> None:
    binary = find_rust_validator_binary()
    valid, errors = validate_via_rust("builder_ii.goose_session_manifest", {"kind": "wrong"})
    assert binary is not None or "kind must be builder_ii.goose_session_manifest" in errors
    assert valid is False


@pytest.mark.parametrize(
    "kind",
    [
        "builder_ii.goose_session_manifest",
        "builder_ii.goose_readonly_runtime_audit",
        "builder_ii.goose_readonly_inspection_audit",
        "builder_ii.performance_measurement",
        "builder_ii.hitl_execution_request",
        "builder_ii.hitl_execution_receipt",
        "builder_ii.approval_record",
    ],
)
def test_python_rust_parity(kind: str) -> None:
    # Generate a mix of valid and invalid mock artifacts
    artifacts = generate_mock_artifacts(kind, 50)
    python_validator = VALIDATORS[kind]

    for art in artifacts:
        # Run python validator
        python_errors = python_validator(art)

        # Run rust validator
        rust_valid, rust_errors = validate_via_rust(kind, art)

        # Compare outcomes
        assert (len(python_errors) == 0) == rust_valid, (
            f"Validity mismatch for kind {kind}: python valid={len(python_errors) == 0}, rust valid={rust_valid}"
        )
        assert set(python_errors) == set(rust_errors), (
            f"Errors mismatch for kind {kind}:\nPython: {python_errors}\nRust: {rust_errors}"
        )
