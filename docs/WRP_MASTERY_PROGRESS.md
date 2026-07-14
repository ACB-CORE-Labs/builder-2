# WRP Absolute Mastery — Progress Marker

**Status:** RECORDED_ONLY progress ledger (not a promotion grant; not S3 enablement).  
**As of:** main tip includes **#146** (S3 readiness + G-LEAD) · HUMAN S3 decision **blocked** · **#145** progress marker · **#144** P5 · S1/S2 approved.  
**Sources of truth:** this file + [`WRP_MASTERY_GAP_MATRIX.md`](WRP_MASTERY_GAP_MATRIX.md) + [`WRP_MASTERY_AGENT_DISPATCH.md`](WRP_MASTERY_AGENT_DISPATCH.md) + [`ROADMAP.md`](ROADMAP.md) WRP phase + exchange under `artifacts/wrp_exchange/mastery/`.

> **Do not inflate.** Planned ≠ executed ≠ verified ≠ promoted. G-LEAD cert ≠ S3 enabled. Readiness `ready=true` ≠ decision approved. HUMAN **blocked** ≠ reopen without new evidence.

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
| S3 scoped `enabled` | S3 | **DECIDED blocked (HUMAN)** | Readiness G-LEAD PASS (#146); `wrp_s3_decision.json` **blocked** by HUMAN (H7 + blockers) — **not** enabled |
| P6 backends | P6 | **OPEN / partial substrate** | **Next focus** after S3 block; hash embed + OPA export landed; heavy tracks open |
| P7 ceremony + W5 | P7 | **PARTIAL** | Ceremony used on authority PRs; W5 commit/tree_hash still OPEN |

**Cursor (now):** S3 **HUMAN-decided blocked**. Enablement off. Next high leverage: **P6** (opt-in backends, M1-safe) and/or **P7/W5**; re-open S3 only with stronger U evidence + enablement design.

---

## 2. Promotion power (honest)

| Stage | Target | State |
| --- | --- | --- |
| S1 | Bound recommendations (flagged) | **Approved** — default still advisory unless bind flags set |
| S2 | HITL live lane | **Approved** v1 + **v2 gateway code** on main — still `hitl_runtime_candidate` |
| S3 | Scoped multi-agent `enabled` | **HUMAN blocked** — readiness ready; Class U micro-only (H7); no `enabled` runtime |
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
| #145 | Progress marker (DONE/OPEN/H1–H12) | merged (`ff0e5df`) |
| #146 | S3 readiness draft + G-LEAD certs | merged; enablement none |
| (open) | S3 HUMAN decision blocked | `wrp_s3_decision.json` decided_by=HUMAN, decision=blocked |

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
| H7 | **Class U numbers are local/micro** | Medium | **Reviewed (S3 readiness draft):** exchange sample ~`record_ms≈0.97`, `peak_rss_mb≈49`; host reconfirm ~`0.76` / `~42` RSS; structural match; `s3_enabled=false`. Proves harness + fail-closed path, **not** production multi-agent utility. **Outcome in readiness notes + decision=blocked:** U suite alone is **insufficient** to approve target_state=`enabled`. Remains open as product risk until HUMAN decides or stronger U evidence lands. |
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

1. **P6** — opt-in backends (embed/OPA/vLLM interface) with M1-safe defaults; do not soft-enable multi-agent.  
2. **P7/W5** — repo-state reconstructive match + ceremony templates / H4 P4 cert hygiene.  
3. **Re-open S3 only when:** stronger Class U (or production-shaped) evidence + scoped enablement design + new readiness/decision + G-LEAD (do not reuse #146 decision).

---

## 7. How to update this marker

When a mastery PR merges:

1. Move the phase row in §1 to DONE / DECIDED.  
2. Add PR to §4.  
3. Add any new hiccup to §5 (or close resolved ones with date).  
4. Align gap matrix rows in the same change.  
5. Never check mastery checklist boxes from docs alone — require code + tests (+ G-LEAD on authority).
