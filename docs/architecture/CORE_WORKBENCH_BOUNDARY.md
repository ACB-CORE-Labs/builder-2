# CORE Workbench Boundary (V.5)

**Status:** `SPEC_ONLY` / design hygiene (V.5)  
**Promotion:** none — documentation only; no runtime surface, no adapter, no authority grant  
**Related:** [ADR-0003](../adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md), [TARGETS.md](../TARGETS.md), [builder_ii/targets/core.py](../../builder_ii/targets/core.py) (V.4 catalog)

> **One line:** builder-II can help **build and verify Workbench *source code*** as a repository target; builder-II is **not** CORE Workbench, not CORE UI/UX, and not a Workbench driver.

---

## 1. Identity map (non-negotiable)

```text
builder-II     = generic governed platform for local agent-assisted software development
CORE           = deterministic cognitive engine + first-class *target profile* / lineage
CORE Workbench = product UI/cockpit surface that lives in the CORE product context
```

| Claim | Allowed? |
| --- | --- |
| builder-II is a generic governed developer platform | Yes |
| CORE is a target profile (`target=core`) | Yes |
| builder-II may prepare context, plans, and HITL-gated patches against CORE (or Workbench) *repos* | Yes (as target work) |
| builder-II **is** CORE Workbench / CORE UI | **No** |
| builder-II drives Workbench UX flows or owns cockpit state | **No** |
| `governance.core_workbench_coupling` is anything other than `NONE` | **No** (today) |

These distinctions are load-bearing: **planned ≠ executed ≠ verified ≠ promoted**, **artifact ≠ authority**, **model output ≠ approval**. Workbench identity is a product boundary, not a branding preference.

---

## 2. What builder-II provides (Workbench-relevant, without being Workbench)

When an operator points builder-II at CORE (or any repo that *contains* Workbench code), builder-II may provide the same governed services it provides for any target:

| Capability class | What builder-II may do | What it must not claim |
| --- | --- | --- |
| Context / repo map | Read-only context packs, target profile defaults | Live Workbench session state |
| Agent profiles | Emit plan/verification *artifacts* for target work | Be the Workbench agent runtime identity |
| Verification | Fixed-argv / profile-bound verification of *target code* under HITL | “Workbench health” as platform identity |
| HITL patch loop | Propose → approve → apply against a worktree (when promoted for that lane) | Silent Workbench deploys or UI mutations |
| WRP / vision RO | Validation-only / read-only lanes (semantic map, agent RO, lifecycle *records*) | Multi-agent Workbench orchestration as product feature |
| Target isolation (V.4) | `core_profile` invariants, path catalogs, semgrep *catalog* on `target=core` only | Generic platform policy rewritten as CORE-only |

**Helping Workbench code** means treating that code as a **software repository under governance**, not becoming the product surface that operators use as Workbench.

---

## 3. What CORE Workbench owns

Workbench (in the CORE product context) owns, among other things:

- Operator-facing UI/UX and cockpit flows  
- Product session identity and presentation  
- Any Workbench-specific runtime that is not builder-II’s governed control plane  
- Product release identity (“this is Workbench”)  

builder-II must not absorb these responsibilities by default, by docs drift, or by informal coupling in code.

---

## 4. Separation of concerns (today)

```text
┌─────────────────────────────────────────────────────────────┐
│  CORE product context                                       │
│   ├── CORE engine / algebra / vault / cognition             │
│   └── CORE Workbench / UI  (product surface)                │
└─────────────────────────────────────────────────────────────┘
              ▲ target repo only (profile = core)
              │ no Workbench coupling
┌─────────────────────────────────────────────────────────────┐
│  builder-II (generic control plane)                         │
│   ├── target profiles: generic | builder | core             │
│   ├── Goose / deepagents / MCP as *adapters* under policy   │
│   ├── artifacts → validate → approve → execute → receipt    │
│   └── governance.core_workbench_coupling = NONE             │
└─────────────────────────────────────────────────────────────┘
```

**Code pins (illustrative, not exhaustive):**

- Artifact governance fields require `core_workbench_coupling: "NONE"`.  
- V.4 `builder_ii/targets/core.py` sets `workbench_coupling: "NONE"`, `platform_identity: false`.  
- Target demos forbid command strings that claim “CORE Workbench” as builder-II identity.  
- ADR-0003 forbids documenting builder-II as CORE Workbench / cockpit.

---

## 5. Future authorized Workbench adapter (design-only)

No Workbench adapter is promoted today. If one is ever proposed, it must follow the same **Third Door** promotion grammar as every other capability. This section is **not** an authorization and **not** an implementation plan.

### 5.1 Minimum boundary requirements

1. **Explicit capability name** — e.g. “Workbench read-only inspection adapter”, never “builder-II is Workbench”.  
2. **Eight promotion gates** — docs, tests, command surface, failure mode, HUMAN approval boundary, output artifact, rollback path, verification path ([CAPABILITY_PROMOTION.md](../CAPABILITY_PROMOTION.md)).  
3. **Target-scoped** — only when `target=core` (or a future named Workbench target profile); never as generic default.  
4. **Coupling flag** — any change to `core_workbench_coupling` requires a HUMAN promotion decision; default remains `NONE`.  
5. **No authority inflation** — adapter outputs are artifacts or read-only views; they are not approval, not deploy authority, not product UI ownership.  
6. **Honest failure modes** — refuse closed when Workbench is absent, when auth is missing, when scope drifts.  
7. **Rollback** — disable flag / delete promotion decision; platform returns to `NONE` coupling.  
8. **Evidence** — readiness + decision records; never self-certify promotion PASS.

### 5.2 Explicit non-goals for any future adapter

- Replacing Workbench UX with builder-II TUI  
- Silent writes into Workbench product state  
- Conflating Goose/deepagents with Workbench identity  
- S3 multi-agent enablement or S4 backend promo as “Workbench features”  
- Cloud invoke as a side-channel to drive UI  

Until a HUMAN decision lands those gates, **there is no Workbench adapter**.

---

## 6. Operator guidance (short)

```bash
# CORE as target (not Workbench identity)
builder-targets show core
builder-targets doctor core

# Context / verification against the CORE repo path (target work)
builder-context pack --target core --no-repomix
```

If a doc, command, or UI string implies builder-II *is* Workbench, treat it as a **truth bug** — fix the claim; do not “implement the identity.”

---

## 7. Related sources of truth

| Doc / surface | Role |
| --- | --- |
| [ADR-0003](../adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md) | Generic platform identity; forbid Workbench conflation |
| [ADR-0001](../adrs/ADR-0001-core-builder-ii-governed-engineering-extension.md) | CORE-born extension, not CORE runtime |
| [TARGETS.md](../TARGETS.md) | Target profiles; CORE is a target |
| [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) | Product positioning |
| [CAPABILITY_PROMOTION.md](../CAPABILITY_PROMOTION.md) | Eight-gate promotion rule |
| V.4 `builder_ii/targets/core.py` | CORE-only catalogs; `workbench_coupling=NONE` |

---

## 8. Honesty locks (V.5)

- This document is **spec_only / hygiene**.  
- It **does not** implement a Workbench adapter.  
- It **does not** flip `core_workbench_coupling`.  
- It **does not** promote S3, S4, cloud invoke, or multi-agent process spawn.  
- It **does** resolve long-standing clarity debt: builder-II helps Workbench *code*; it is not Workbench.

**Cursor after V.5:** documentation boundary is explicit; implementation remains `NONE` coupling until HUMAN authorizes otherwise.
