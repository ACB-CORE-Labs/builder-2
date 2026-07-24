
f = "builder_ii/governance/ledger/verification_execution_ledger.py"
with open(f, "r") as fp:
    content = fp.read()

append_func = """
import contextlib
import typing

@contextlib.contextmanager
def _exclusive_ledger_lock(ledger_root: Path) -> typing.Iterator[None]:
    import fcntl
    ledger_root.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_root / ".lock"
    with lock_path.open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def append_verification_execution_receipt(
    *,
    receipt_path: Path,
    plan_path: Path,
    approval_path: Path,
    ledger_root: Path | None = None,
    output: Path | None = None,
) -> dict[str, typing.Any]:
    receipt = _load_json_object(receipt_path)
    repo_path = Path(str(receipt.get("target_repo", "."))).expanduser().resolve()
    resolved_ledger_root = (
        ledger_root.expanduser().resolve()
        if ledger_root is not None
        else (repo_path / ".builder" / "ledger")
    )
    
    with _exclusive_ledger_lock(resolved_ledger_root):
        record = index_verification_execution_receipt(
            receipt_path=receipt_path,
            plan_path=plan_path,
            approval_path=approval_path,
            ledger_root=resolved_ledger_root,
        )
        if record.get("valid") is True:
            output_path = output or default_verification_execution_ledger_output(record)
            write_verification_execution_ledger_record(record, output_path)
        return record
"""

if "_exclusive_ledger_lock" not in content:
    content += append_func
    with open(f, "w") as fp:
        fp.write(content)
