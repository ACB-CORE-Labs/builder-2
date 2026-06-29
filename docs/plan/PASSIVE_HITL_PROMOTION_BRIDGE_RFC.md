# Passive HITL Promotion Bridge RFC (Goal 4 Design & Authorization)

Status: Design-only authorization RFC for Goal 4.

This document defines and authorizes the Goal 4 passive human-in-the-loop (HITL) promotion bridge artifact slice for the builder-II platform. It establishes the typed, traceable boundary where passive proposals from Goal 2 (orchestration assignment) and Goal 3 (deepagents work artifacts) request, review, and record human promotion decisions before any runtime execution candidate is constructed.

---

## 1. Current Plan Position

builder-II is a generic governed local agent/developer platform. It is NOT CORE, NOT CORE Workbench/UI, and NOT a second CORE runtime. CORE is solely a target profile adapter.

The canonical master plan progression is:
- **Goal 2 (Completed)**: Added passive orchestration assignment artifacts (`builder_ii.agent_assignment_plan`, `builder_ii.orchestration_assignment_plan`, `builder_ii.orchestration_assignment_dry_run`, `builder_ii.orchestration_assignment_validation_report`), binding target, task, agent, model recommendation, context, verification, tool policy, HITL policy, outputs, and handoff refs by SHA-256 without executing anything.
- **Goal 3 (Completed)**: Added passive deepagents work artifacts (`builder_ii.deepagents_work_plan`, `builder_ii.deepagents_subagent_assignment`, `builder_ii.deepagents_subagent_result`, `builder_ii.deepagents_subagent_review`, `builder_ii.deepagents_human_gate_request`, `builder_ii.deepagents_blocked_action_record`, `builder_ii.deepagents_proposal_result`, `builder_ii.deepagents_work_validation_report`). Goal 3 remains purely proposal-based and artifact-only.
- **Goal 4 (This Slice)**: Authorizes the passive HITL promotion bridge artifacts. It connects Goal 2 and Goal 3 proposals to an auditable human decision boundary without enabling runtime execution.

```text
Goal 2 passive orchestration assignment
  → Goal 3 passive deepagents work/proposal artifacts
    → Goal 4 human promotion request/review/decision boundary artifacts
```

---

## 2. Scope

This RFC authorizes the design and future implementation of typed, JSON-backed promotion bridge artifacts and validation CLI utilities. Specifically, it covers:
- Recording formal requests for human promotion of verified proposals.
- Recording structured reviews against governance policies and target profiles.
- Recording explicit human promotion decisions (`approved_for_candidate_design`, `rejected`, `needs_revision`).
- Recording immutable approval boundaries defining exact permitted next-stage candidate scopes.
- Recording explicit rejection records with blocking rationale.
- Providing passive validation reporting for the promotion chain.

---

## 3. Non-Goals & Non-Negotiables

Goal 4 is strictly an authorization and tracking boundary ("make the promotion boundary explicit, typed, reviewable, auditable, and still passive"). It is NOT "turn it on."

The following are strictly forbidden under Goal 4:
- **No runtime execution**: No active code execution of any kind.
- **No active deepagents behavior**: No construction of deepagents or invocation of subagents.
- **No model execution**: No LLM client calls or token generation.
- **No tool execution**: No tool execution engines activated.
- **No shell execution**: No shell or subprocess commands executed as a builder-II capability.
- **No Goose invocation**: No starting or interacting with Goose sessions.
- **No MCP invocation**: No Model Context Protocol server calls.
- **No network calls**: No network access as a builder-II capability.
- **No target repo mutation**: No writes or edits to target repositories.
- **No memory mutation**: No memory ledger writes or updates.
- **No hidden authority**: No implicit permission escalation.
- **No artifact-as-authority**: No artifact may imply `artifact_is_authority: true`.
- **No command-authority bypass**: All actions remain subject to strict Command Authority Tiers.
- **No verification bypass**: Chain verification fails closed on any missing or unhashed dependency.
- **No CORE Workbench/UI coupling**: Zero coupling to CORE proprietary UI or cockpit interfaces.
- **No CORE-specific global identity**: Preserves platform neutrality.
- **No Deephaven work**: Deephaven integrations remain untouched.
- **No Goal 5/6 runtime**: Execution candidate creation and live activation are deferred to future goals.

---

## 4. Proposed Artifact Kinds

Goal 4 evaluates and authorizes the following six passive artifact kinds:

| Artifact Kind | Description | Role in Bridge |
| :--- | :--- | :--- |
| `builder_ii.hitl_promotion_request` | Formal promotion request wrapping a proposed artifact | Initiates promotion workflow |
| `builder_ii.hitl_promotion_review` | Policy and security review of a promotion request | Evaluates compliance and risks |
| `builder_ii.hitl_promotion_decision` | Human decision recording approval or rejection | Records operator verdict |
| `builder_ii.hitl_approval_boundary` | Immutable scope definition for approved proposals | Defines exact allowed candidate scope |
| `builder_ii.hitl_rejection_record` | Explicit rejection record with blockers | Terminates promotion path |
| `builder_ii.hitl_promotion_validation_report` | Static validation report for promotion artifacts | Proves structural integrity |

### Evaluated & Rejected/Deferred Kinds
- `builder_ii.execution_candidate_manifest`: **Rejected/Deferred to Goal 5**. While an execution candidate artifact is essential before runtime launch, placing it in Goal 4 creates high risk of runtime coupling. Goal 4 stops strictly at the `hitl_approval_boundary`. Constructing candidate runtime manifests is deferred to Goal 5.

---

## 5. Per-Artifact Required Refs

Every Goal 4 artifact must cryptographically bind to its dependencies via exact SHA-256 digests (`sha256` and relative/absolute file path bindings):

1. `builder_ii.hitl_promotion_request`:
   - `proposal_ref`: SHA-256 of the subject proposal (e.g., `builder_ii.deepagents_proposal_result`, `builder_ii.orchestration_assignment_validation_report`).
   - `target_profile_ref`: SHA-256 of the target profile.
   - `session_manifest_ref`: SHA-256 of the active session configuration.
2. `builder_ii.hitl_promotion_review`:
   - `request_ref`: SHA-256 of the `hitl_promotion_request`.
   - `policy_ref`: SHA-256 of applicable governance policies (`builder_ii.deepagents_governed_policy`).
3. `builder_ii.hitl_promotion_decision`:
   - `review_ref`: SHA-256 of the `hitl_promotion_review`.
   - `request_ref`: SHA-256 of the `hitl_promotion_request`.
4. `builder_ii.hitl_approval_boundary`:
   - `decision_ref`: SHA-256 of an approved `hitl_promotion_decision`.
   - `permitted_scope_manifest`: Exact specification of allowed target profiles, read-only commands, and denied boundaries.
5. `builder_ii.hitl_rejection_record`:
   - `decision_ref` or `request_ref`: SHA-256 of the rejected decision or request.
6. `builder_ii.hitl_promotion_validation_report`:
   - `subject_refs`: List of SHA-256 digests for all promotion artifacts validated.

---

## 6. Allowed Statuses & Dispositions

All state tracking strings must be explicitly passive.

### Allowed Record States
- `REQUESTED_ONLY`
- `REVIEWED_ONLY`
- `DECISION_RECORDED_ONLY`
- `BOUNDARY_RECORDED_ONLY`
- `REJECTED_ONLY`
- `VALIDATION_ONLY`

### Allowed Decision Dispositions
- `approved_for_candidate_design`
- `rejected`
- `needs_revision`

---

## 7. Authority Boundary & Invariants

Every Goal 4 artifact must include or enforce the following immutable governance dictionary:

```json
{
  "executes_model": false,
  "executes_tools": false,
  "executes_shell": false,
  "invokes_goose": false,
  "constructs_deepagents": false,
  "constructs_subagents": false,
  "invokes_mcp": false,
  "performs_network_calls": false,
  "mutates_target_repo": false,
  "mutates_memory": false,
  "artifact_is_authority": false,
  "bypasses_command_authority": false,
  "bypasses_verification": false,
  "core_workbench_coupling": "NONE"
}
```

### What a Human Decision Artifact May Set True
To clearly distinguish decision recording from execution permission, an approved decision artifact may ONLY set tracking properties:
```json
{
  "records_human_decision": true,
  "decision_result": "approved_for_candidate_design",
  "grants_runtime_authority": false,
  "authorizes_execution": false,
  "requires_separate_execution_candidate": true
}
```

---

## 8. Active-State Forbidden Terms

