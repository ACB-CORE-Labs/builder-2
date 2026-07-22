# Passive Execution Candidate Manifest RFC (Goal 5 Design & Authorization)

Status: Design-only authorization RFC for Goal 5. No Python artifact module, CLI command, runtime launcher, executor, model call, tool call, shell command, network call, Goose invocation, MCP invocation, deepagents construction, target repository mutation, or memory mutation is authorized by this document.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI, and not a second CORE runtime. CORE is only a target profile / adapter. Deephaven work is out of scope and forbidden for this slice.

---

## 1. Current Plan Position

Goal 5 sits after the completed passive ladder:

- **Goal 2 (complete)**: passive orchestration assignment artifacts bind target, task, agent, model recommendation, context, verification, tool policy, HITL policy, outputs, and handoff refs by SHA-256 without execution authority.
- **Goal 3 (complete)**: passive deepagents work/proposal artifacts represent optional deepagents-style planning and review without adding deepagents as a hard dependency or constructing subagents.
- **Goal 4 (complete)**: passive HITL promotion bridge artifacts produce `builder_ii.hitl_approval_boundary` records from reviewed human promotion decisions. The boundary records approved candidate-design scope only and defaults its required future artifact to `builder_ii.execution_candidate_manifest`.
- **Goal 5 (this RFC)**: authorizes the design contract for a passive/candidate-only execution candidate manifest that consumes a verified `builder_ii.hitl_approval_boundary` and produces a bounded, reviewable, rollback-aware, verification-bound candidate artifact. It does not implement runtime behavior.
- **Goal 6 or later**: may consider runtime activation through a separate RFC and artifact path. Goal 5 explicitly defers Goal 6/runtime activation.

The intrinsic space is an evidence graph, not an execution loop:

```text
Goal 2 passive assignment refs
  -> Goal 3 passive proposal refs
    -> Goal 4 HITL promotion request/review/decision
      -> builder_ii.hitl_approval_boundary
        -> Goal 5 builder_ii.execution_candidate_manifest
          -> Goal 6 separate activation artifact, if ever authorized
```

The manifest is a reconstructive memory object. It records enough structured state to reconstruct the proposed future execution review path, but it does not perform that execution and cannot become authority.

## 2. Scope

Goal 5 authorizes an implementation design for one primary passive artifact kind:

- `builder_ii.execution_candidate_manifest`

Goal 5 also authorizes one supporting passive validation/report artifact for the later implementation PR:

- `builder_ii.execution_candidate_manifest_validation_report`

The manifest may describe a proposed future execution under a previously approved HITL boundary. It may include command previews, target profile refs, verification profile refs, approval boundary refs, preflight requirements, rollback requirements, dry-run expectations, denied boundaries, and required future proof artifacts.

The validation report may validate manifest structure, refs, digest bindings, scope boundaries, rollback requirements, verification requirements, and authority invariants. It is validation-only and cannot convert a candidate into permission.

## 3. Non-Goals & Non-Negotiables

Goal 5 is passive/candidate-only. It is not "turn it on."

Goal 5 does not authorize:

- runtime activation;
- execution receipts as evidence of Goal 5 completion;
- command running;
- arbitrary shell command manifests;
- target repo mutation candidates unless a future RFC proves a narrower safe sub-slice;
- Goose runtime activation;
- deepagents subagent dispatch;
- MCP invocation;
- network execution;
- memory mutation;
- autonomous patch application;
- CORE Workbench/UI integrations;
- Deephaven work.

Goal 5 also forbids shell execution, forbids model execution, forbids tool execution, forbids Goose invocation, forbids deepagents construction, forbids MCP invocation, forbids network calls, forbids target repo mutation, and forbids memory mutation.

No artifact is authority. No artifact may bypass command authority, bypass verification, grant runtime authority, authorize execution, grant action authority, or hide future activation inside validation.

## 4. Existing HITL / Candidate Surfaces in the Codebase

The current codebase already provides the following relevant surfaces:

