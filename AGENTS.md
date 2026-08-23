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
For governed changes to a separate target repository after builder-II has been
independently qualified for that use:

1. **Plan Phase:** Generate a passive read-only execution plan artifact (e.g., `builder_ii.verification_execution_plan`).
2. **Halt for HITL:** You must stop and wait for a Human-In-The-Loop approval artifact before proceeding.
3. **Execution:** Once approved, execute strictly within the bounds of the provided receipt.
4. **Verification:** Generate an evidence bundle. Do not self-certify correctness.

### Bootstrap boundary: builder-II does not govern its own development

Until the complete product has been independently proven and explicitly admitted for
self-hosting, the workflow above does **not** authorize builder-II to plan, approve,
execute, or verify changes to builder-II itself. During builder-II development:

* `builder-verify`, `builder-hitl`, proposals, approvals, receipts, ledgers, and related
  artifacts may be exercised only as test subjects and diagnostic outputs.
* Those artifacts are not development authority, merge evidence, or substitutes for
  ordinary operator-supervised engineering review.
* In-scope changes proceed through direct repository inspection, edits, focused tests,
  final local CI, and normal Git/GitHub review under the active user mission.
* Active worktrees and retained evidence belong in durable project-local development
  storage. Host temporary directories such as `/private/tmp` are disposable scratch
  space, not durable custody.

Self-hosting requires a separate, explicit platform admission backed by independent
end-to-end evidence. No individual passing artifact or capability promotes the system
into that state.

## 5. Version Control & Repository Management
**CRITICAL**: This repository uses GitHub for source control and pull requests, but
does not use GitHub-hosted workflows or required status checks.
- Use the `gh` (GitHub) CLI for explicitly authorized repository and pull-request operations.
- Do not create, enable, or rely on GitHub Actions workflows for verification.
- **LOCAL CI ONLY**: You MUST run `bash scripts/ci.sh` and ensure all gates pass BEFORE pushing commits or creating a Pull Request. The local gate-battery receipt is the merge evidence.

## 6. Reasoning & Problem-Solving Discipline (non-trivial design/R&D)

LLM agents are not reliably intelligent by default; builder-II's governance exists partly to catch that. On every non-trivial task — anything touching a load-bearing module (`command_authority.py`, `platform_completion_audit.py`, the verification/HITL lanes, the promotion docs) or crossing a promotion boundary — hold to this protocol. Skipping steps produces confident-sounding work that is wrong in load-bearing ways.

1. **Read the code — never reason from names or structure alone.** Read the implementation, trace imports and call sites, and identify the invariant the module protects. `hitl_patch_apply.py` tells you nothing until you have read which gate it enforces before any I/O.
2. **Find the shape — what underlying structure does the problem have?** Name the repeating structure before proposing a solution. Most builder-II subsystems are one shape: build a `kind`-tagged artifact → `finalize`/attach digest → a paired `validate-*` re-checks schema, digests, and chain refs → downstream consumes it. Make that shape visible; don't paper over it. Duplication is a symptom of an unnamed shape.
3. **Rank by leverage — genius-to-effort, not ease.** Rank possible changes by how much structural load they remove vs. the effort they take, and implement in that order. Doing the easy, low-leverage change first and skipping the high-leverage one optimizes for the wrong thing.
4. **Enumerate changes precisely — no ambiguity about what goes where.** Before committing, state every change, the file it lives in, and why; the commit message must reflect it. Vague commits ("refactor", "cleanup") are unacceptable on load-bearing modules.
5. **Prove against real claims — not abstract correctness.** "Tests pass" is not proof. Name the specific pinned assertion the change preserves or enables: a truth-matrix row/state in `platform_completion_audit.py`, a pin in `test_platform_completion_truth.py` / `test_docs_truth_enforcement.py`, a promotion state in `docs/CAPABILITY_PROMOTION.md`, or a digest-bound artifact and its `validate-*` lane. State the exact command that verifies it (the smallest `uv run pytest …` selection, plus `builder-platform audit-docs` / `builder-platform matrix` when docs or the matrix are in play). If no lane covers the change, say so — that gap is itself a finding.
6. **Connect to the governance model — what does this do for the platform's guarantees?** builder-II is a governed control plane, not an autonomous engineer. Every non-trivial change must be articulable in terms of the load-bearing distinctions it strengthens — *planned ≠ executed ≠ verified ≠ promoted*, *artifact ≠ authority*, *model output ≠ approval* — and the single verb grammar *artifact → validate → approve → execute → receipt*. If you cannot state which distinction the change strengthens, or whether it moves a capability across a promotion boundary (and therefore needs the eight promotion gates plus an evidence-backed matrix flip — never documentation alone), the change is not yet understood well enough to ship. (builder-II has no internal cognition pipeline of its own to map work onto — that belongs to CORE, the AI architecture; builder-II's "model" is this governance grammar.)
7. **Commit with discipline — right branch, right invariant, right lane.** Confirm repo state and branch before every commit. GitHub-hosted source control: branch from `main`, open PRs with `gh`, never commit directly to `main`. State which invariant or promotion state the change protects, and run the relevant local `bash scripts/ci.sh` gate before declaring done.

**Failure modes this prevents:** reasoning from file names instead of the code (wrong analysis); solving before finding the shape (solutions that recreate the same problem as a second artifact vocabulary or a parallel validator); doing the easy changes first (high-leverage work never ships); vague success criteria (regressions that pass "tests" but break a pinned truth claim or silently inflate a promotion state); changes that can't be tied to the governance model (drift away from the "artifact, not authority" boundary the whole platform enforces).

## 7. Scientific & Governance Closure Protocol (Evidence Custody Standards)

When closing an implementation plan set or sealing benchmark/runtime evidence:

1. **Cryptographic Binding Invariant**: Derivative reports must cryptographically cover the manifests they evaluate. When computing `report_digest`, never exclude `manifest_digest` (`report_digest` must retain `manifest_digest`).
2. **Exact-Tip Evidence Provenance**: Physical raw-sample measurements must bind exact collection metadata (`git_commit`, `git_tree`, methodology SHA, runtime identity). Never reuse or re-wrap previous raw samples under a new HEAD manifest; recollect physical evidence on the exact commit tip.
3. **Provider Contact Telemetry & Pre-Output Cost Accounting**: Distinguish pre-provider connection failures (`provider_contacted=False`, zero tokens/cost) from post-contact timeouts or HTTP errors occurring before public token emission (`provider_contacted=True`). Debit budget successors conservatively with input token costs when the provider was reached.
4. **Authentic Source Reconstruction**: Any validator named `reconstruct_and_validate_*` must perform genuine, independent reconstruction from raw canonical source artifacts rather than passively accepting already assembled route/state objects.
5. **Deterministic Async Testing**: Forbid static sleeps in async, socket, or IPC cancellation tests. Use bounded polling on terminal states with deterministic timeouts to prevent race conditions and test flakiness.
6. **Strict Closure Sequence**: Never self-certify closure without executing the full adversarial custody loop:
   ```text
   code settled
   → commit
   → exact-tip physical collection
   → validate raw sample provenance
   → build exact-tip manifest/report
   → independently validate report
   → exact-tip receipt CI
   → validate CI receipt
   → clean worktree
   → push
   → PR update
   ```