To prevent semantic drift or accidental misinterpretation by automated parsers, Goal 4 artifacts and schema validators must reject any current state or status field containing active terms unless prefixed by a denial context:
- Forbidden active terms: `AUTHORIZED`, `ENABLED`, `PROMOTED`, `EXECUTABLE`, `ACTIVE`, `RUNNING`.
- Allowed usage: Only inside denial explanations (e.g., `"runtime_status": "DISABLED"`, `"error": "Active execution is FORBIDDEN"`).

---

## 9. Validation Requirements

Native JSON schema validation functions must be created for each artifact kind (e.g., `validate_hitl_promotion_request`). Validation fails closed if:
- Any required SHA-256 reference is missing or malformed.
- Any authority flag in Section 7 is set to `true`.
- Any active forbidden term appears in record state fields.
- Decision disposition is `approved_for_candidate_design` but unresolved review blockers exist.

---

## 10. Artifact Index Integration Requirements

The six Goal 4 artifact kinds must be registered in the platform artifact index (`builder_ii.artifact_index_record`). Indexing a Goal 4 artifact records its location, kind, schema version, and cryptographic hash without marking it as executable.

---

## 11. Artifact Chain Verification Requirements

The chain verifier (`builder_ii.artifact_chain_verification`) must be extended to traverse Goal 4 references:
- Resolving `hitl_approval_boundary` -> `hitl_promotion_decision` -> `hitl_promotion_review` -> `hitl_promotion_request` -> `proposal_ref`.
- Verification guarantees that the cryptographic chain from Goal 2 assignment through Goal 3 proposal to Goal 4 human boundary is unbroken and tamper-free.

---

## 12. Command Authority Requirements

All CLI commands associated with Goal 4 must be classified strictly under **Tier 1 (artifact-only planning/validation)** in `builder_ii/command_authority.py`:
- Promotion state: `STATE_ARTIFACT_ONLY` or `STATE_VALIDATION_ONLY`.
- Approval mode: `MODE_NONE` (for generation/validation of passive records).
- Runtime boundary: Emits passive JSON records only. No code execution.

---

## 13. Operator Command Surface Requirements

The operator command surface (`docs/OPERATOR_COMMAND_SURFACE.md`) will expose the following Tier 1 commands:

| Command | Tier | Output Behavior |
| :--- | :--- | :--- |
| `builder-hitl promotion-request` | Tier 1 | Writes `hitl_promotion_request` JSON artifact |
| `builder-hitl promotion-review` | Tier 1 | Writes `hitl_promotion_review` JSON artifact |
| `builder-hitl promotion-decision` | Tier 1 | Writes `hitl_promotion_decision` JSON artifact |
| `builder-hitl approval-boundary` | Tier 1 | Writes `hitl_approval_boundary` JSON artifact |
| `builder-hitl rejection-record` | Tier 1 | Writes `hitl_rejection_record` JSON artifact |
| `builder-hitl validate-promotion` | Tier 1 | Validates promotion artifacts and outputs report |

---

## 14. Tests Required for the Later Implementation PR

When Goal 4 is implemented in Python code, the test suite must include:
1. `test_hitl_promotion_request_creation_and_validation`: Proves creation and fail-closed validation on missing proposal refs.
2. `test_hitl_promotion_authority_invariants`: Asserts all authority flags remain `false` across all six artifact kinds.
3. `test_hitl_promotion_forbidden_terms`: Asserts rejection of active terms like `ENABLED` or `EXECUTABLE`.
4. `test_hitl_promotion_chain_verification`: Proves chain verification traversal from boundary down to Goal 2/3 source proposals.
5. `test_hitl_promotion_command_authority_tier`: Proves all CLI commands are registered at Tier 1 and cannot execute shell or mutate repos.

---

## 15. Rollback Path

Because Goal 4 artifacts are purely passive files written to explicit output paths, rollback requires no system or database state restoration. Rollback consists solely of:
1. Deleting the emitted JSON artifact files.
2. Recording a `builder_ii.hitl_rejection_record` invalidating the promotion request digest if needed.

---

## 16. Future Handoff to Goal 5 / Goal 6

Once Goal 4 implementation is completed and verified:
- **Goal 5** will design Tier 3 execution candidate manifests (`builder_ii.execution_candidate_manifest`) that consume a verified `builder_ii.hitl_approval_boundary`.
- **Goal 6** will implement approved live runtime activation (such as Goose session execution or deepagents subagent dispatch), strictly gated by verified Goal 5 candidate manifests and Goal 4 approval boundaries.
