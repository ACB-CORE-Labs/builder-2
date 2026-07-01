import json as json_lib
from pathlib import Path

def test_b8_approval_evidence_exists_and_validates() -> None:
    approval_path = Path("tests/fixtures/b8/b8-execution-approval.json")
    receipt_path = Path("tests/fixtures/b8/b8-execution-approval-receipt.json")

    assert approval_path.exists(), "B8 execution approval file must exist under tests/fixtures/b8/"
    assert receipt_path.exists(), "B8 execution approval receipt file must exist under tests/fixtures/b8/"

    approval = json_lib.loads(approval_path.read_text(encoding="utf-8"))
    receipt = json_lib.loads(receipt_path.read_text(encoding="utf-8"))

    # Validate approval details
    assert approval.get("kind") == "builder_ii.execution_plan_approval"
    assert approval.get("plan_path") == "docs/plan/B8_B9_GOVERNED_EXECUTION_PLAN.md"
    assert approval.get("plan_sha256") == "11fdcb603fa76230c64ee56936593240f59e537bc8030801dcb9249c04d9b5eb"

    # Check boundaries
    denied = approval.get("denied_boundaries", [])
    denied_set = {d.lower() for d in denied}
    
    assert any("hidden memory" in d for d in denied_set), "Must deny hidden memory"
    assert any("vector store" in d or "vector db" in d for d in denied_set), "Must deny vector store"
    assert any("autonomous memory writes" in d for d in denied_set), "Must deny autonomous memory writes"
    assert any("target repo mutation" in d or "target repository mutation" in d for d in denied_set), "Must deny target repo mutation"
    assert any("core workbench" in d for d in denied_set), "Must deny CORE Workbench"
    assert any("deephaven" in d for d in denied_set), "Must deny Deephaven"
    assert any("b9" in d for d in denied_set), "Must deny B9"

    # Validate receipt
    assert receipt.get("kind") == "builder_ii.execution_plan_approval_receipt"
    assert receipt.get("valid") is True, f"Receipt is invalid, errors: {receipt.get('errors')}"
    assert not receipt.get("errors"), f"Receipt has errors: {receipt.get('errors')}"
    assert receipt.get("approval_ref", {}).get("path") == "tests/fixtures/b8/b8-execution-approval.json"
