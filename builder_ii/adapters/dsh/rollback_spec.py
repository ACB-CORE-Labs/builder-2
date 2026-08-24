"""
Rollback specification for the DSH-Goose ACP integration.
"""

def get_rollback_plan(session_id: str) -> str:
    """
    Returns the exact steps required to rollback a DSH-Goose session safely.
    Since DSH-0 is read-only, rollback consists strictly of process tree
    termination and isolated directory cleanup, with no target mutations to revert.
    """
    return f"""
    Rollback Specification for Session {session_id}:
    1. Send SIGTERM to the `goose acp` process and all children.
    2. Wait 5 seconds, then send SIGKILL if still running.
    3. Truncate the observational DSH session log to the last known-good state.
    4. Delete .builder/runtime/dsh/{session_id} isolation root.
    5. Ensure no persistent credentials or approvals were leaked.
    6. Record RollbackReceipt in builder-II ledger.
    """
