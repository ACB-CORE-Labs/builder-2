"""Tests for builder_ii.hitl_patch_proposal — design-only governance assertions."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import builder_ii.governance.hitl.hitl_patch_proposal as hitl_mod
from builder_ii.governance.hitl.hitl_patch_proposal import (
    HITL_PATCH_PROPOSAL_KIND,
    create_hitl_patch_proposal,
    dumps_hitl_patch_proposal,
    validate_hitl_patch_proposal,
    validate_hitl_patch_proposal_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_DOC_PATH = Path(__file__).parent.parent / "docs" / "HITL_PATCH_PROPOSAL.md"
_MODULE_SRC = inspect.getsource(hitl_mod)


# ---------------------------------------------------------------------------
# 1. Valid spec validates
# ---------------------------------------------------------------------------
def test_valid_spec_validates() -> None:
    """A freshly-created spec must pass validation with no errors."""
    spec = create_hitl_patch_proposal(
        patch_description="test patch design spec",
        reason="unit test",
        target_head_sha="a" * 40,
        verification_receipt_file_sha256="b" * 64,
    )
    assert spec["kind"] == HITL_PATCH_PROPOSAL_KIND
    errors = validate_hitl_patch_proposal(spec)
    assert errors == [], f"Unexpected validation errors: {errors}"


# ---------------------------------------------------------------------------
# 2. Invalid enabled runtime fails
# ---------------------------------------------------------------------------
def test_invalid_enabled_runtime_fails() -> None:
    """Setting current_state.runtime to anything other than DISABLED must fail."""
    spec = create_hitl_patch_proposal(target_head_sha="a" * 40, verification_receipt_file_sha256="b" * 64)
    spec["current_state"]["runtime"] = "ENABLED"
    errors = validate_hitl_patch_proposal(spec)
    assert any("current_state.runtime must be DISABLED or NOT_AUTHORIZED" in e for e in errors)


# ---------------------------------------------------------------------------
# 3. Source writes enabled fails
# ---------------------------------------------------------------------------
def test_source_writes_enabled_fails() -> None:
    """Enabling source_writes in governance must fail validation."""
    spec = create_hitl_patch_proposal()
    spec["governance"]["source_writes"] = "ENABLED"
    errors = validate_hitl_patch_proposal(spec)
    assert any("governance.source_writes must be DISABLED or NOT_AUTHORIZED" in e for e in errors)


# ---------------------------------------------------------------------------
# 4. artifact_is_authority true fails
# ---------------------------------------------------------------------------
def test_artifact_is_authority_true_fails() -> None:
    """Setting artifact_is_authority to True must fail validation (both locations)."""
    # governance block
    spec = create_hitl_patch_proposal()
    spec["governance"]["artifact_is_authority"] = True
    errors = validate_hitl_patch_proposal(spec)
    assert any("governance.artifact_is_authority must be false or NOT_AUTHORIZED" in e for e in errors)

    # current_state block
    spec2 = create_hitl_patch_proposal(target_head_sha="a" * 40, verification_receipt_file_sha256="b" * 64)
    spec2["current_state"]["artifact_is_authority"] = True
    errors2 = validate_hitl_patch_proposal(spec2)
    assert any("current_state.artifact_is_authority must be false or NOT_AUTHORIZED" in e for e in errors2)


# ---------------------------------------------------------------------------
# 5. CORE Workbench coupling other than NONE fails
# ---------------------------------------------------------------------------
def test_core_workbench_coupling_non_none_fails() -> None:
    """Any core_workbench_coupling value other than NONE must fail."""
    for bad_value in ("TIGHT", "LOOSE", "PARTIAL", "TRUE"):
        spec = create_hitl_patch_proposal(target_head_sha="a" * 40, verification_receipt_file_sha256="b" * 64)
        spec["governance"]["core_workbench_coupling"] = bad_value
        errors = validate_hitl_patch_proposal(spec)
        assert any("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in e for e in errors), (
            f"Expected failure for coupling={bad_value!r}, got: {errors}"
        )


# ---------------------------------------------------------------------------
# 6. Docs include the future governed path
# ---------------------------------------------------------------------------
def test_docs_include_future_governed_path() -> None:
    """Documentation must describe the complete eight-stage future patch path."""
    assert _DOC_PATH.exists(), f"Doc file not found: {_DOC_PATH}"
    doc_text = _DOC_PATH.read_text(encoding="utf-8")

    required_stages = [
        "patch proposal",
        "human approval record",
        "preflight record",
        "explicit patch application request",
        "patch application receipt",
        "rollback artifact",
        "verification record",
        "handoff/postflight",
    ]
    for stage in required_stages:
        assert stage in doc_text, f"Docs missing future path stage: {stage!r}"


# ---------------------------------------------------------------------------
# 7. Docs do not claim patch application is enabled
# ---------------------------------------------------------------------------
def test_docs_do_not_claim_patch_application_enabled() -> None:
    """The documentation must not claim that patch application is currently active."""
    assert _DOC_PATH.exists(), f"Doc file not found: {_DOC_PATH}"
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    lower_doc = doc_text.lower()

    # Platform identity guards
    assert "builder-II is a generic governed local agent/developer platform." in doc_text
    assert "It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime." in doc_text
    assert "CORE is only a target profile." in doc_text

    # No forbidden activation claims
    assert "patch application is enabled" not in lower_doc
    assert "runtime execution is enabled" not in lower_doc
    assert "subprocess.run(" not in doc_text
    assert "deephaven" not in lower_doc
    assert "voice/tts/stt" not in lower_doc
    assert "builder-ii is core workbench" not in lower_doc


# ---------------------------------------------------------------------------
# 8. Module does not import subprocess
# ---------------------------------------------------------------------------
def test_module_does_not_import_subprocess() -> None:
    """The module source must not contain any subprocess import or usage."""
    assert "import subprocess" not in _MODULE_SRC
    assert "from subprocess" not in _MODULE_SRC
    assert "subprocess." not in _MODULE_SRC


# ---------------------------------------------------------------------------
# 9. No function applies patches or writes target source
# ---------------------------------------------------------------------------
def test_no_function_applies_patches_or_writes_target_source() -> None:
    """Statically verify that no callable in the module applies patches or writes source files."""
    forbidden_calls = [
        "os.system",
        "os.popen",
        "exec(",
        "eval(",
        "shutil.",
        "apply_patch",
        "write_source",
        "patch_file",
    ]
    for token in forbidden_calls:
        assert token not in _MODULE_SRC, f"Forbidden token {token!r} found in module source"

    # subprocess must not be imported or called (bare word appears in string constants,
    # so we check for import/call patterns specifically).
    assert "import subprocess" not in _MODULE_SRC
    assert "from subprocess" not in _MODULE_SRC
    assert "subprocess.run(" not in _MODULE_SRC
    assert "subprocess.Popen(" not in _MODULE_SRC
    assert "subprocess.call(" not in _MODULE_SRC

    # Verify via AST that no function is named with patch/apply/write_source verbs
    # targeting source files (excluding the spec-write helper which writes JSON).
    tree = ast.parse(_MODULE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            # The only allowed write function writes the JSON spec artifact, not source.
            assert "apply_patch" not in name, f"Function {name!r} appears to apply patches"
            assert "write_source" not in name, f"Function {name!r} appears to write source"
            assert "patch_target" not in name, f"Function {name!r} appears to patch a target"


# ---------------------------------------------------------------------------
# 10. All governance fields default to DISABLED / False / NONE
# ---------------------------------------------------------------------------
def test_governance_defaults_fully_disabled() -> None:
    spec = create_hitl_patch_proposal()
    gov = spec["governance"]
    for key in (
        "patch_application",
        "source_writes",
        "file_mutation",
        "git_mutation",
        "commit_push",
        "shell_execution",
        "subprocess_execution",
        "model_execution",
        "network_mcp_execution",
        "goose_runtime_activation",
        "deepagents_runtime",
    ):
        assert gov[key] == "DISABLED", f"governance.{key} must be DISABLED or NOT_AUTHORIZED by default"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


# ---------------------------------------------------------------------------
# 11. File I/O round-trip
# ---------------------------------------------------------------------------
def test_file_io_round_trip(tmp_path: Path) -> None:
    spec = create_hitl_patch_proposal(patch_description="round-trip test", reason="ci", target_head_sha="a" * 40, verification_receipt_file_sha256="b" * 64)
    out = tmp_path / "hitl_patch_proposal.json"
    hitl_mod.write_hitl_patch_proposal(spec, out)
    assert out.exists()
    errors = validate_hitl_patch_proposal_file(out)
    assert errors == [], f"Round-trip validation failed: {errors}"

    # Missing file
    missing = tmp_path / "does_not_exist.json"
    errs = validate_hitl_patch_proposal_file(missing)
    assert any("file not found" in e for e in errs)


# ---------------------------------------------------------------------------
# 12. dumps produces valid JSON
# ---------------------------------------------------------------------------
def test_dumps_produces_valid_json() -> None:
    import json

    spec = create_hitl_patch_proposal(target_head_sha="a" * 40, verification_receipt_file_sha256="b" * 64)
    text = dumps_hitl_patch_proposal(spec)
    parsed = json.loads(text)
    assert parsed["kind"] == HITL_PATCH_PROPOSAL_KIND
