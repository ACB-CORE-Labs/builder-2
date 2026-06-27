# Convention Layer Kernel

**Status:** Design v1.1 — Updated to address Issue #115
**Owner:** CORE builder-II platform
**Date:** 2026-06-27

## Purpose

The Convention Layer Kernel is the single, canonical abstraction that unifies all builder-II governed artifacts around the Codename Goose execution substrate.

It enforces the core doctrine from ADR-0002:

> Use Codename Goose natively underneath.
> Expose builder conventions above.
> Preserve governance and evidence around the seam.

Every resolved session, Goose projection, orchestration plan, approval spec, dry-run, verification report, and handoff must be expressible through (or compose with) this kernel.

## Design Principles (Non-Negotiable)

1. **Semantic Rigor** — Every field has precise meaning. A plan is never execution. A projection is never authority. Evidence is always explicit and chain-linked.
2. **Mechanical Sympathy** — Respects real local development (Git state, repos, Goose recipes, human review loops, existing tool surfaces).
3. **Fail-Closed Governance** — Unknown states, missing evidence, or authority escalation are rejected visibly with typed errors.
4. **Projection Purity** — Produces deterministic, inspectable Goose-native surfaces without side effects.
5. **Evidence Chaining** — Every artifact carries or links to verifiable provenance via ArtifactIndex and ChainVerifier.
6. **Generic-First** — Works cleanly for `generic`, `builder`, and `core` target profiles without leakage.

## Core Concepts

### 1. ResolvedSessionSpine

The canonical resolved state before any projection or execution consideration.

```python
@dataclass(frozen=True)
class ResolvedSessionSpine:
    target_profile: str
    repo_path: str
    agent_profile: str
    prompt_profile: Optional[str]
    verification_profile: str
    authority_mode: AuthorityMode
    context_pack_ref: Optional[str]
    model_policy: dict[str, Any]
    goose_projection_policy: dict[str, Any]
    required_evidence: list[str]
    handoff_expectation: dict[str, Any]
    governance: GovernanceBlock

    def validate(self) -> ValidationResult: ...
```

### 2. GooseNativeProjection

Deterministic output suitable for direct use with Codename Goose.

```python
@dataclass(frozen=True)
class GooseNativeProjection:
    provider: str
    model: str
    planner_provider: Optional[str]
    planner_model: Optional[str]
    recipe_path: Optional[str]
    working_directory: str
    session_name: str
    context_pack_ref: Optional[str]
    builtins: list[str]
    extensions: list[str]
    builder_model_tier: Optional[str]
    builder_session_mode: str
    governance: GovernanceBlock

    def validate(self) -> ValidationResult: ...
```

### 3. GovernanceBlock (Immutable)

```python
@dataclass(frozen=True)
class GovernanceBlock:
    runtime_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    model_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    shell_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    source_writes: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    git_mutation: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    artifact_is_authority: bool
    core_workbench_coupling: Literal["NONE", "TARGET_ONLY"]
    deepagents_activation: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]

    def is_safe_for_projection(self) -> bool: ...
    def to_dict(self) -> dict[str, Any]: ...
```

### 4. GovernedArtifact Protocol

All first-class artifacts should implement or compose with:

```python
class GovernedArtifact(Protocol):
    artifact_kind: str
    governance: GovernanceBlock

    def validate(self) -> ValidationResult: ...
    def to_chain_record(self) -> ArtifactChainRecord: ...
```

### 5. ConventionKernelPlatformBundle

The canonical platform spine bundle coordinates the entire set of passive planning/verification specifications. It is produced by:

```python
bundle = kernel.prepare_platform_spine(
    settings,
    target_profile,
    repo_path=...,
    task=...,
)
```

It is strictly planned-only/artifact-only and preserves the following constraints:
- It **does not grant authority** or execute any runtime.
- It **does not start Goose** or Goose runtime sessions.
- It **does not start deepagents** or delegate to agents.
- It **does not run models** or perform LLM inference.
- It **does not mutate target repository source code**.
- It **does not replace the command authority registry**.
- It **checks the command authority registry** for every referenced planned/verification command. If a command is unregistered, or classified as Tier 2+ without an explicit operator-managed marking, the kernel will refuse to build the platform spine.

## Kernel Responsibilities

- Resolve a `ResolvedSessionSpine` by delegating to existing `profile_resolution.py`, `context_pack.py`, `target_profiles.py`, and `model_policy.py`.
- Produce pure `GooseNativeProjection` from a validated spine.
- Generate dry-run, approval, and handoff artifacts that are chain-verifiable.
- Enforce governance at every transition with typed errors.
- Register outputs with `ArtifactIndex` and `ChainVerifier`.
- Support introspection, diffing, and provenance queries.

## Integration Points (Existing Codebase)

- `profile_resolution.py` → supplies resolved profiles into spines
- `context_pack.py` → supplies context_pack_ref and content
- `goose_projection.py` + `goose_recipe_context_projection.py` → should delegate to kernel for projection creation
- `orchestration_plan.py` + `orchestration_dry_run.py` → use kernel for role-level spines
- `artifact_chain_verification.py` → accepts kernel-produced records
- `handoff_artifacts.py` → should produce chain-linked handoff records from kernel outputs

## Acceptance Criteria (from Issue #115)

- [x] docs/CONVENTION_LAYER_KERNEL.md updated with explicit platform spine bundle details and delegation model
- [x] tests/test_convention_kernel.py and tests/test_convention_kernel_platform_spine.py exist with scenario coverage (happy path + adversarial governance cases)
- [x] Kernel produces chain-verifiable records
- [x] All projections remain safe (governance.is_safe_for_projection())
- [x] Acceptance command: `uv run pytest tests/test_convention_kernel.py tests/test_convention_kernel_platform_spine.py tests/test_registry_closure.py -q`

## Non-Goals

- Launching Codename Goose or any runtime execution
- Constructing deepagents subagents
- Any autonomous source or git mutation

This kernel makes the convention layer inevitable, auditable, and scalable while preserving the strict authority boundary with Codename Goose.
