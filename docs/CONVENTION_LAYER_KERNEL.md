# Convention Layer Kernel

**Status:** Design v1 — For review and incremental implementation
**Owner:** CORE builder-II platform
**Date:** 2026-06-27

## Purpose

The Convention Layer Kernel is the single, canonical abstraction that unifies all builder-II governed artifacts around the Codename Goose execution substrate.

It enforces the core doctrine:

> Use Codename Goose natively underneath.
> Expose builder conventions above.
> Preserve governance and evidence around the seam.

Every resolved session, Goose projection, orchestration plan, approval spec, dry-run, verification report, and handoff must be expressible through (or compose with) this kernel.

## Design Principles (Non-Negotiable)

1. **Semantic Rigor** — Every field has precise meaning. A plan is never execution. A projection is never authority. Evidence is always explicit.
2. **Mechanical Sympathy** — Respects real local development (Git, repos, Goose recipes, human review loops).
3. **Fail-Closed Governance** — Unknown states, missing evidence, or authority escalation are rejected visibly.
4. **Projection Purity** — The kernel produces deterministic, inspectable Goose-native surfaces without side effects.
5. **Evidence Chaining** — Every artifact carries or links to verifiable provenance.
6. **Generic-First** — Works for `generic`, `builder`, and `core` target profiles without leakage.

## Core Concepts

### 1. ResolvedSessionSpine

The canonical resolved state before any projection or execution consideration.

```python
@dataclass(frozen=True)
class ResolvedSessionSpine:
    target_profile: str
    repo_path: str
    agent_profile: str
    prompt_profile: str | None
    verification_profile: str
    authority_mode: AuthorityMode  # PLANNED_ONLY | PROPOSED | APPROVED etc.
    context_pack_ref: str | None
    model_policy: ModelPolicy
    goose_projection_policy: GooseProjectionPolicy
    required_evidence: list[str]
    handoff_expectation: HandoffExpectation
    # Immutable governance block
    governance: GovernanceBlock  # runtime_execution=DISABLED, artifact_is_authority=False, ...
```

### 2. GooseNativeProjection

Deterministic output suitable for Goose (env, recipe, context, etc.).

```python
@dataclass(frozen=True)
class GooseNativeProjection:
    provider: str
    model: str
    planner_provider: str | None
    planner_model: str | None
    recipe_path: str | None
    working_directory: str
    session_name: str
    context_pack_ref: str | None
    builtins: list[str]
    extensions: list[str]
    # Plus any custom builder_ fields for convention
    builder_model_tier: str | None
    builder_session_mode: str
    governance: GovernanceBlock
```

### 3. GovernedArtifact (Base)

All first-class artifacts inherit or compose with this.

```python
class GovernedArtifact(ABC):
    @property
    @abstractmethod
    def artifact_kind(self) -> str: ...

    @property
    @abstractmethod
    def governance(self) -> GovernanceBlock: ...

    def validate(self) -> ValidationResult: ...
    def to_chain_record(self) -> ArtifactChainRecord: ...
```

### 4. GovernanceBlock (Immutable)

```python
@dataclass(frozen=True)
class GovernanceBlock:
    runtime_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"]
    model_execution: Literal["DISABLED", ...]
    shell_execution: Literal["DISABLED", ...]
    source_writes: Literal["DISABLED", ...]
    artifact_is_authority: bool = False
    core_workbench_coupling: Literal["NONE", "TARGET_ONLY"] = "NONE"
    # ... other fields

    def is_safe_for_projection(self) -> bool:
        return self.runtime_execution == "DISABLED" and not self.artifact_is_authority
```

## Kernel Responsibilities

- Resolve a `ResolvedSessionSpine` from target + profiles + context
- Produce `GooseNativeProjection` from spine (pure function)
- Validate governance boundaries at every transition
- Generate dry-run / approval / handoff artifacts
- Register with `ArtifactIndex` and `ChainVerifier`
- Support introspection and diffing of projections

## Migration Path (Existing Code)

Existing modules will gradually compose with or delegate to the kernel:

- `session_config.py` → produces `ResolvedSessionSpine`
- `goose_projection.py` → produces `GooseNativeProjection` via kernel
- `orchestration_plan.py` → uses kernel for role-level spines
- `goose_wrapper_plan.py`, `runtime_activation_approval.py`, `orchestration_dry_run.py` → built on kernel outputs

## Implementation Order

1. Core dataclasses + GovernanceBlock + validation
2. Spine resolution + pure projection function
3. Base `GovernedArtifact` + registration helpers
4. Integration points with existing Goose modules
5. CLI surfaces updated to use kernel
6. Full test suite + scenario coverage

## Non-Goals (For Now)

- Actual Goose process launching (remains outside builder-II authority)
- Deepagents runtime construction
- Any autonomous mutation or execution

This kernel makes the convention layer inevitable, auditable, and scalable while preserving the strict authority boundary with Codename Goose.
