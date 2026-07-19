# Getting started with builder-II

**Audience:** new operators and builders.  
**Goal:** one optimal path from zero → trustworthy local loop → using **STRATUM** to see and leverage the whole platform without confusing *display* with *authority*.

This page is the **map**. Deeper paths stay specialized:

| If you need… | Go to |
|--------------|--------|
| One proven 30‑min clone → patch loop (CI-smoked) | [`FIRST_SESSION.md`](../FIRST_SESSION.md) |
| Operator golden path / demo-loop | [`OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md) |
| STRATUM keys, flags, empty-spine troubleshooting | [`STRATUM.md`](STRATUM.md) |
| Philosophy / why the platform exists | [`MANIFESTO.md`](MANIFESTO.md) |
| What is promoted vs speculative | [`CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md), [`ROADMAP.md`](ROADMAP.md) |
| Full doc index | [`README.md`](README.md) |

---

## 1. Mental model (read once, keep forever)

builder-II is a **governed control plane** for local agent-assisted development. It is **not** CORE Workbench, not an autonomous engineer, and not “ChatGPT with a repo open.”

### Four load-bearing distinctions

```text
planned  ≠  executed  ≠  verified  ≠  promoted
artifact ≠  authority
model output ≠ approval
subagent output ≠ truth
```

If a UI, log line, or model message collapses any of these, **trust the artifact and the validator**, not the chrome.

### The recurring shape of the platform

Almost every capability follows the same verb grammar:

```text
artifact  →  validate-*  →  (HITL approve if needed)  →  execute  →  receipt / postflight
```

- **Artifact** — JSON with a `kind`, often digest-bound. Evidence, not permission.
- **Validate** — schema, digests, chain refs. Fail closed.
- **HITL** — human approval boundaries for authority-changing work.
- **Execute** — only promoted, fixed-argv lanes (never “the TUI felt like it”).
- **Receipt** — what actually happened, on disk, re-checkable.

### The Third Door (Builder’s Signet)

Any capability that **changes authority** needs all eight, in spirit and usually in evidence:

1. Documentation  
2. Tests  
3. CLI / command surface  
4. Failure mode  
5. Human approval boundary  
6. Output artifact  
7. Rollback path  
8. Verification path  

In STRATUM, **HITL / promotion instruments** surface this as the Third Door grid — slots stay **unevaluated** until real readiness evidence exists (never painted green by default).

### Determinism, auditability, traceability

| Pillar | What it means here | How you check |
|--------|--------------------|---------------|
| **Determinism** | Same inputs → same digests / frames where the surface claims it (CodeVault demos, prepare packages, gate receipts) | Re-run validators; CodeVault `demo` / `validate-demo`; never trust wall-clock-only stories |
| **Auditability** | Claims about the platform are matrix-backed; docs cannot over-claim | `builder-platform matrix`, `audit-docs`, `scripts/verify_v0_release.py` |
| **Traceability** | Chain of kinds and refs on disk; spine is a view of that chain, not a fake progress bar | Spine + pin in STRATUM; `verify_artifact_chain`; `.builder/artifacts` |
| **Governance** | Promotion states gate what may run; command authority tiers gate what may even be *attempted* | `builder-platform matrix` / **C** in STRATUM; `?` palette tier inspector |

---

## 2. Optimal starter path (recommended order)

Do this on a machine you control. Prefer **one git checkout** and stay in it (STRATUM reads *that* tree’s `.builder/`).

### Phase A — Install and identity (10 minutes)

```bash
git clone <builder-II> && cd builder-II
uv sync                          # Apple Silicon local models later: uv sync --extra mlx
cp .env.example .env             # defaults are self-target "builder" profile
```

Edit `.env` only when pointing at a real project:

```bash
BUILDER_TARGET_REPO=/path/to/your/repo
BUILDER_TARGET_PROFILE=generic   # or builder | core
BUILDER_ARTIFACT_ROOT=.builder/artifacts
BUILDER_RUNTIME_MODE=passive     # default: no surprise runtime
```

See also: [`CONFIG_ONBOARDING.md`](CONFIG_ONBOARDING.md).

**Sanity:**