- `builder_ii.hitl_promotion_request`, `builder_ii.hitl_promotion_review`, `builder_ii.hitl_promotion_decision`, `builder_ii.hitl_approval_boundary`, `builder_ii.hitl_rejection_record`, and `builder_ii.hitl_promotion_validation_report` in `builder_ii/governance/hitl/hitl_promotion_artifacts.py`.
- `builder_ii.hitl_approval_boundary` requires `source_decision_result: approved_for_candidate_design`, `source_decision_record_state: DECISION_RECORDED_ONLY`, all authority flags false, and `requires_separate_execution_candidate: true`.
- `builder_ii.hitl_approval_boundary.required_future_artifacts` defaults to `builder_ii.execution_candidate_manifest`.
- `builder_ii.hitl_verification_execution_candidate` in `builder_ii/governance/hitl/hitl_verification_candidate.py` is an existing specialized candidate for future operator-approved verification commands. It is candidate-only/planned-only, accepts narrow verification command classes or verification profile refs, requires proposal/approval/preflight/request refs, and encodes receipt/postflight/rollback/verification/chain-binding requirements as future evidence.
- `builder_ii.hitl_execution_request` and `builder_ii.hitl_execution_receipt` are passive HITL record objects. The receipt template records `NOT_EXECUTED` and null execution-result fields in current validation.
- `builder_ii.hitl_chain_binding` binds proposal, approval, preflight, request, receipt, postflight, verification, and optional evidence-bundle slots without execution authority.
- `builder_ii.artifact_chain_verification` already traverses Goal 2, Goal 3, Goal 4, and existing HITL candidate refs by path/digest/kind.
- `builder_ii.artifact_index_records` recognizes governed artifact kinds as metadata only and does not activate them.
- `builder_ii.command_authority` separates Tier 1 artifact-only planning/validation from Tier 3 HITL-gated execution candidates and Tier 4 forbidden automation.

Evaluated architectural directions:

1. Reuse `builder_ii.hitl_verification_execution_candidate` as the Goal 5 manifest. Rejected because it is intentionally narrow: verification-command only, older proposal/approval/preflight/request refs, and not boundary-first around `builder_ii.hitl_approval_boundary`.
2. Define only `builder_ii.execution_candidate_manifest`. Accepted as the primary artifact because Goal 4 explicitly points to it and the next intrinsic object is a bounded candidate manifest.
3. Define `builder_ii.execution_candidate_manifest` plus `builder_ii.execution_candidate_manifest_validation_report`. Accepted because validation is a separate passive correction operator; it can prove structure without granting authority.
4. Add a runtime activation or executor artifact. Rejected and deferred to Goal 6 or later.

## 5. Proposed Goal 5 Artifact Kinds

Goal 5 should authorize these future implementation artifact kinds:

| Artifact kind | State | Purpose |
| --- | --- | --- |
| `builder_ii.execution_candidate_manifest` | candidate-only | Describes a bounded proposed future execution under a verified `builder_ii.hitl_approval_boundary`; it executes nothing. |
| `builder_ii.execution_candidate_manifest_validation_report` | validation-only | Validates candidate-manifest refs, scope, rollback requirements, verification requirements, denied boundaries, and authority invariants; it executes nothing and grants no authority. |

The manifest should be generic-first. CORE may appear only as a target profile value or target profile ref. There must be no CORE Workbench/UI coupling.

The manifest should wrap the existing `builder_ii.hitl_verification_execution_candidate` only by reference when a proposed future execution is specifically a verification command. It should not replace that specialized sibling in Goal 5. Reconciliation can happen later if implementation evidence proves the general manifest can subsume the specialized candidate without widening authority.

## 6. Deferred / Rejected Kinds

Goal 5 rejects or defers:

- `builder_ii.execution_activation_request` until Goal 6 or later;
- `builder_ii.execution_receipt` as Goal 5 evidence;
- `builder_ii.goose_runtime_activation_manifest`;
- `builder_ii.deepagents_runtime_dispatch_manifest`;
- `builder_ii.mcp_invocation_manifest`;
- arbitrary shell command manifests;
- autonomous patch application manifests;
- target repo mutation manifests unless a future RFC proves a safe sub-slice;
- memory mutation manifests;
- CORE Workbench/UI integration manifests.

