# WRP Absolute Mastery — Progress Marker

**Status:** RECORDED_ONLY progress ledger (not a promotion grant; not S3 enablement).  
**As of:** main tip includes **#144** (P5 Class U) · **#143** (S2 v2 gateways) · **#142** (P4 R\* apply) · S1/S2 decisions.  
**Sources of truth:** this file + [`WRP_MASTERY_GAP_MATRIX.md`](WRP_MASTERY_GAP_MATRIX.md) + [`WRP_MASTERY_AGENT_DISPATCH.md`](WRP_MASTERY_AGENT_DISPATCH.md) + [`ROADMAP.md`](ROADMAP.md) WRP phase + exchange under `artifacts/wrp_exchange/mastery/`.

> **Do not inflate.** Planned ≠ executed ≠ verified ≠ promoted. G-LEAD cert ≠ S3 enabled.

---

## 1. Where we are on the plan pipeline

Canonical merge order (dispatch §5 / absolute mastery):

```text
pure modules → S1 bind → live lane (S2) → R* apply (P4) → Class U (P5) / S3 → backends (P6) → ceremony + W5 (P7)
```

| Phase | Plan ID | Status on main | Evidence |
| --- | --- | --- | --- |
| P0 constitutional docs | P0 | **DONE** | #136 lineage; `mastery/P0/governor/` certs |
| P2 pure modules | P2.x | **DONE** | embed, graph, opa, receipt ingest modules + tests |
| P2 wires | P2 remainder | **DONE** | #139 fleet_binding, MSDA preflight env, embed classifier |
| S1 bound recommendations | S1 | **DECIDED approved** | `planning/evidence/wrp_s1_{readiness,decision}.json`; bind via flags only |
| S2 HITL live lane v1 | S2 / P3 | **DECIDED approved** | `planning/evidence/wrp_s2_{readiness,decision}.json`; #140/#141; plan-live → run-approved |
| S2 v2 gateway nodes | S2 v2 | **DONE (HITL candidate)** | #143; G-LEAD PASS; model/tool gateway record+stub_tool |
| P4 R\* apply | P4 | **DONE (HITL φ-policy)** | #142; versioned `phi_policy`; no DEFAULT_PHI mutate |
| P5 Class U measured | P5 | **DONE (validation_only)** | #144; G-LEAD PASS; `builder-wrp benchmark --class u` |
| S3 scoped `enabled` | S3 | **NOT STARTED** | Needs HUMAN eight-gate + numbers review; Class U data now available |
| P6 backends | P6 | **OPEN / partial substrate** | Hash embed + OPA export landed; ModernBERT/vLLM/LangGraph open |
| P7 ceremony + W5 | P7 | **PARTIAL** | Ceremony used on authority PRs; W5 commit/tree_hash still OPEN |

**Cursor (now):** Standing **between P5 complete and S3-or-P6/P7 fork**. Next high-leverage choice is data-driven S3 discussion **or** P6/P7 polish — not more unmeasured live expansion.

---

## 2. Promotion power (honest)

| Stage | Target | State |
| --- | --- | --- |
| S1 | Bound recommendations (flagged) | **Approved** — default still advisory unless bind flags set |
| S2 | HITL live lane | **Approved** v1 + **v2 gateway code** on main — still `hitl_runtime_candidate` |
| S3 | Scoped multi-agent `enabled` | **OPEN** — Class U does **not** promote |
| S4 | Backend promotions | **OPEN** |

Live path remains **HITL candidate**, not global enabled multi-agent.

---

## 3. Mastery checklist (marker)

```text
[ ] Master-Plan W0–W5 green with Maker + Governor evidence  ← PARTIAL: substrate+HITL strong; W5 repo-state OPEN
[ ] Live lane promoted and used under MSDA + budgets         ← PARTIAL: S2 decided HITL; not S3 "promoted enabled"
[x] R deterministic; R* applied through promotion; adaptivity on receipt epochs
[x] Proof R, D, U evidenced (U with numbers via class_u_harness #144)
[~] Dual-platform ceremony for authority changes            ← PARTIAL: used for S2/S2-v2/P5; uneven on P4 exchange certs
[~] CAPABILITY_PROMOTION / matrix / command_authority match  ← PARTIAL: WRP rows updated; continuous drift risk
[ ] Heavy backends opt-in with tests; defaults M1-safe       ← PARTIAL: hash embed/OPA export; heavy tracks OPEN
[ ] Gap matrix zero OPEN rows                                ← FAIL until S3/P6/P7/W5 closed or deliberately deferred
```

`[x]` = closed with code+tests+docs (and G-LEAD where required).  
`[~]` = substantially practiced but not airtight.  
`[ ]` = still open for absolute mastery.

---

## 4. Merged PR map (this mastery arc)

