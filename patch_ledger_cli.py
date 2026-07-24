import os
import re

f = "builder_ii/cli/ledger_cli.py"
with open(f, "r") as fp:
    content = fp.read()

target = """        try:
            record = index_verification_execution_receipt(
                receipt_path=receipt,
                plan_path=plan,
                approval_path=approval,
            )
        except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
            raise WorkflowError(f"failed to load receipt chain: {exc}") from exc
        if record.get("valid") is not True:
            raise WorkflowError(
                "invalid verification execution receipt chain: " + "; ".join(record.get("errors") or [])
            )
        errors = validate_verification_execution_ledger_record(record)
        if errors:
            raise WorkflowError("invalid verification execution ledger record: " + "; ".join(errors))
        target_repo = Path(str(record.get("target_repo", "."))).expanduser().resolve()
        ledger_root = target_repo / ".builder" / "ledger"
        output_path = output or default_verification_execution_ledger_output(record)
        write_verification_execution_ledger_record(record, output_path)"""

replacement = """        from builder_ii.governance.ledger.verification_execution_ledger import append_verification_execution_receipt
        try:
            record = append_verification_execution_receipt(
                receipt_path=receipt,
                plan_path=plan,
                approval_path=approval,
                output=output,
            )
        except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
            raise WorkflowError(f"failed to load receipt chain: {exc}") from exc
        if record.get("valid") is not True:
            raise WorkflowError(
                "invalid verification execution receipt chain: " + "; ".join(record.get("errors") or [])
            )
        errors = validate_verification_execution_ledger_record(record)
        if errors:
            raise WorkflowError("invalid verification execution ledger record: " + "; ".join(errors))"""

content = content.replace(target, replacement)
with open(f, "w") as fp:
    fp.write(content)