```bash
uv run builder doctor
uv run builder-targets list
uv run builder-targets validate
uv run builder-agent profiles
uv run builder-tools check --tier tier1
```

### Phase B — Ask the platform what is true (5 minutes)

Do **not** start agents yet. Ask for evidence:

```bash
uv run python scripts/verify_v0_release.py
uv run builder-platform matrix
uv run builder-platform status
uv run builder-platform next
uv run builder-platform audit-docs
```

| Command | Why |
|---------|-----|
| `verify_v0_release.py` | Structural/governance anti-handwave harness |
| `matrix` | Every capability row + promotion-ish state |
| `status` / `next` | Operator summary + ordered safe next commands |
| `audit-docs` | Docs that claim more than the matrix allows → fail |

Optional golden-path bundle (no runtime, no model):

```bash
uv run builder-platform golden-path --target builder --output-dir .builder/artifacts/b9-golden-path
uv run builder-platform validate-golden-path .builder/artifacts/b9-golden-path/golden-path-report.json
```

### Phase C — First governed package (fills the chain)

```bash
uv run builder-session prepare-package generic \
  -o .builder/session \
  --task "first governed session"

uv run builder-session validate-prepare-package .builder/session
uv run builder-session summarize-prepare-package .builder/session
```

This is the first time the **artifact spine** has real meat. Details: [`GOVERNED_PREPARE_PACKAGE.md`](GOVERNED_PREPARE_PACKAGE.md), [`ARTIFACT_CHAIN_VERIFICATION.md`](ARTIFACT_CHAIN_VERIFICATION.md).

### Phase D — Open STRATUM (observe + compose)

From the **same** repo root:

```bash
uv run builder-stratum
# hero splash ~3s (any key skips) → operator console
# first open: walkthrough auto-opens if artifacts empty
# skip guide: --no-guide   force: --guide   skip splash: --no-splash
# env: STRATUM_SKIP_GUIDE=1
# equivalent: uv run builder stratum --experimental
```

Then use the instrument map in §3.

### Phase E — Full authority loop when ready

When you want propose → approve → verify → apply → rollback with receipts, leave STRATUM and follow:

