# Agent Operating Procedures for builder-II

## 1. System Authority (READ THIS FIRST)
You are operating within `builder-II`, a governed control plane for local agent-assisted software development.

* **YOU DO NOT POSSESS INHERENT AUTHORITY.** You are a reasoning/proposal adapter. Your outputs are artifacts, not commands.
* You must strictly adhere to the following epistemological boundaries:
  - *Planned* is not *executed*.
  - *Executed* is not *verified*.
  - *Verified* is not *promoted*.
  - *Model output* is not *approval*.

## 2. Engineering Pillars (The Builder's Signet)
All proposed code, plans, and architectures must reflect:

* **Mechanical Sympathy:** The primary target is an Apple Silicon M1 (16GB unified memory). Do not propose heavy, memory-intensive dependencies. All MLX models must fit within a 2GB-7GB footprint.
* **Semantic Rigor:** Maintain exact meaning across all artifacts. Never conflate a manifest with runtime evidence.
* **The Third Door:** Every capability that changes authority requires docs, tests, a command surface, a failure mode, a human approval boundary, an output artifact, a rollback path, and a verification path.
* **Honesty pins ≠ non-implementation:** A default `false` / fail-closed pin rejects *false claims*; it is **not** permission to skip building the governed execution path. Implement full logic; pin unearned claims. See `docs/HONESTY_PINS_VS_IMPLEMENTATION.md`.

## 3. Platform Integration Rules
Do not attempt to bypass the governed control plane. All actions must flow through the appropriate adapter:

* **Goose Adapter:** The approved operator runtime substrate. Propose session manifests for Goose; do not assume Goose decides authority.
* **deepagents Adapter:** Used strictly for structured delegation and interrupt/resume behaviors within governed artifacts.
* **MCP Adapter:** Treat all external capabilities as inventory-first, deny-by-default. Do not invent tools.

## 4. Operational Workflow Requirements
When tasked with a feature or bug fix:

1. **Plan Phase:** Generate a passive read-only execution plan artifact (e.g., `builder_ii.verification_execution_plan`).
2. **Halt for HITL:** You must stop and wait for a Human-In-The-Loop approval artifact before proceeding.
3. **Execution:** Once approved, execute strictly within the bounds of the provided receipt.
4. **Verification:** Generate an evidence bundle. Do not self-certify correctness.

## 5. Version Control & Repository Management
**CRITICAL**: This repository is hosted on a private **Forgejo** server, NOT GitHub.
- **DO NOT** use the `gh` (GitHub) CLI.
- **DO NOT** attempt to push, pull, or clone from `github.com`.
- **USE** the `tea` CLI (Gitea/Forgejo CLI) for issues, PRs, and repository management.
- **USE** the provided Forgejo MCP tools if available.
- **LOCAL CI ONLY**: You MUST run the local CI script (e.g. `bash scripts/ci.sh`) and ensure all gates pass BEFORE pushing commits or creating a Pull Request. Do not rely on the remote Forgejo runner to catch CI failures.

## 6. Reasoning & Problem-Solving Discipline (non-trivial design/R&D)

LLM agents are not reliably intelligent by default; builder-II's governance exists partly to catch that. On every non-trivial task — anything touching a load-bearing module (`command_authority.py`, `platform_completion_audit.py`, the verification/HITL lanes, the promotion docs) or crossing a promotion boundary — hold to this protocol. Skipping steps produces confident-sounding work that is wrong in load-bearing ways.

1. **Read the code — never reason from names or structure alone.** Read the implementation, trace imports and call sites, and identify the invariant the module protects. `hitl_patch_apply.py` tells you nothing until you have read which gate it enforces before any I/O.
2. **Find the shape — what underlying structure does the problem have?** Name the repeating structure before proposing a solution. Most builder-II subsystems are one shape: build a `kind`-tagged artifact → `finalize`/attach digest → a paired `validate-*` re-checks schema, digests, and chain refs → downstream consumes it. Make that shape visible; don't paper over it. Duplication is a symptom of an unnamed shape.
3. **Rank by leverage — genius-to-effort, not ease.** Rank possible changes by how much structural load they remove vs. the effort they take, and implement in that order. Doing the easy, low-leverage change first and skipping the high-leverage one optimizes for the wrong thing.
4. **Enumerate changes precisely — no ambiguity about what goes where.** Before committing, state every change, the file it lives in, and why; the commit message must reflect it. Vague commits ("refactor", "cleanup") are unacceptable on load-bearing modules.
5. **Prove against real claims — not abstract correctness.** "Tests pass" is not proof. Name the specific pinned assertion the change preserves or enables: a truth-matrix row/state in `platform_completion_audit.py`, a pin in `test_platform_completion_truth.py` / `test_docs_truth_enforcement.py`, a promotion state in `docs/CAPABILITY_PROMOTION.md`, or a digest-bound artifact and its `validate-*` lane. State the exact command that verifies it (the smallest `uv run pytest …` selection, plus `builder-platform audit-docs` / `builder-platform matrix` when docs or the matrix are in play). If no lane covers the change, say so — that gap is itself a finding.
6. **Connect to the governance model — what does this do for the platform's guarantees?** builder-II is a governed control plane, not an autonomous engineer. Every non-trivial change must be articulable in terms of the load-bearing distinctions it strengthens — *planned ≠ executed ≠ verified ≠ promoted*, *artifact ≠ authority*, *model output ≠ approval* — and the single verb grammar *artifact → validate → approve → execute → receipt*. If you cannot state which distinction the change strengthens, or whether it moves a capability across a promotion boundary (and therefore needs the eight promotion gates plus an evidence-backed matrix flip — never documentation alone), the change is not yet understood well enough to ship. (builder-II has no internal cognition pipeline of its own to map work onto — that belongs to CORE, the AI architecture; builder-II's "model" is this governance grammar.)
7. **Commit with discipline — right branch, right invariant, right lane.** Confirm repo state and branch before every commit. Forgejo-hosted: branch from `main`, open PRs with `tea`, never `gh`, never push to `github.com`, never commit directly to `main`. State which invariant or promotion state the change protects, and run the smallest slice of `.github/workflows/ci.yml` that proves it before declaring done.

**Failure modes this prevents:** reasoning from file names instead of the code (wrong analysis); solving before finding the shape (solutions that recreate the same problem as a second artifact vocabulary or a parallel validator); doing the easy changes first (high-leverage work never ships); vague success criteria (regressions that pass "tests" but break a pinned truth claim or silently inflate a promotion state); changes that can't be tied to the governance model (drift away from the "artifact, not authority" boundary the whole platform enforces).
