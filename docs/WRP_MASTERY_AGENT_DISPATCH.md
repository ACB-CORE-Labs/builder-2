# WRP Absolute Mastery — Multi-Agent Dispatch Charter

**Purpose:** Maximum parallel throughput without dual-authority, file contention, or soft stops.  
**Charter:** Absolute mastery plan (P0–P7, S1–S4). Substrate is incomplete; promotion and live lane are mandatory.

This document answers: **who works, on what, when, in parallel with whom, and what Antigravity/Gemini owns.**

---

## 1. Agent roster and excellence bar

| Agent ID | Platform / model | Excellence mandate | Never does |
| --- | --- | --- | --- |
| **M-LEAD** | Grok Build / **Grok-4.5** | Architecture, integration, gateways, authority, promotion flips, live lane, genius-level end-to-end correctness | Self-certify mastery; skip eight gates |
| **M-FAST** | Grok Build / **Composer-2.5-fast** (or subagents: tdd-guide, general-purpose in worktrees) | Pure modules, validators, fixtures, CLI thin wrappers, TDD RED→GREEN at speed | Edit `command_authority.py`, matrix, CAPABILITY_PROMOTION, gateway preflight entrypoints without M-LEAD |
| **M-REVIEW** | Grok Build / code-reviewer + security-reviewer subagents | Pre-Governor Maker self-review (not certification) | Merge authority; override Governor |
| **G-LEAD** | Antigravity / **Gemini-3.1-Pro** | Architectural integrity, dual-correction \(R^*\), promotion gate audits, merge ceremony cert, MSDA/OPA policy review | Implement Maker code as authority; silent enablement |
| **G-FAST** | Antigravity / **Gemini-3.5-Flash** | Scorecards, pytest/CI log digests, acceptance tables, telemetry/state-matrix extraction | Final architectural sign-off alone |
| **HUMAN** | Lead engineer | Approve promotions S1–S3/S4, override ceremony (recorded), start Antigravity at gate points | — |

**Proficiency rule:** Each agent works only in its excellence domain. M-FAST never “almost” edits authority files. G-LEAD never rubber-stamps Maker claims without reading digests and boundaries.

---

## 2. Contended resources (serial ownership)

Only **M-LEAD** may edit (one writer at a time):

| Resource | Why serial |
| --- | --- |
| `builder_ii/command_authority.py` | Tier/promotion truth |
| `builder_ii/platform_completion_audit.py` + truth pins | Matrix claims |
| `docs/CAPABILITY_PROMOTION.md` | Capability power claims |
| `docs/ROADMAP.md` WRP rows | Public completion language |
| Gateway preflight entry hooks (`model_execution_gateway.py`, `tool_invocation_gateway.py` MSDA inject) | Live deny path |
| Promotion decision merges that flip states | Single decision chain |

**Parallel-safe** (M-FAST worktrees, different files):

- `builder_ii/wrp/embedding_backend.py`, `opa_adapter.py`, `graph_runtime.py`, `receipt_ingest.py`, `class_u_harness.py`
- New `tests/test_wrp_*.py` for those modules
- Fixture JSON under `tests/fixtures/wrp/`
- Exchange packaging under `artifacts/wrp_exchange/mastery/P*/` (Maker half only)

**Integration merges:** M-LEAD rebases worktree PRs into the mastery trunk branch in order: pure modules → binding → live lane → promotion docs.

---

## 3. When HUMAN starts Antigravity (Governor)