- **[`FIRST_SESSION.md`](../FIRST_SESSION.md)** (canonical smoked path), or  
- **[`OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md)** demo-loop  

STRATUM will show chain / HITL / postflight **after** those CLIs write artifacts; it does not perform the loop for you.

---

## 3. STRATUM: leverage every instrument

STRATUM is an **instrument panel**, not a second control plane.

```text
inspect  →  compose  →  run (in your terminal)
```

### Spatial layout

| Column | Role |
|--------|------|
| **Spine (left)** | Pipeline stages as a living chain; density glyphs; pin/inspect |
| **Center** | Morphing instruments (idle, models, agents, audit, HITL, help…) |
| **Signals (right)** | HITL gate light, event ledger tail, capability caps (usually DISABLED here), RAM HUD |

Footer chain bar: **DIGEST —** until verification exposes one; **AUTH** not evaluated by display alone; **artifact_is_authority = FALSE** is healthy.

### Keymap → platform capability

| Key | Instrument | Platform surface it reflects | Compose / action |
|-----|------------|------------------------------|------------------|
| **0** | Walkthrough | First-session path | Opt-out **X** |
| **H** | Help (pages **[** **]**) | Full keymap + boundaries | — |
| **Idle / ESC** | Operator dashboard | `operator_status` / `operator_next` + chain stats | **N** next |
| **j/k SPC** | Spine / inspect | On-disk kinds under `.builder/artifacts` | Pin real JSON |
| **M** | Memory | Artifact memory atoms if present | — |
| **O** | Models | `.env` config + registry + routing policy | Compose policy/models; no spend |
| **U** | Deepagents | Profiles + readiness + forge compose lines | Second **U**: assign picker |
| **C** | Platform audit | Completion matrix rows | Same family as `builder-platform matrix` |
| **W** | Workflow | Recipes + workflow stages + goose manifest | Compose `builder-goose manifest` (hand-off is **G**) |
| **Y** | Orchestration | Plans / assignments / obligations on disk | Compose plan / lane-policy |
| **B** | CodeVault | Frame/vault JSON scan | Compose demo/status/frame |
| **E** | Quality gates | Required evidence / blockers template | Advisory artifact shape |
| **T** | Tooling | Local tool registry install check | — |
| **?** | Palette | Full `COMMAND_AUTHORITY` tiers | Compose if permitted |
| **~** | Composer | Context-injected CLI line | **Never executes** |
| **P** | Prepare wizard | Session prepare choices | Composes `builder-session prepare-package …` |
| **V** | Validate | Chain re-check + compose validate-prepare | |
| **G** | Goose hand-off | Uses existing read_only manifest, or **asks** before auto-prep; then `start-readonly` | Fail-closed on authority; still no raw Goose |
| **N** | Next | `create_operator_next_action_report` | Prefills composer |
| **A / R / I** | HITL ceremony | Pending proposal if any | Compose approve/reject; **I** inspect |

Details and flags: [`STRATUM.md`](STRATUM.md). In-app guide mirrors this.

### How to “use the whole system” from STRATUM

Think in **lanes**, not features:

1. **Truth lane** — **C**, **N**, `matrix` / `next` outside  
2. **Session lane** — **P** → terminal prepare → spine fills → **SPC** inspect  
3. **Model policy lane** — **O** (what *could* run; not a live call)  
4. **Agent design lane** — **U** (roster/readiness; forge/assign via composed CLI)  
5. **Runtime lane** — **G** asks before minting a passive read_only manifest if none exists, then hands off to `start-readonly`  
6. **HITL lane** — when a proposal is on disk, gate ceremony + compose **A/R**  
7. **Quality / tooling lane** — **E**, **T** before you claim “ready to merge”  

If a lane has no artifacts, STRATUM shows **absence** (empty spine, awaiting_generation). That is success of honesty, not failure of the product.

---

## 4. Subsystems in plain language

### Configuration & onboarding

- **Config** resolves targets, models, artifact roots without claiming runtime.  
- **Setup/onboarding** plans and validates; many apply paths stay unpromoted.  
- Commands: `builder-config *`, `builder-setup *` — see [`CONFIG_ONBOARDING.md`](CONFIG_ONBOARDING.md).  
- STRATUM does not replace setup; after setup artifacts exist, spine/inspect show them.

### Artifact chain & verification

- Kinds live under `.builder/` (often `artifacts/`).  
- `verify_artifact_chain` → valid/invalid, native errors, link health.  
- STRATUM spine ≈ pipeline stages; **V** re-runs verification for display.  
- Docs: [`ARTIFACT_INDEX.md`](ARTIFACT_INDEX.md), [`ARTIFACT_CHAIN_VERIFICATION.md`](ARTIFACT_CHAIN_VERIFICATION.md).

### HITL (human-in-the-loop)

- Request → evidence → approval → execute → receipt.  
- CLI family: `builder-hitl *`. Read-only CLI TUI: `builder hitl *` ([`TUI_INSPECTION_SURFACE.md`](TUI_INSPECTION_SURFACE.md)).  
- STRATUM **never harvests confirmation** for digests it merely renders.

### Goose (preferred local operator runtime, when promoted)

- Manifest first (`builder-goose manifest --mode read_only …`).  
- Start only via governed commands; STRATUM **G** only launches `start-readonly` after checks.  
- Docs: [`GOOSE_SESSION.md`](GOOSE_SESSION.md), [`GOOSE_READONLY.md`](GOOSE_READONLY.md), [`RUNTIME_PROMOTION.md`](RUNTIME_PROMOTION.md).

### Deepagents / orchestration / recipes / models

These are the four configuration surfaces people ask about first after “what is an artifact?”.  
**Full how-to:** [§5 below](#5-how-builder-ii-configures-work).

| Surface | STRATUM | Primary CLI |
|---------|---------|-------------|
| Goose recipes | **W** (inventory) | YAML under `recipes/` + Goose session/manifest |
| Deepagents | **U** | `builder-deepagents *`, Forge |
| Orchestration | **W** + compose | `builder-orchestration *` |
| Models / providers | **O** | `.env` + `builder-model-policy` / `builder models` / `builder-model` |

### CodeVault (Paid Commercial Plugin Upgrade)

- **Clifford Algebra $\text{Cl}(4,1)$ Geometry:** Content-addressed **layout-identity** geometry — not a vector DB, and not approximate vector or ANN/HNSW searches.
- **Chain:** `repo_map` → frames → optional CGA lift → exact recall → findings → context packs.
- **Clean Separation:** The CodeVault engine has been cleanly separated from open core to a paid commercial plugin (`builder-ii-code-vault`).
- **CLI Upgrade Seam:** In the open-source distribution, the `builder-code-vault` CLI command acts as a fail-closed seam. Every invocation (e.g. `frame`, `digest`, or `recall`) will echo a helpful upgrade message and exit with status `1`.
- **Acquiring CodeVault:** If you are interested in advanced hierarchical frames, exact geometric/structural recall, polyglot CPython AST extraction, and determinism demos, please reach out to the maintainers to inquire/ask about it.
- **Determinism expectation (with plugin):** Re-running vault demo/validate on a fixed repository fixture yields byte-identical frame digests.

### Quality gates & promotion

- Quality-gate artifacts list required evidence and merge blockers without executing tests.  
- Promotion readiness / decisions are separate kinds; Third Door maps to readiness evidence.  
- Docs: [`QUALITY_GATES.md`](QUALITY_GATES.md), [`PROMOTION_READINESS.md`](PROMOTION_READINESS.md), [`CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md).