Existing `builder_ii.hitl_verification_execution_candidate` remains a specialized sibling and may be referenced by `builder_ii.execution_candidate_manifest` as prior candidate evidence. It should not be renamed or expanded during Goal 5 implementation unless a separate reconciliation RFC is accepted.

## 7. Required Cryptographic Refs

The future `builder_ii.execution_candidate_manifest` must cryptographically bind all authoritative context through refs containing kind, path, and SHA-256 digest. At minimum, the design must support:

- `approval_boundary_ref` pointing to `builder_ii.hitl_approval_boundary`;
- `promotion_decision_ref` pointing to `builder_ii.hitl_promotion_decision`;
- `promotion_review_ref` pointing to `builder_ii.hitl_promotion_review`;
- `promotion_request_ref` pointing to `builder_ii.hitl_promotion_request`;
- source proposal refs from Goal 2/3, including `builder_ii.orchestration_assignment_plan`, `builder_ii.orchestration_assignment_validation_report`, `builder_ii.deepagents_proposal_result`, and/or `builder_ii.deepagents_work_validation_report`;
- `target_profile_ref`;
- `command_authority_ref` or immutable command authority snapshot ref;
- `verification_profile_ref` or `verification_profile_report_ref`;
- `rollback_plan_ref` or rollback-plan-required placeholder with expected kind `builder_ii.rollback_plan`;
- git state/preflight refs such as `builder_ii.git_state_record` and/or `builder_ii.preflight_record` when available;
- `candidate_scope_manifest_ref` when candidate scope is factored into a separate passive manifest later;
- `future_activation_gate_ref` only as an unresolved future requirement, never as current permission;
- `artifact_chain_verification_report_ref` when the source chain has already been verified.

The manifest must fail closed if any required ref is missing, unhashed, malformed, kind-mismatched, digest-mismatched, path-unsafe, or points outside the permitted approval boundary.

## 8. Allowed Candidate States

The manifest and validation report may use only explicitly passive states:

- `CANDIDATE_RECORDED_ONLY`
- `BOUNDARY_CHECKED_ONLY`
- `PREFLIGHT_REQUIRED_ONLY`
- `ROLLBACK_REQUIRED_ONLY`
- `VERIFICATION_REQUIRED_ONLY`
- `VALIDATION_ONLY`

Goal 5 must reject active or ambiguous states such as `AUTHORIZED`, `ENABLED`, `PROMOTED`, `EXECUTABLE`, `ACTIVE`, `RUNNING`, `EXECUTED`, `APPLIED`, `MERGED`, and `VERIFIED` unless they appear only inside a denial sentence such as "runtime execution is disabled".

## 9. Authority Boundary & Invariants