| Trigger (Maker done) | Start | Model | Prompt focus | Artifact out |
| --- | --- | --- | --- | --- |
| **P0** docs on PR | **Now (#136)** | 3.1-Pro | Authority language vs actual power; no false enablement; mastery not claimed complete | `mastery/P0/governor/wave_mastery_P0_cert.json` |
| After each **P2.x** pure-module package | After Maker exchange | 3.1-Pro | Dual-correct module vs Blueprint operator semantics | `mastery/P2.x/governor/*_cert.json` |
| After **P2.x** test logs | Same window | **3.5-Flash** | Parse pytest; fill acceptance scorecard | `*_scorecard.json` |
| **P1 S1–S3** readiness ready | Before decision merge | **Both** | Eight-gate completeness | `governor.promotion_gate_audit.json` |
| **P3** live lane + gateway preflight PR | Before merge | **3.1-Pro** | Security: MSDA always-before-invoke; no shell; budget | live-lane security cert |
| **P4** \(R^*\) apply path | Before apply-promotion | 3.1-Pro | Dual-correction cannot self-grant authority | R* apply cert |
| **P5** Class U numbers | After harness run | 3.5-Flash + 3.1-Pro | Numbers real; no invented U | U evidence audit |
| **P6** backend defaults | Before S4 | 3.1-Pro | Defaults still M1-safe; opt-in only | backend policy cert |
| **P7** final | End | 3.1-Pro | Architectural sign-off + W5 | final handoff cert |
| **Any authority push** | Pre-push | 3.1-Pro cert + 3.5-Flash log digest | Merge ceremony | `governor.merge_certification.json` |

**Default rule:** Maker ships package → **you start Antigravity** → Governor cert → only then merge/push authority. Maker does not self-certify.

**Governor can run concurrently with Maker** on *already packaged* waves while Maker starts the *next non-contended* package (see §4).

---

## 4. Parallelism map (maximum safe concurrency)

### 4.1 Global pipeline (phases)

```text
                    ┌──────────────┐
                    │ P0 docs (#136)│──► G-LEAD cert ──► merge
                    └──────┬───────┘
                           │ (Maker may start below without waiting for merge
                           │  if branched from same base; rebase after merge)
         ┌─────────────────┼─────────────────┬──────────────────┐
         ▼                 ▼                 ▼                  ▼
    P2.0 embed        P2.1 topology     P2.3 OPA adapter   P2.6 graph runtime
    P2.4 receipt      P2.5 factory      P2.7 Class U       P2.8 replay repo
    (M-FAST × N worktrees — pure files only)
         │                 │                 │                  │
         └─────────────────┴────────┬────────┴──────────────────┘
                                    ▼
                          M-LEAD integration branch
                          P2.2 fleet binding + S1 bind design
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              P1 S1 decision   G-LEAD gate audit   G-FAST tables
                    │
                    ▼
              P3 live lane (M-LEAD) + M-FAST receipts/CLI
                    │
              G-LEAD security cert
                    │
              P1 S2 decision (HUMAN + G-LEAD)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    P4 R* apply           P6 backends (M-FAST adapters)
         │                     │
         └──────────┬──────────┘
                    ▼
              P5 Class U + S3 (M-LEAD + G-LEAD)
                    ▼
              P7 ceremony + W5 final (G-LEAD sign-off)
```

### 4.2 What runs **in parallel right now** (post-P0 package)

| Lane | Owner | Work | Depends on | Blocks |
| --- | --- | --- | --- | --- |
| **G0** | HUMAN → **G-LEAD** | Cert PR #136 / P0 exchange | P0 package exists | P0 merge hygiene |
| **G0b** | HUMAN → **G-FAST** | Optional scorecard of gap matrix OPEN count | P0 package | Nothing |
| **A** | **M-FAST** | `embedding_backend.py` + tests (HashingEmbedder, Protocol, kNN hooks) | None | P2.0 integration |
| **B** | **M-FAST** | `graph_runtime.py` + pattern executors + tests | None | P3 |
| **C** | **M-FAST** | `opa_adapter.py` export + pure parity fixtures | None | P2.3 gateway wire |
| **D** | **M-FAST** | `receipt_ingest.py` + tests from fake receipts | None | P4 |
| **E** | **M-LEAD** | S1 binding design: `model_routing_recommendation` + assignment dry-run **require** WRP digest fields | Read-only until A–D land | P1 S1 |
| **F** | **M-REVIEW** | Review each M-FAST PR before Governor package | A–D PRs | Governor package quality |

**Do not parallelize:** two agents writing gateway preflight or `command_authority.py`.

### 4.3 Per-phase parallel windows

| Phase | Parallel Maker | Serial Maker | Concurrent Governor |
| --- | --- | --- | --- |
| **P0** | — | Docs (done) | Cert now |
| **P1 S1** | Evidence packaging tests (M-FAST) | Decision + matrix + bind (M-LEAD) | Gate audit while evidence draft exists |
| **P2** | P2.0, P2.1, P2.3 export, P2.4, P2.5 plan states, P2.6, P2.7, P2.8 (all M-FAST worktrees) | P2.2 fleet_binding shape + integration (M-LEAD) | Cert each completed slice; Flash scorecards |
| **P3** | Live receipts, CLI `run-approved`, scenario tests (M-FAST) | Gateway MSDA preflight, live_lane core (M-LEAD) | Security cert when package ready; Flash on scenario logs |
| **P4** | Epoch/real-receipt harness (M-FAST) | Apply-promotion path + store versioning (M-LEAD) | Dual-correction cert |
| **P5** | Class U suite runners (M-FAST) | S3 decision + scope profile (M-LEAD) | U audit + enablement cert |
| **P6** | Embedder opt-in, LangGraph adapter, vLLM interface stubs (M-FAST ×3) | Default-safety policy docs (M-LEAD) | Backend policy cert |
| **P7** | Runbook, PR templates, demo script (M-FAST) | Final matrix honesty (M-LEAD) | Final architectural sign-off |

### 4.4 Antigravity concurrency with Maker

| Situation | Allowed? |
| --- | --- |
| G-LEAD reviews P0 while M-FAST builds embedding backend | **Yes** |
| G-LEAD reviews P2.0 while M-FAST builds P2.6 | **Yes** |
| G-LEAD and M-LEAD both edit CAPABILITY_PROMOTION | **No** — Governor writes only exchange certs, not repo authority files |
| G-FAST parses CI while M-LEAD implements live lane | **Yes** |
| Two Governors certifying same wave without coordination | **No** — one cert file owner per wave |
| Governor implements Python modules in main | **No** — Governor validates; Maker implements (unless HUMAN assigns exception recorded) |

Governor **writes only:**

```text
artifacts/wrp_exchange/mastery/<phase>/governor/**
```

(and optionally review markdown under that tree). Code/docs merges stay Maker + HUMAN.

---

## 5. Worktree / PR topology (efficiency)

```text
main
 └── feat/wrp-absolute-mastery          # integration trunk (M-LEAD)
       ├── feat/wrp-m-p2-embedding      # M-FAST worktree
       ├── feat/wrp-m-p2-graph-runtime  # M-FAST worktree
       ├── feat/wrp-m-p2-opa            # M-FAST worktree
       ├── feat/wrp-m-p2-receipt-ingest # M-FAST worktree
       ├── feat/wrp-m-p1-s1-bind        # M-LEAD (after pure modules green)
       ├── feat/wrp-m-p3-live-lane      # M-LEAD
       └── feat/wrp-m-p6-*              # M-FAST backends
```

Current branch `feat/wrp-absolute-mastery-p0` merges first → rename/continue as integration trunk or branch `feat/wrp-absolute-mastery` from main after #136.

**Merge order into trunk:** pure modules → S1 bind → live lane → R* apply → Class U/S3 → backends polish → P7.

---

## 6. Genius-level implementation standards (all Maker agents)

1. **Read call sites** before inventing APIs; extend existing digest/governance envelopes.  
2. **TDD:** failing test first for every new behavior; ≥80% on new modules.  
3. **Fail closed:** missing approval, MSDA deny, budget overrun → structured error + receipt, no partial authority.  
4. **Immutability:** new artifacts via `base_envelope` + digests; no silent mutate of frozen experience.  
5. **Mechanical sympathy:** default path M1-safe; heavy backends Protocol + explicit opt-in.  
6. **End-to-end:** each phase has a scenario test that crosses ≥2 modules; P3+ crosses gateways.  
7. **Name the claim:** every PR body cites gap-matrix row IDs closed.  
8. **No soft stop:** PR is not “done” if it only documents the hard path.

---

## 7. End-to-end coverage matrix (who proves what)

| Mastery exit criterion | Maker proof | Governor proof | Parallelizable? |
| --- | --- | --- | --- |
| W0 95% tier | pytest + score-classifier | Flash scorecard | Score while Maker adds embedder |
| W1 handoff | topology + live handoff scenario | Topology audit | Flash metrics // Maker patterns |
| W2 budget | stress tests + fleet_binding | Policy review high-cost models | Yes for stress vs review |
| W3 100% gate | MSDA + gateway preflight tests | Security cert | Cert after package only |
| W4 30% epochs | synthetic + real receipt series | Dual-correction cert | Harness // cert prep |
| W5 reconstruct | digest + tree_hash | Reconstructive hash cert | Yes |
| Class U numbers | harness artifacts | U audit | Measure // review |
| S1–S3 enabled power | decision + matrix + tests | promotion_gate_audit | Evidence draft // audit draft |
| Dual-platform ceremony | exchange packages | merge_certification | Always concurrent with next Maker lane |

---

## 8. Prompt packs (copy for Antigravity)

### 8.1 P0 / PR #136 (run now)

```text
You are Governor (Gemini-3.1-Pro) for builder-II WRP absolute mastery P0.
Read: artifacts/wrp_exchange/mastery/P0/, docs/WRP_MASTERY_GAP_MATRIX.md,
docs/WRP_CONTROL_PLANE.md, docs/WRP_ACCEPTANCE.md, ADR-0007, CAPABILITY_PROMOTION WRP row.
Verify: (1) no claim that live lane or absolute mastery is complete;
(2) staged S1–S3 described as future decisions; (3) current power recommendation_only;
(4) soft-stop-at-substrate rejected. Emit governor/wave_mastery_P0_cert.json
{status: PASS|FAIL, findings[], authority_language_ok: bool, digest_notes}.
```

### 8.2 Promotion gate (S1–S3)

```text
You are Governor promotion auditor. Verify eight gates for target_state=<S1|S2|S3>
against readiness + decision draft + tests/docs/CLI. Fail if any gate missing or
if CAPABILITY_PROMOTION would claim more power than code. Emit
governor.promotion_gate_audit.json.
```

### 8.3 Live lane security (P3)

```text
You are Governor security auditor for builder-wrp run-approved.
Trace: approval required → MSDA preflight → invoke → receipt.
Refuse PASS if any path skips MSDA, allows shell=True, or mutates policy without promotion.
```

### 8.4 Flash scorecard

```text
You are Governor Flash. Parse the attached pytest/CI receipt. Fill Master-Plan W0–W5
and gap-matrix rows with PASS/FAIL/PARTIAL and command digests. Emit scorecard JSON only.
```

---

## 9. Immediate dispatch (execute this sprint)

| Order | Action | Agent | Parallel with |
| --- | --- | --- | --- |
| 1 | Cert P0 (#136) | **HUMAN starts G-LEAD** (+ optional G-FAST) | 2–5 |
| 2 | Embedding backend TDD | **M-FAST** | 1,3,4,5 |
| 3 | Graph runtime TDD | **M-FAST** | 1,2,4,5 |
| 4 | OPA adapter export TDD | **M-FAST** | 1,2,3,5 |
| 5 | Receipt ingest TDD | **M-FAST** | 1,2,3,4 |
| 6 | S1 binding design + tests plan | **M-LEAD** | 1–5 (design only until modules land) |
| 7 | Maker review of 2–5 | **M-REVIEW** | after each lands |
| 8 | Governor cert packages for 2–5 | **G-LEAD / G-FAST** | while M-LEAD does S1 impl |
| 9 | S1 promotion decision PR | **M-LEAD + HUMAN + G-LEAD** | after bind + readiness |

---

## 10. Anti-patterns (efficiency killers)

- Waiting for Governor before starting **non-contended** next modules  
- Starting live lane before MSDA preflight design  
- Parallel edits to `command_authority.py`  
- Governor rewriting product code without Maker  
- Declaring phase done when only docs moved  
- Serializing all M-FAST work “to be safe” when files do not overlap  

---

## 11. Success of this dispatch model

Dispatch is successful when:

1. ≥3 pure-module lanes run concurrently during P2  
2. Governor is busy whenever a package exists (no idle cert queue >1 packaged wave)  
3. Wall-clock to S2 live lane is dominated by integration + cert, not by idle serial pure modules  
4. Zero authority-file merge conflicts from parallel agents  
5. Absolute mastery checklist still has **zero intentional skips**