---

## 5. How builder-II configures work

builder-II does **not** configure “agents” the way a SaaS dashboard does. You author **passive files and artifacts**; promotion and HITL decide if anything may execute. Order of operations is always:

```text
describe (YAML/JSON) → validate → (optional HITL) → execute only if promoted
```

### 5.1 Goose recipes (session behavior recipes)

**What they are:** Goose-oriented YAML playbooks under `recipes/` (top-level recipes + `recipes/subrecipes/`). They encode instructions, sub-recipe graphs, and workflow shape for a coding/platform session — **not** builder-II authority.

**What exists in-repo (examples):**

| Path | Role |
|------|------|
| `recipes/core-coding.yaml` | Governed coding agent recipe (invariants, workflow, model roster notes) |
| `recipes/core-platform.yaml` | Platform-oriented recipe; references subrecipes |
| `recipes/subrecipes/*.yaml` | `explore`, `implement`, `review`, `verify`, `plan`, … |

**builder-II’s way of setting them up:**

1. **Edit YAML in the repo** (or copy a template and specialize for your target).  
2. Keep recipes under the project’s `recipes/` tree so Goose sees them via `GOOSE_RECIPE_PATH` (projection/setup describe this path; default config key `goose_recipe_path` → `recipes`).  
3. **Do not treat a recipe file as a runtime grant.** Runtime still needs a **Goose session manifest** with an explicit mode (`read_only`, etc.) and, for start, a promoted/governed launch path.  
4. Session projection / wrapper plans may bind `recipe_name` / `recipe_path` into Goose argv (`goose session --recipe …`) when a non-readonly launch path is eventually used — still outside STRATUM’s write authority.

**Minimal operator loop:**

```bash
# Inspect inventory
ls recipes recipes/subrecipes

# STRATUM: W shows recipe inventory; G asks before minting a read_only manifest
# if none exists, then hands off to builder-goose start-readonly (authority-gated)
uv run builder stratum --experimental
# Optional: mint ahead of time so G skips the prompt
# mkdir -p .builder/goose && uv run builder-goose manifest --target generic --mode read_only \
#   --task "inspect only" --output .builder/goose/session.json
```

**Mental model:** recipes = *how the operator runtime should behave if launched*; manifests + promotion = *whether it may launch*. Auto-prep is opt-in (confirm dialog) and only creates a passive artifact — it does not start Goose or grant authority.


Docs: [`GOOSE_SESSION.md`](GOOSE_SESSION.md), [`GOOSE_RUNTIME.md`](GOOSE_RUNTIME.md), [`GOOSE_CONVENTION_LAYER.md`](GOOSE_CONVENTION_LAYER.md).

---

### 5.2 Deepagents (profiles, Forge, passive work chain)

**What they are:** optional **planning / subagent harness** under builder-II governance. They are not a second CORE runtime and must not bypass HITL.

**Two profile layers:**