The future manifest and validation report must include or enforce this exact authority boundary:

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
  "runtime_execution": false,
  "source_writes": false,
  "memory_mutation": false,
  "artifact_is_authority": false,
  "bypasses_command_authority": false,
  "bypasses_verification": false,
  "grants_runtime_authority": false,
  "authorizes_execution": false,
  "grants_authority": false,
  "requires_separate_activation_artifact": true,
  "core_workbench_coupling": "NONE"
}
```

The same invariants must appear in any governance block. If the implementation uses `DISABLED` strings instead of booleans for a governance sub-block, the top-level authority flags above must still remain present and false where applicable.

The manifest may record `records_candidate_intent: true`, but it must never record `records_execution: true`, `authorizes_execution: true`, or `grants_authority: true`.

## 10. Candidate Scope Model

Permitted candidate scope:

- describes future operator-reviewed execution intent;
- binds to a verified `builder_ii.hitl_approval_boundary`;
- binds to a target profile (`generic`, `builder`, or `core`) without changing builder-II identity;
- records command previews only as inert strings or structured argument arrays;
- references command authority tier metadata or snapshots;
- references verification profile requirements;
- references rollback requirements;
- records denied boundaries;
- records required future proof artifacts;
- records dry-run expectations as expectations only;
- references existing specialized candidates such as `builder_ii.hitl_verification_execution_candidate` when applicable.

Denied candidate scope:

- shell execution or subprocess execution;
- model execution;
- tool execution;
- Goose runtime activation;
- deepagents construction or subagent dispatch;
- MCP invocation;
- network calls;
- target repo mutation;
- memory mutation;
- git mutation, commit, push, or PR creation;
- autonomous patch application;
- arbitrary command manifests not tied to command authority classification;
- execution receipts as proof that Goal 5 has run anything;
- CORE Workbench/UI coupling;
- Deephaven work.

Candidate command previews must be bounded by command authority metadata. Tier 0 or Tier 1 previews may describe structural validation. Tier 3 previews may describe HITL-gated execution-candidate intent only. Tier 4 commands must remain forbidden. No tier creates activation permission in Goal 5.

## 11. Rollback Requirements

Every manifest must encode rollback evidence requirements before any future activation can be considered:

- rollback policy is required;
- either a no-mutation assertion or a `builder_ii.rollback_plan` expected-kind ref is required;
- any future mutating sub-slice must require a `builder_ii.rollback_plan` before activation and a `builder_ii.rollback_receipt` after operator-managed rollback, but Goal 5 does not authorize that sub-slice;
- rollback requirements must bind to the approval boundary and candidate scope;
- rollback requirements must state that deleting the candidate manifest and validation report is the rollback path for Goal 5 itself.

Rollback evidence in Goal 5 is a requirement, not proof of completed rollback.

## 12. Verification Requirements

Every manifest must encode verification evidence requirements before any future activation can be considered:

- verification profile or verification profile report ref is required;
- proposed verification commands are inert previews and must not run;
- expected future `builder_ii.execution_verification_record` requirements must be recorded;
- expected future postflight and chain-binding requirements must be recorded when applicable;
- validation must fail closed if the manifest claims planned verification has already run;
- validation must fail closed if verification evidence is missing, kind-mismatched, digest-mismatched, or outside the approval boundary.

Verification evidence in Goal 5 is a requirement, not completed evidence.

## 13. Artifact Index Requirements

The later implementation PR must register:

- `builder_ii.execution_candidate_manifest`;
- `builder_ii.execution_candidate_manifest_validation_report`.

Artifact index recognition is inventory only. It records path, kind, schema version, byte count, validation state, and SHA-256 digest. It must not mark a manifest as executable, approved, activated, authoritative, or runtime-enabled.

## 14. Artifact Chain Verification Requirements

The later implementation PR must extend `builder_ii.artifact_chain_verification` so the chain verifier can traverse:

```text
execution_candidate_manifest
  -> approval_boundary_ref
  -> promotion_decision_ref
  -> promotion_review_ref
  -> promotion_request_ref
  -> Goal 2/Goal 3 source proposal refs