| PR | Topic | Main |
| --- | --- | --- |
| #136+ | P0 / early mastery docs | base |
| #138 | S1 bind | merged |
| #139 | P2 wires | merged |
| #140/#141 | S2 v1 live + hardening + decision | merged |
| #142 | P4 R\* apply | merged (`953115f` lineage) |
| #143 | S2 v2 gateways | merged (`d0aad9e`) |
| #144 | P5 Class U | merged (`7401b1e`) |

Exchange packages: `artifacts/wrp_exchange/mastery/{P0,P2-pure,P2-wires,S1,S2,S2-v2,P4,P5}/`.

---

## 5. Hiccups / concerns / review backlog

These are **not** silent failures of the platform grammar; they are residual risks and process debt. Ranked for review.

### 5.1 Process & multi-agent

| ID | Concern | Severity | Notes / mitigation |
| --- | --- | --- | --- |
| H1 | **Parallel agents on same task** | High (process) | A subagent re-scaffolded S2 v1 on stale `feat/wrp-mastery-s2-live-lane` while claiming S2 v2. Stopped; no main damage. **Review:** keep one writer per contended surface; always branch from current main. |
| H2 | **`tea pr merge` 405** | Medium (ops) | Often fails; merges done via `git merge --no-ff` + `git push origin main`. **Review:** document Forgejo merge path; close PRs explicitly when needed. |
| H3 | **G-LEAD tip lag** | Medium | G-LEAD sometimes audited mid-PR tips (pre-scorecard / pre-mypy fix). Certs still PASS after tip moved; re-run targeted pytest at cert tip when tip advances. |
| H4 | **P4 exchange governor cert thin** | Medium | `mastery/P4/governor/` on main lacks a full wave cert file (unlike S2-v2/P5). Code is on main via #142. **Review:** optional retro G-LEAD cert for archival consistency, or accept Maker+HUMAN merge as recorded. |
| H5 | **Dispatch doc stale “now” sections** | Low | §4.2 still describes post-P0 parallel windows. Pipeline diagram still shows P5+S3 coupled. **This progress file is the living cursor;** dispatch historical sections kept for intent. |

### 5.2 Power honesty & product

| ID | Concern | Severity | Notes / mitigation |
| --- | --- | --- | --- |
| H6 | **S2 v2 is not cloud invoke** | High (honesty) | Default `gateway_mode=record` = synthetic digests + MSDA. No provider network. **Do not market as “model gateway live.”** Cloud remains explicit future gate. |
| H7 | **Class U numbers are local/micro** | Medium | Sample ~`record_ms≈1`, `peak_rss_mb≈49`. Proves harness + fail-closed path, **not** production multi-agent utility. **Review before S3:** whether U thresholds and scenario suite are enough for an enablement decision. |
| H8 | **S1 bind still flag-gated** | Medium | Approved decision does not default-bind routing; `require_wrp_binding` / env / dry-run flags required. Intentional; easy to misread as “S1 fully on.” |
| H9 | **MSDA preflight default off outside live lane** | Medium | Live lane forces MSDA; model/tool gateways use env `BUILDER_II_WRP_MSDA_PREFLIGHT`. Real invoke paths can still skip preflight if env unset. |
| H10 | **Fleet binding vs session plan** | Low–Med | `fleet_binding` on allocation + recommendations; not fully driving live session/model authority. Gap row still PARTIAL. |
| H11 | **Adaptivity axis incomplete** | Low | P4 epoch/receipt path exists; Class U report leaves adaptivity null. Full perf dashboards OPEN. |
| H12 | **Gap row drift** | Low | Some rows still say “no gateway” / “live lane OPEN” for fleet — corrected in gap matrix when this marker lands. Continuous `audit-docs` helps. |

### 5.3 What does **not** need panic review

- Dual-platform G-LEAD/G-FAST ceremony for S2, S2-v2, P5 is working as designed.  
- Fail-closed patterns (digest approval, shell deny, v1 refuse gateway flags) tested.  
- DEFAULT_PHI immutability preserved under P4/P5.  
- Mechanical sympathy defaults (M1-safe record/stub) held.

---

## 6. Recommended next steps (plan-ordered)

1. **Human read of Class U sample** — `artifacts/wrp_exchange/mastery/P5/governor/sample_class_u_report.json` and whether suite is sufficient for S3 discussion.  
2. **Either:**
   - **S3** — eight-gate readiness + G-LEAD + HUMAN decision (promotion boundary; do not soft-enable), **or**
   - **P6** — opt-in backends (embed/OPA/vLLM interface) with M1-safe defaults, **or**
   - **P7/W5** — repo-state reconstructive match + ceremony templates.  
3. **Hygiene (optional, high leverage/low risk):** retro P4 governor cert; update dispatch §4 “now” table; tighten gap rows if any lag.

---

## 7. How to update this marker

When a mastery PR merges:

1. Move the phase row in §1 to DONE / DECIDED.  
2. Add PR to §4.  
3. Add any new hiccup to §5 (or close resolved ones with date).  
4. Align gap matrix rows in the same change.  
5. Never check mastery checklist boxes from docs alone — require code + tests (+ G-LEAD on authority).
