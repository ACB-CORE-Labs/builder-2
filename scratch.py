from pathlib import Path
from tests.test_verification_promotion_gate import _write_chain
from builder_ii.governance.ledger.verification_execution_ledger import validate_receipt_chain_for_ledger, _load_json_object

p = Path("tmp")
p.mkdir(exist_ok=True)
plan_path, approval_path, receipt_path = _write_chain(p)

receipt = _load_json_object(receipt_path)
plan = _load_json_object(plan_path)
approval = _load_json_object(approval_path)
errors = validate_receipt_chain_for_ledger(receipt=receipt, plan=plan, approval=approval)
print("Errors:", errors)
