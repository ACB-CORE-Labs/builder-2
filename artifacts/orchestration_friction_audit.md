# Orchestration & HITL Friction Audit

**Surface:** `StratumApp` (`builder-platform tui`) · **Method:** Semantic Pilot, driven in-process
**Date:** 2026-07-17 · **Lanes:** `tests/scenarios/test_hitl_orchestration.py` (11, mutation-proved 4/4)

> **Status — updated 2026-07-17, findings not rewritten.** This is the record of what was measured
> on the date above; the findings below are left as they were found. Two have since been acted on,
> and the rest still stand:
>
> * **§5.2 (Third Door reads VAULT LOCKED by default) — CLOSED.** `render()` collapsed every
>   non-`True` slot into a refusal, so an unassessed door was indistinguishable from a refused one.
>   `third_door_state()` now derives four states and an unassessed door reads `VAULT UNASSESSED`.
>   Consequently the "VAULT LOCKED" wording in §1 and §3 describes the readout **as it was**, not as
>   it is.
> * **§5.1 (Third Door is decorative w.r.t. authority) — STILL TRUE, deliberately.** Wiring it to a
>   mechanical lock was proposed and refused on measurement: the door reads unassessed on every host
>   (no readiness artifact exists to read), so a lock would have refused every operator everywhere,
>   and would have been enforcing *absence of evidence* as *denial*. The readout fix is the
>   prerequisite; a lock, if ever built, binds to `THIRD_DOOR_LOCKED` and never to
>   `THIRD_DOOR_UNASSESSED`.
> * **§2's central claim was re-tested from the other side.** A proposal to auto-execute
>   `TIER_0`/`TIER_1` commands from the TUI while airgapping `TIER_3`/`TIER_4` was refused, because
>   `builder-hitl approve-patch` — the command the `a` key composes — **is `TIER_1`**. The tiers
>   classify a command's mechanism (artifact-only), not its authority, and for that command writing
>   the artifact *is* the approval. See
>   `test_tier_is_a_blast_radius_classifier_not_an_authority_classifier`.

---

## Verdict in one line

**The governance gates held — but not for the reason the directive supposes, and the headline
number it asks for cannot honestly be produced.** STRATUM has no execution authority to gate. There
is nothing to bypass, so there is no bypass to test; what there is, is the absence of the
capability, which these lanes now pin.

---

## 1. The premise that did not survive contact

The directive frames STRATUM as an engine with HITL gates in front of it, and `ThirdDoorGate` as
"an impassable blocker". Measured, it is neither.

| Directive's model | Measured reality |
| --- | --- |
| Execute a `TIER_3`/`TIER_4` command, get blocked by a gate | **There is no execution path to attempt.** The palette is a tier inspector; selection composes a string. |
| `ThirdDoorGate` is an impassable blocker | It is a `Static` that renders eight constraints and the words VAULT LOCKED. **Nothing in the codebase consults it for a decision.** |
| HITL approval is a happy path with some friction | `approve`/`reject` are **constitutive refusals**. The TUI composes a CLI command for the operator's own terminal and stops. |

STRATUM's own compose modal states this in its header: **"context injection · STRATUM runs nothing"**.

This is the same shape this repository keeps getting caught by — *something that looks like the
source of authority and isn't*. A splash owning `app.screen`. A fossil `build/` palette. A docstring
for a method that never runs. `ThirdDoorGate` is the newest member of that family: it is named like
a gate, rendered like a gate, and enforces nothing.

## 2. Objective 1 — Governance breach: **HELD**

Driven against the real `COMMAND_AUTHORITY_REGISTRY`, with `subprocess.run`/`Popen` trip-wired to
raise on any launch.

- **3 `TIER_4` commands** exist: `builder-deepagents`, `builder-deepagents delegate`,
  `builder-hitl run-command`. Selecting any → `refused (command is forbidden or unpromoted)`,
  **no composer opens**, screen returns to base.
- **26 `TIER_3`**, 18 permitted. A permitted one opens the composer prefilled — and stops there.
- **A pending Tier-4 patch proposal on disk stayed byte-identical** (`state: PENDING`) across every
  key tried: `a`, `r`, `i`, `?`, and escape from each.
- **The trip-wire never fired.** STRATUM owns exactly **one** process launch in the whole TUI —
  `_hand_off_goose_readonly`, fixed argv, `shell=False`, read-only Goose, reached only via an
  explicit confirm. Nothing on the HITL or palette path acquires a second.

The refusal is real and it is checked against the real registry — but the *load-bearing* reason
nothing breaches is architectural, not defensive: **the keypress→execution edge does not exist.**

## 3. Objective 2 — The Friction Score

### Happy path: **2 presses — and that is the terminus, not the finish line**

| # | press | result |
| --- | --- | --- |
| 1 | `a` | Binds the pending gate, opens the composer **prefilled** with `uv run builder-hitl approve-patch` |
| 2 | `enter` | Surfaces the composed command; composer closes |

**Friction Score: 2.** Minimal, non-redundant, and prefilled so the second press is a confirmation
rather than typing. **Nothing to flag as hostile.**

