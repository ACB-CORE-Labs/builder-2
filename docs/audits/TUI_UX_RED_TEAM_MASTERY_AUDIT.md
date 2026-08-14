# TUI / UX Red-Team Mastery Audit

**Status:** RECORDED_ONLY audit (not a promotion grant; not a claim that findings are fixed).  
**Date:** 2026-07-19  
**Target:** `core-labs/builder-II` @ `main` (`0da735f` tip at audit start)  
**Method:** Four parallel deep agents (surface map · interaction · governance honesty · product mastery) + direct source read of `builder_ii/tui/`, inspection `*_tui.py`, tests, and docs.  
**Doctrine:** planned ≠ executed ≠ verified ≠ promoted · artifact ≠ authority · honesty pins ≠ non-implementation.

---

## 0. One-paragraph verdict

STRATUM is an unusually mature **governance instrument panel** (compose ≠ execute, no digest fabrication, Third Door unassessed≠locked, Goose hand-off via fixed governed argv). It is **not** utmost operator-product mastery. Last-mile substrate (price book, budget, seam invoke, measured tokens, run-manifest replay, OTel, subagent loop) is largely **DONE in code and invisible in the console**. HITL “Approve/Reject” are footer theater over incomplete CLI compose. Four center modes are dead furniture. Status chrome greenglows presence as “verified” / “ALL GATES CLEAR.” Dual “TUI” naming (Textual STRATUM vs Rich inspect CLIs) fractures the mental model. **Overall operator UX mastery ≈ 2.3 / 5** (honesty high; day-to-day work loop scaffold).

---

## 1. What “TUI” actually is (do not collapse)

| Layer | Tech | Interactive? | Primary path |
| --- | --- | --- | --- |
| **STRATUM** (`StratumApp`) | Textual | Yes | `builder stratum --experimental` / `builder-stratum` / `builder-platform tui` |
| **Deepagents Forge** | Textual | Yes | `builder-deepagents forge` |
| **`builder tui *`** | Rich panels | No | One-shot stdout |
| **Inspection surface** (`hitl_tui`, `model_tui`, …) | ANSI / Typer | No | CI-friendly inspect |

Docs that call all of this “the TUI” without distinction train false confidence.

---

## 2. Mastery scorecard

| Subsystem | Depth (1–5) | Note |
| --- | ---: | --- |
| Truth / honesty pins in UI | **5** | Digest absence, compose-not-execute, door taxonomy |
| Governance vocabulary on screen | **4** | Epistemic matrix, capability rail, palette tiers |
| CLI inspection surface | **4** | Schema-backed, exit-code usable |
| STRATUM layout / theming | **3** | Three-pane + Cosmic Void |
| Prepare→plan→approve→execute→verify IA | **2** | Spine = artifact kinds, not operator verbs |
| HITL ceremony UX | **2** | Incomplete compose; D unimplemented |
| Cross-surface consistency | **2** | Dual TUI meaning; palette drift |
| Empty / error / recovery | **2** | Thin recovery narrative |
| Last-mile cost / budget / seam | **1** | Zero TUI bindings |
| Runtime ledger / replay product | **1** | EVENTS rail ≠ event_ledger / run_manifest |
| Mechanical Sympathy HUD | **1** | RAM once; MLX t/s never wired |
| **Overall operator UX** | **~2.3** | Substrate mastery ≠ console mastery |

---

## 3. CRITICAL findings

### C1 — Command palette is not keyboard-operable

- **Where:** `builder_ii/tui/widgets/palette.py` (Escape only; select via `on_click` only).
- **Why it fails mastery:** Primary discovery surface for a keyboard console; mouse-only select on a registry of hundreds of commands.
- **Bar:** j/k or arrows + Enter; Pilot test without click.

### C2 — HITL A/R compose incomplete / kind-wrong

- **Where:** `builder_ii/tui/app.py` ~847–877.
- **Approve** composes bare `uv run builder-hitl approve-patch` without `--proposal` / `--output` even when proposal path is bound.
- **Reject** composes `builder-hitl rejection-record` (promotion-bridge ceremony), not a patch reject.
- **Worse:** scenario tests **pin the incomplete strings as success** (`tests/scenarios/test_hitl_orchestration.py`).
- **Bar:** Bound, runnable compose or refuse; tests assert required flags when path known.