| Layer | Location | Role |
|-------|----------|------|
| Built-in profiles | `builder_ii/agent_profiles.py` | Named roles (`repo_mapper`, `patch_planner`, …) with authority + tool allow/deny |
| Forge YAML templates | `profiles/deepagents/*.yaml` | Passive specs (cartographer, handoff scribe, orchestration architect, …) — **passive**, not runtime authority |

**builder-II’s way of creating a new deepagent:**

1. **Forge** (guided) — preferred:
   ```bash
   # Interactive wizard (Textual)
   uv run builder-deepagents forge

   # Headless dry-run (safe; no write)
   uv run builder-deepagents forge --non-interactive --dry-run \
     --name "my_cartographer" --profile generic \
     --description "Maps repo topology without writes" \
     --capabilities read_files,read_git \
     --output-artifact artifacts/deepagents/my_cartographer \
     --rollback-path rollback/deepagents/my_cartographer
   ```
2. Forge enforces **promotion-rule style checks** before emit (docs, output artifact, rollback, verification, HITL for write/shell).  
3. Emit writes **only** under `profiles/deepagents/{slug}.yaml` (plus optional handoff note) — not target source.  
4. **Readiness** before treating deepagents as available:
   ```bash
   uv run builder-deepagents readiness --target generic -o .builder/artifacts/deepagents-readiness.json
   uv run builder-deepagents validate-readiness .builder/artifacts/deepagents-readiness.json
   ```

**builder-II’s way of using deepagents for work (artifact chain, not “just run”):**

```text
work-plan → assign-subagent → (run-plan / results) → review / proposal →
  execution-candidate → approve-candidate → run-approved (only if promoted)
```

Concrete passive start:

```bash
# Policy + readiness first
uv run builder-deepagents policy -o .builder/artifacts/deepagents-policy.json
uv run builder-deepagents validate .builder/artifacts/deepagents-policy.json

# Work plan then assignment (passive artifacts)
uv run builder-deepagents work-plan --help    # inspect required flags
uv run builder-deepagents assign-subagent --help
```

**STRATUM:** **U** shows roster + bridge readiness; second **U** opens compose picker for `assign-subagent` (never dispatches).

Docs: [`DEEPAGENTS_FORGE.md`](DEEPAGENTS_FORGE.md), [`DEEPAGENTS_POLICY.md`](DEEPAGENTS_POLICY.md), [`DEEPAGENTS_WORK_ARTIFACTS.md`](DEEPAGENTS_WORK_ARTIFACTS.md), [`DEEPAGENTS_RUNTIME.md`](DEEPAGENTS_RUNTIME.md).

---

### 5.3 Orchestration (plans, assignments, obligations)

**What it is:** a **Goal / Law** style control surface for multi-agent *planning* — still **artifact_only / validation_only** by default. No autonomous writes, shell, model, MCP, or Goose from the orchestration CLI itself.

**builder-II’s way:**

```text
plan → validate
  → render-assignment → dry-run → validate
  → lane-policy → mint-obligation → status / why
```

**Starter commands:**

```bash
# 1) High-level plan (no agents constructed)
uv run builder-orchestration plan generic \
  --task "map then review auth module" \
  --roles repo_mapper,code_reviewer \
  -o .builder/artifacts/orch-plan.json
uv run builder-orchestration validate .builder/artifacts/orch-plan.json

# 2) Assignment plan (passive bindings)
uv run builder-orchestration render-assignment --help
# then validate + dry-run the emitted assignment plan

# 3) Lane policy + obligations (Law 1: no speech without a ticket)
uv run builder-orchestration lane-policy -o .builder/artifacts/lane-policy.json
uv run builder-orchestration validate-lane-policy .builder/artifacts/lane-policy.json
uv run builder-orchestration mint-obligation --help
uv run builder-orchestration status --help
uv run builder-orchestration why --help
```

**How this relates to deepagents:** orchestration describes *who may speak and under what ticket*; deepagents work-plan/assign bind *profiles and tasks* into passive assignment artifacts; **neither** is a silent multi-agent runtime.

**STRATUM:** **W** shows workflow stage grammar + recipe inventory (not a live orchestrator). Compose orchestration commands with **~** / **?**.