> ⚠️ **The number must not be read as "2 presses to approve."** There is no third press that
> approves, and no number of presses that would. The flow terminates at a command the operator runs
> in their own terminal. **A "presses to complete a capability promotion" score does not exist for
> this surface** — reporting one would be fabricating a path. The artifact assertion in the lane
> proves the flow settled nothing on its way out.

This is a deliberate boundary, not an unfinished feature. STRATUM's stated reason: *"TUI cannot
harvest confirmation for a digest it renders"* — a keypress may not launder the approval boundary of
a TIER_3/TIER_4 surface.

### Rollback path: **CLEAN**

`r` → composer → `escape`, three times:

- Screen stack unwinds to base every cycle. No hang.
- **No orphaned nodes.** Node census identical across cycles.
- Proposal unmutated.

**A near-miss worth recording.** The first measurement looked like a leak: **39 nodes at boot → 65
after the first interaction**. It is not. The 26 arrivals are all `FooterKey` — Textual's `Footer`
lazily mounting one child per binding. It is Textual's furniture arriving, not STRATUM's litter, and
it stabilises immediately (65, 65, 65, 65 across four cycles). A lane that compared against the boot
census would have reported a phantom orphan leak forever. The lane compares **cycle-to-cycle**, which
is what a real leak — monotonic growth — would actually look like.

## 4. What these lanes pin

| Lane | Claim |
| --- | --- |
| `test_selecting_a_forbidden_command_refuses_and_composes_nothing` ×3 | Every TIER_4 command is refused, no composer |
| `test_selecting_a_permitted_command_composes_it_but_still_executes_nothing` | Fail-closed ≠ correct: permitted commands still work |
| `test_the_gate_keys_compose_a_command_and_never_touch_approval_state` ×2 | `a`/`r` compose the governed CLI command; artifact byte-identical |
| `test_no_gate_keypress_reaches_a_subprocess` | No key acquires an execution edge |
| `test_friction_two_presses_compose_an_approval_and_that_is_the_terminus` | Friction Score = 2, pinned as an exact number |
| `test_rejecting_the_composer_restores_the_screen_without_orphaning_nodes` | Stack unwinds, no accumulation |
| `test_the_third_door_is_a_readout_not_a_blocker` | VAULT LOCKED, composer still reachable |

### Mutation proof (4/4)

| mutation | lanes red |
| --- | --- |
| Palette composes for forbidden commands (drop authority check) | 3 |
| `approve` writes `APPROVED` to the artifact | 2 |
| `approve` shells out to a subprocess | 4 |
| *(inert attempt: injected before the gate binds — caught and redone)* | — |

The fourth row is kept deliberately. The first version of the mutation wrote to
`_hitl_proposal["path"]` *before* `try_bind_pending_hitl()` had populated it, so it silently did
nothing and **11 lanes passed** — which reads exactly like a hole in the test suite. The corrected
mutation self-asserts that it is not inert. A mutation that does not mutate is a green that means
nothing, which is the same failure mode as the instrument this whole track exists to fix.

## 5. Unvarnished findings

1. **`ThirdDoorGate` is decorative with respect to authority.** It renders eight constraints from
   `project_third_door()`; no caller reads its state. If it is meant to enforce, it does not, and
   nothing today would notice. *(Recorded, not fixed — enforcement is a promotion boundary
   decision, not a test-lane decision.)*
2. **The Third Door reads VAULT LOCKED by default.** With no promotion readiness artifact present
   all eight constraints are unevaluated, which renders as locked. Unevaluated is not failed — the
   widget's own docstring says so — but the rendering does not distinguish "not yet assessed" from
   "assessed and refused" at a glance.
3. **The friction score's real cost is the context switch**, not the keypresses. Two presses, then
   the operator leaves the TUI, runs a command elsewhere, and returns. That is the governance
   boundary working as designed; it is worth naming as the actual UX cost rather than pretending
   the cost is keystrokes.
4. **`pilot.click` cannot reach most palette entries.** With every registered command mounted, an
   entry scrolled out of the viewport raises `OutOfBounds`. The driver reports this as a failed step
   rather than swallowing it, but selection-by-click is not drivable for arbitrary commands without
   filtering first. *(Textual hit-testing, not governance. Noted for future driver work.)*

## 6. Boundary of this audit

These lanes prove what STRATUM **does not do**: execute, mutate approval state, or gate on the Third
Door. They do not prove the underlying `builder-hitl` CLI honours its own boundaries — that is
`docs/audits/B4_CLOSURE_AUDIT.md`'s territory, and the composed command is where STRATUM's
responsibility ends and the CLI's begins.

No deepagents *orchestration* workflow was driven, because none is reachable from this surface:
`builder-deepagents delegate` is TIER_4 `forbidden_unpromoted` and the palette refuses it. The `y`
(Orchestration) mode is a projection view, not a workflow engine. **Auditing "a Deepagent
Orchestration workflow" through the TUI is not currently possible** — not because it is gated,
but because it does not exist.