### C3 — First-session spine path is structurally broken

- Guide / prepare uses `-o .builder/session` (or similar).
- Spine loads **only** top-level `*.json` under `.builder/artifacts` (`projections/chain.py` glob).
- Operator can “complete prepare” and still see nine pending stages forever.
- **Bar:** One root for prepare + spine, or multi-root scan; scenario: prepare → spine lights.

### C4 — Last-mile muscle has zero console surface

| Capability (code DONE) | TUI |
| --- | --- |
| `price_book` / measured tokens / USD | Absent |
| `model_budget` deny/debit | Absent |
| `invoke_local` / `invoke_cloud` | Absent |
| `run_manifest` + replay harness | Absent |
| `otel_ledger_export` / runtime event spine | EVENTS rail is a different thin tail |
| Subagent loop / earned `spawn_executed` | U composes assign only |

**Impact:** “Work as usual” for last-mile is CLI archaeology. Honesty of STRATUM does not excuse product invisibility of the economic/runtime spine.

---

## 4. HIGH findings

| ID | Finding | Evidence | Severity |
| --- | --- | --- | --- |
| H1 | Footer **Approve/Reject** harvest authority language for compose-only acts | `app.py` bindings vs action bodies | HIGH |
| H2 | Spine status **`verified`** = presence, not chain proof | `chain.py` `_stage_status` comment + return | HIGH |
| H3 | Epistemic matrix greening from **kind-name heuristics**, digests always `—` | `chain.py` `epistemic_from_chain` | HIGH |
| H4 | **ALL GATES CLEAR** = no pending HITL JSON, not cleared governance | `signals.py` / `scan_pending_hitl` | HIGH |
| H5 | Four dead modes: PREPARE, POSTFLIGHT, PROMOTION, GOOSE_LIVE | Renderers exist; never assigned | HIGH |
| H6 | Verification lane / MCP / WRP / ledger-index have no STRATUM instruments | Coverage gap table (agent 1) | HIGH |
| H7 | Guide says G never mints manifests; code can auto-prep under confirm | `stratum_guide.py` vs `app.py` G path | HIGH |
| H8 | `builder-platform tui` / `python -m builder_ii.tui` skip experimental gate | Launch path inconsistency | HIGH |
| H9 | Write pin tests only scan `builder_ii/tui/**`; G writes via `stratum_prepare` | `test_stratum_tui.py` scope | HIGH |
| H10 | `promote_tui` readiness can exit 0 on **empty gates** | `promote_tui.py` `_render_readiness` | HIGH |
| H11 | GETTING_STARTED key map drift (e.g. Orch as W vs code **Y**) | Docs vs `app.py` BINDINGS | MED–HIGH |

---

## 5. Dead / stub furniture (honesty debt)

| Item | Location | Note |
| --- | --- | --- |
| HITL diff viewer | `STRATUM_UNIMPLEMENTED_SURFACES`, **D** | Only *named* mockup; still in footer |
| `RejectScreen` | `cli_passthrough.py` | Defined, never pushed |
| `StratumMode.PREPARE/POSTFLIGHT/PROMOTION/GOOSE_LIVE` | `stratum.py` | Renderers without entry |
| `action_cycle_focus` | `app.py` | Documented dead (TAB shadowed); help still claims three-pane cycle |
| Capability rail | `signals.py` | Always DISABLED (honest non-exec; looks like live policy forever) |
| MechanicalSympathy MLX t/s | `masterpiece.py` | Never updated → permanent NO MODEL / decorative |
| CodeVault plugin boundary | `builder-code-vault` | Opaque optional-import seam; fail-closed when absent |
| ForgeApp | semantic driver | Not registered (only StratumApp) |

---

## 6. Governance honesty (conditional pass)

| Criterion | Result |
| --- | --- |
| Keypress grants approval/authority | **PASS** (compose refusals; measured) |
| Labels never inflate | **FAIL** (Approve, verified, ALL GATES CLEAR, epistemic greening) |
| Platform matrix (C) decorative? | **PASS (data)** — uses `capability_rows()` |
| Docs-truth covers TUI labels? | **FAIL** — audit-docs is docs-only |
| Secrets in model panel | **PASS** (presence-only) |
| G path write+subprocess | **Documented exception** outside narrow write pin |

**Verdict:** Conditional pass as *instrument + compose plane*; fail if scored as *authority-enforcing control plane*.