Docs: [`ORCHESTRATION_ASSIGNMENT.md`](ORCHESTRATION_ASSIGNMENT.md), [`ORCHESTRATION_OBLIGATIONS.md`](ORCHESTRATION_OBLIGATIONS.md).

---

### 5.4 Models and providers

Three separate layers — do not collapse them:

| Layer | Purpose | Hot path |
|-------|---------|----------|
| **A. Local config (`.env`)** | Which backend/alias this machine prefers | `BUILDER_MODEL_*` |
| **B. Passive registry + routing policy** | Catalog + recommendation rules (no spend) | `builder-model-policy` |
| **C. Governed call gateway** | Actual call + receipt when allowed | `builder-model call` |

#### A. Configure providers / aliases (local)

From `.env.example` (copy to `.env`):

```bash
BUILDER_MODEL_BACKEND=mlx-lm          # local MLX server path on Apple Silicon
BUILDER_MODEL_TIER=primary
BUILDER_MODEL_ALIAS=qwen-coder        # primary coding alias
BUILDER_MODEL_BASE_URL=http://127.0.0.1:8080/v1
BUILDER_MODEL_TEMPERATURE=0.0

# HF / MLX community repos per alias (override when testing conversions)
BUILDER_MLX_MODEL_PHI=mlx-community/Phi-4-mini-reasoning-4bit
BUILDER_MLX_MODEL_QWEN=mlx-community/Qwen2.5-Coder-7B-Instruct-4bit
# … see .env.example for full roster
```

**Doctrine (M1 16GB):** one model at a time; smallest lane that works; heavy lanes explicit opt-in. See [`model_role_matrix.md`](model_role_matrix.md).

```bash
uv run builder models                 # roster + cache status
# switch/reset runtime when changing aliases (prefer documented switch path)
uv run builder switch-model --help    # if available in your install
```

Cloud / OpenAI-compatible providers appear in the **passive client registry** as recorded clients (often stub/disabled until you promote a real endpoint). Secrets never go in registry JSON — use env **ref names**, not raw keys (registry validation rejects secret-shaped fields).

#### B. Registry and routing (passive)

```bash
# Recommend a route without executing
uv run builder-model-policy render \
  --task-intent coding \
  --max-risk local_network \
  -o .builder/artifacts/model-routing-recommendation.json

uv run builder-model-policy dry-run --help
uv run builder-model-policy validate .builder/artifacts/model-routing-recommendation.json
```

Also inspectable via root groups: `builder model routing *` / `builder model registry *` (read-only TUI surface).

**STRATUM:** **O** projects the client registry + routing rules (display only).

#### C. Actually calling a model (governed)

Only when you intend a real call and the gateway is permitted:

```bash
uv run builder-model call --help
uv run builder-model validate-receipt --help
```

Expect **envelope + receipt** artifacts. Prefer local lanes for day-to-day; treat cloud as escalation with HITL/promotion discipline. Direct `builder ask` / Goose sessions are separate operator paths — still bound by config and runtime promotion.

**Never:** paste API keys into artifacts, README, or STRATUM compose history.

---

### 5.5 How the four fit together (one picture)

```text
                    ┌─────────────────┐
                    │  Target profile │  generic | builder | core
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Goose recipes        Deepagent YAML      Model .env + registry
   recipes/*.yaml       profiles/deepagents  BUILDER_MODEL_* + policy
         │                   │                   │
         ▼                   ▼                   ▼
   goose manifest      work-plan/assign     routing recommendation
   (mode read_only…)   orchestration plan   (passive)
         │                   │                   │
         └─────────────┬─────┴─────────┬─────────┘
                       ▼               ▼
              HITL / promotion     governed execute
              (if authority)       (model call / goose start / …)
                       │
                       ▼
                 receipts + postflight + spine (STRATUM observes)
```

**STRATUM’s job in this picture:** make each box legible (**O/U/W/G/C/N**) and hand you the next CLI line — not collapse the boxes into one “Run” button.

---

## 6. Target profiles

| Profile | Role |
|---------|------|
| `generic` | Default external project |
| `builder` | Platform self-target (this repo) |
| `core` | CORE as a *target*, not builder-II’s identity |

