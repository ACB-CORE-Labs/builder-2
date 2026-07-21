
from typing import Any

# The canonical, rigorous list of capability boundaries tracked for every runtime execution
GOVERNANCE_KEYS = (
    "agent_construction",
    "artifact_is_authority",
    "artifacts_are_authority",
    "autonomous_agent_authority",
    "benchmark_execution",
    "capability_state",
    "claims_verification_passed",
    "command_execution",
    "commit_push",
    "core_workbench_coupling",
    "deepagents_construction",
    "deepagents_delegation",
    "deepagents_runtime",
    "deepagents_runtime_start",
    "deephaven_touch",
    "executes_commands",
    "file_mutation",
    "git_mutation",
    "git_status_inspection",
    "goose_runtime_activation",
    "goose_runtime_start",
    "hardware_probe",
    "mcp_execution",
    "memory_mutation",
    "model_execution",
    "model_execution_loops",
    "network_access",
    "network_mcp_execution",
    "notes_vault_mutation",
    "patch_application",
    "proof_of_capability_only",
    "pull_request_creation",
    "quality_gate_executes_commands",
    "report_is_completed_evidence",
    "repository_file_reads",
    "repository_writes",
    "runtime_activation",
    "runtime_authority",
    "runtime_execution",
    "runtime_executor",
    "search_execution",
    "shell_execution",
    "source_collection",
    "source_patches_applied",
    "source_writes",
    "subagent_construction",
    "subprocess_backed_authority",
    "subprocess_execution",
    "target_artifact_reads",
    "target_repo_writes",
    "ticket_creation",
    "web_search",
)

def build_standard_governance(capability_state: str) -> dict[str, Any]:
    """Create a standardized governance block with all permissions explicitly disabled."""
    gov: dict[str, Any] = {
        "capability_state": capability_state,
        "artifact_is_authority": False,
        "artifacts_are_authority": False,
        "executes_commands": False,
        "core_workbench_coupling": "NONE",
        "proof_of_capability_only": True,
        "runtime_executor": False,
    }

    for key in GOVERNANCE_KEYS:
        if key not in gov:
            gov[key] = "DISABLED"

    return gov

def validate_standard_governance(gov: Any, expected_capability_state: str) -> list[str]:
    """Validate that the governance block conforms to the rigid builder-II standard."""
    errors: list[str] = []

    if not isinstance(gov, dict):
        return ["governance must be an object"]

    if gov.get("capability_state") != expected_capability_state:
        errors.append(f"governance.capability_state must be {expected_capability_state}")

    if gov.get("artifact_is_authority", False) is not False:
        errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
    if gov.get("artifacts_are_authority", False) is not False:
        errors.append("governance.artifacts_are_authority must be false or NOT_AUTHORIZED")
    if gov.get("executes_commands", False) is not False:
        errors.append("governance.executes_commands must be false or NOT_AUTHORIZED")
    if gov.get("core_workbench_coupling", "NONE") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    if gov.get("proof_of_capability_only", True) is not True:
        errors.append("governance.proof_of_capability_only must be true or NOT_AUTHORIZED")
    if gov.get("runtime_executor", False) is not False:
        errors.append("governance.runtime_executor must be false or NOT_AUTHORIZED")

    all_keys = set(list(gov.keys()) + list(GOVERNANCE_KEYS))
    for key in sorted(list(all_keys)):
        if key not in (
            "capability_state",
            "artifact_is_authority",
            "artifacts_are_authority",
            "executes_commands",
            "core_workbench_coupling",
            "proof_of_capability_only",
            "runtime_executor",
        ):
            val = gov.get(key, "DISABLED")
            if key == "source_writes" and val == "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
                continue
            if key == "claims_verification_passed":
                if val not in (True, False, "DISABLED", "NOT_AUTHORIZED"):
                    errors.append("governance.claims_verification_passed must be a boolean or DISABLED or NOT_AUTHORIZED")
                continue
            if val not in ("DISABLED", "NOT_AUTHORIZED"):
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")

    return errors