```

The chain verifier must also traverse target profile, command authority snapshot, verification profile/report, rollback plan, git state/preflight, existing specialized candidate refs, and any artifact chain verification report refs when present.

Chain verification is a correction operator. It proves hash/kind/path coherence only. It does not grant permission, does not execute commands, and does not convert candidate state into activation.

## 15. Command Authority Requirements

The future manifest-rendering and manifest-validation CLI surfaces, if implemented, must be non-executing candidate design, not activation.

Expected classification for a later CLI:

- render manifest command: Tier 1 artifact-only planning/validation if it only writes JSON to an explicit artifact output path;
- validate manifest command: Tier 1 validation-only;
- no executor command in Goal 5;
- no command-running code in Goal 5;
- no shell, model, tool, Goose, deepagents, MCP, network, target repo, memory, or git authority in Goal 5 commands.

If a later design treats the manifest itself as a Tier 3 HITL runtime candidate artifact, that classification must remain candidate-only and still forbid activation without a separate Goal 6 activation artifact.

## 16. Operator Command Surface Requirements

No operator command surface is implemented by this RFC. A later implementation may add passive commands such as:

- `builder-hitl candidate-manifest`
- `builder-hitl validate-candidate-manifest`

Those commands must be documented as artifact-only / validation-only. They may write only explicit artifact output paths. They must not run commands, launch Goose, construct deepagents, invoke MCP, call models, call tools, access networks, mutate target repositories, mutate memory, or create runtime sessions.

The operator documentation must preserve builder-II generic-first identity, state CORE as target profile only, forbid CORE Workbench/UI coupling, and forbid Deephaven work.

## 17. Validation Requirements

The future validator must fail closed when:

- `approval_boundary_ref` is missing or does not point to `builder_ii.hitl_approval_boundary`;
- the approval boundary is not `BOUNDARY_RECORDED_ONLY`;
- the source decision is not `approved_for_candidate_design`;
- promotion request/review/decision refs are missing, malformed, or inconsistent with the boundary;
- source proposal refs are missing or outside allowed Goal 2/Goal 3 source kinds;
- target profile is outside `generic`, `builder`, or `core`;
- CORE is treated as platform identity rather than target profile;
- CORE Workbench/UI coupling is anything other than `NONE`;
- any authority invariant is true;
- `requires_separate_activation_artifact` is not true;
- command previews are unclassified, Tier 4, arbitrary shell, or contain shell control syntax;
- rollback requirements are absent;
- verification requirements are absent;
- validation claims runtime execution, completed verification, or activation evidence;
- Deephaven appears as a work target or integration surface.

## 18. Tests Required for Implementation

The later implementation PR must include tests proving:

1. `builder_ii.execution_candidate_manifest` can be created and validated from a verified `builder_ii.hitl_approval_boundary`.
2. The manifest fails closed when the approval boundary is missing, invalid, not approved for candidate design, or digest-mismatched.
3. All authority invariants remain false, including `executes_model`, `executes_tools`, `executes_shell`, `invokes_goose`, `constructs_deepagents`, `constructs_subagents`, `invokes_mcp`, `performs_network_calls`, `mutates_target_repo`, `mutates_memory`, `runtime_execution`, `source_writes`, `memory_mutation`, `artifact_is_authority`, `bypasses_command_authority`, `bypasses_verification`, `grants_runtime_authority`, `authorizes_execution`, and `grants_authority`.
4. `requires_separate_activation_artifact: true` is required.
5. Candidate states are limited to `CANDIDATE_RECORDED_ONLY`, `BOUNDARY_CHECKED_ONLY`, `PREFLIGHT_REQUIRED_ONLY`, `ROLLBACK_REQUIRED_ONLY`, `VERIFICATION_REQUIRED_ONLY`, and `VALIDATION_ONLY`.
6. Command previews are inert and command authority classification is non-executing candidate design, not activation.
7. Shell/model/tool/Goose/deepagents/MCP/network/target repo/memory mutation boundaries are forbidden.
8. Existing `builder_ii.hitl_verification_execution_candidate` remains a specialized sibling or explicitly referenced prior candidate, not silently widened.
9. Artifact index and artifact chain verification registries recognize the new kinds after implementation.
10. Docs preserve builder-II generic-first identity, CORE as target profile only, no CORE Workbench/UI coupling, and no Deephaven work.

## 19. Rollback Path for Goal 5 Itself

This RFC is docs/test authorization only. Rollback for Goal 5 itself is:

1. Revert or delete `docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md`.
2. Remove the roadmap entry for the Goal 5 RFC.
3. Remove the RFC lock test.

If the later implementation exists, rollback is limited to deleting generated `builder_ii.execution_candidate_manifest` and `builder_ii.execution_candidate_manifest_validation_report` artifacts, plus reverting their code/docs/tests. Since Goal 5 performs no runtime execution and no target mutation, there is no runtime state to restore.

## 20. Future Handoff to Goal 6

Goal 6 or later must start from a verified Goal 5 manifest and still prove a separate activation artifact. The activation artifact must be distinct from `builder_ii.execution_candidate_manifest`, must be approved by its own RFC, and must pass the full promotion gate: docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.

Goal 6 remains deferred. Nothing in Goal 5 activates runtime execution, shell execution, model execution, tool execution, Goose runtime, deepagents dispatch, MCP calls, network calls, target repo mutation, memory mutation, source writes, git mutation, or hidden authority.