List/validate: `builder-targets list|validate`. Demo: [`TARGET_PROFILE_DEMOS.md`](TARGET_PROFILE_DEMOS.md).

---

## 7. Common failure modes (and the correct read)

| You see | Correct interpretation | Next move |
|---------|------------------------|-----------|
| Empty STRATUM spine | No kinds in **this** checkout’s `.builder/artifacts` | prepare-package here, or launch STRATUM from the tree that has artifacts |
| Chain valid FALSE | Schema drift / invalid governance / unknown kinds on disk | Print `verify_artifact_chain` errors; fix or archive stale JSON |
| DIGEST — | No ambient chain digest from verifier | Do not invent one; pin artifact-local digest fields if present |
| Epistemic matrix “green” on old UI | Fake defaults on pre-revamp builds | Use feattui-revamp / current STRATUM (defaults to —) |
| Capabilities all DISABLED in rail | STRATUM grants no execution caps | Expected; use governed CLI for real work |
| `N` suggests matrix forever | Incomplete matrix rows | Read blockers; promote only with evidence, not by re-running TUI |
| Deepagents “Dispatch” language | Old UI copy; surface composes only | Use current STRATUM; run `builder-deepagents assign-subagent` yourself |
| Forge emit blocked | Missing Third-Door-style fields / HITL gates for write-shell | Fix preview checklist; dry-run first |
| Model call fails / no server | MLX server not up or wrong `BASE_URL` | Start local server; check `builder models`; one model at a time |
| Orchestration plan “does nothing” | By design — artifact_only | `validate` + `dry-run`; separate HITL for any real run |

---

## 8. Suggested weekly operator rhythm

1. `builder-platform matrix` + **C** in STRATUM — what is true  
2. `builder-platform next` + **N** — what to do next  
3. Session prep / validate — keep the chain honest  
4. Review recipes / deepagent YAML if session shape changed  
5. `builder-model-policy render` + **O** before changing default aliases  
6. CodeVault frame/demo when geometry recall matters  
7. HITL only when changing authority — compose from STRATUM, approve in CLI  
8. `audit-docs` before you write README claims  

---

## 9. Hardware note (mechanical sympathy)

Primary design target: **Apple Silicon, ~16GB unified memory**. Local MLX models should stay in a modest footprint (~2–7GB class). STRATUM’s RAM HUD is a reminder, not a guarantee. Heavier lanes are explicit opt-in, not defaults. See [`model_role_matrix.md`](model_role_matrix.md).

---

## 10. Where to go next

| Path | Document |
|------|----------|
| Smoked first loop | [`FIRST_SESSION.md`](../FIRST_SESSION.md) |
| Golden path / demos | [`OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md) |
| STRATUM reference | [`STRATUM.md`](STRATUM.md) |
| Recipes / Goose | [`GOOSE_SESSION.md`](GOOSE_SESSION.md), [`GOOSE_RUNTIME.md`](GOOSE_RUNTIME.md) |
| Deepagents | [`DEEPAGENTS_FORGE.md`](DEEPAGENTS_FORGE.md), [`DEEPAGENTS_WORK_ARTIFACTS.md`](DEEPAGENTS_WORK_ARTIFACTS.md) |
| Orchestration | [`ORCHESTRATION_ASSIGNMENT.md`](ORCHESTRATION_ASSIGNMENT.md), [`ORCHESTRATION_OBLIGATIONS.md`](ORCHESTRATION_OBLIGATIONS.md) |
| Models | [`model_role_matrix.md`](model_role_matrix.md), `.env.example` |
| Command encyclopedia | [`OPERATOR_COMMAND_SURFACE.md`](OPERATOR_COMMAND_SURFACE.md) |
| Invariants | [`GOVERNANCE_INVARIANTS.md`](GOVERNANCE_INVARIANTS.md) |
| CodeVault | CodeVault CLI seam / `builder-code-vault` (Plugin Upgrade Required) |
| Manifesto | [`MANIFESTO.md`](MANIFESTO.md) |

---

## 11. One-sentence contract

**builder-II produces reviewable evidence and gated commands; STRATUM makes that evidence legible and the next honest command one keystroke away — it never becomes the authority.**