---

## 7. CLI vs TUI coverage (extract)

| Capability | CLI | STRATUM / inspect | Severity |
| --- | --- | --- | --- |
| HITL patch ceremony | Full | Compose-only + thin inspect; D stub | HIGH |
| Verification plan→run | Full | Spine stage only if artifact present | CRITICAL |
| Last-mile budget/cost/seam | Full | **None** | CRITICAL |
| WRP control plane | Full | **None** | CRITICAL |
| MCP inventory | Full | **None** | CRITICAL |
| Promotion readiness | Full | Dead PROMOTION mode; `builder promote *` inspect OK | HIGH |
| Postflight | Full | Dead POSTFLIGHT mode; inspect OK | HIGH |
| Goose readonly | Full | **G** hand-off live | Covered |
| Models registry | Full | O projection + model_tui | MED |

---

## 8. Ideal mastery bar (end-state narrative)

Single console mental model; center panel is a **verb stage machine**, not a mode soup:

```
PREPARE → PLAN → APPROVE → EXECUTE → VERIFY → PROMOTE
```

Last-mile always-on HUD:

| Strip | Content |
| --- | --- |
| Budget | remaining tokens/$; last debit version |
| Seam | invoke mode; local vs cloud; receipt path |
| Ledger | runtime event chain tail; open → replay filter |
| Cost | measured tokens + USD vs estimate honesty |

HITL **A/R** only when compose is fully bound (paths + digests) or key is hidden. Spine `verified` → `present` / `on_disk`. **ALL GATES CLEAR** → **NO PENDING HITL**. Every `StratumMode` either has a key path **or** is listed unimplemented (symmetric truth).

---

## 9. Ranked remediation (leverage × integrity)

1. **HITL compose completeness** (flags + kind) + stop pinning incomplete strings  
2. **Spine ↔ prepare root alignment** (first-session golden path)  
3. **Last-mile HUD** (budget/cost/seam/ledger) on Approve/Execute stages  
4. **Semantic greening renames** (verified / ALL GATES CLEAR / epistemic completed)  
5. **Wire or delete dead modes** (POSTFLIGHT, PROMOTION, PREPARE, GOOSE_LIVE)  
6. **Keyboard palette**  
7. **Verification instrument** (plan/approval/receipt compose)  
8. **Align experimental launch gates** + document G write exception in authority pin  
9. **Unify “TUI” vocabulary** in docs (STRATUM vs inspect)  
10. **Forge + palette paths in semantic driver**

---

## 10. What is already excellent (do not regress)

- No fabricated chain digests; tests ban digest-shaped literals under `tui/`  
- HITL does not harvest approval digests from the display surface  
- Goose hand-off uses fixed argv to `builder-goose start-readonly`, not raw goose builtins  
- Third Door unassessed vs locked taxonomy  
- `run_tui` propagates Textual `return_code` (crash ≠ exit 0)  
- Semantic driver + no-TTY-scraping ban  
- Inspection CLIs schema-backed and CI-exit usable  

---

## 11. Official-completion implication

**Backend last-mile substrate** and **TUI/UX last-mile product** are not the same completion claim.

| Claim | Status after this audit |
| --- | --- |
| Governed execution seam, cost, ledger, cloud adapters, subagent loop (code) | Shipped (prior PRs) |
| Operator “work as usual” in the console for that muscle | **Not met** |
| TUI honesty against authority laundering | **Strong** |
| TUI thorough deep articulate mastery of all capabilities | **Failed red-team bar** |

Recommend: treat this audit as **blocking for “official TUI/UX complete”** until at least C1–C4 and H1–H5 are addressed (or explicitly accepted as out-of-scope product decisions with matching label demotion). Backend last-mile may remain “substrate complete” if claims stay CLI-first and the console stops greenglowing systems it does not drive.

---

## 12. Agent roster (evidence)

| Agent | Focus | Outcome |
| --- | --- | --- |
| Explore 1 | Full surface map + CLI vs TUI gaps | Dead modes, launch gates, coverage table |
| Explore 2 | Interaction quality | C1–C3, palette, HITL compose, guide/G mismatch |
| Explore 3 | Governance honesty | Label inflation, conditional pass |
| Explore 4 | Product mastery | Scorecard 2.3/5, ideal end-state narrative |

*Soli Deo gloria.*
