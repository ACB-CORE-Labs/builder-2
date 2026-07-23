# STRATUM Orchestration Cockpit — design for sign-off

> **Status: DESIGN_ONLY.** Nothing in this document implements, enables, or promotes any
> capability. Stage 2 below would cross a documented STRATUM boundary and therefore
> requires the full eight-gate promotion path; this document exists so that decision is
> made once, deliberately, instead of leaking in one convenience at a time.

## 1. Problem (audit F3)

The deepagents lane already has a real run lifecycle — approved candidates, run/resume,
checkpoints (`CHECKPOINTED`), a hash-chained event ledger, and replay — but the operator
console has **no run-control surface**. There is no way, from STRATUM, to watch a run's
events as they land, drill into what it is doing, stop it, resume it, or adjust its
configuration. Auditability without agency: today an operator who sees something wrong in
the ledger tail has to leave the console, find the right CLI incantation, and hope the
run state is what they think it is. The requirement (operator-stated): *see what it's
doing, drill down, and stop/start it if something is wrong.*

## 2. The boundary this touches

`docs/STRATUM.md` records the console's contract: STRATUM **is** a read-only view and a
command composer; it **is not** an "executor of composed commands." A cockpit whose Stop
button actually stops a run crosses that line — STRATUM would gain dispatch authority for
the first time. That is not a reason to refuse it; it is a reason to stage it and gate it.
The Third Door applies to UIs too: the answer to "the TUI must never execute" is not a
wall of composed commands, it is *governed* execution with the same artifacts, approvals,
and receipts as the CLI lane it fronts.

## 3. Stage 1 — Drill-down + compose (no contract change)

Everything in this stage is projection and composition, inside STRATUM's existing
contract, implementable without a promotion decision:

- **Run roster.** Under **Y**, a cockpit pane lists deepagents run envelopes and event
  ledgers found on disk: run id, backend mode, status (`COMPLETED` / `CHECKPOINTED` /
  `FAILED`), event count, last event age, obligation discharge summary.
- **Live event drill-down.** Selecting a run tails its ledger in place (the signal rail
  already tails global events; this scopes to one run), with pin/inspect on any event —
  the same j/k/SPC grammar the spine already teaches. Digest chain state is shown from
  the validator's verdict, never synthesized.
- **Checkpoint tree.** Checkpoints render as resumable points with their digests; the
  budget/obligation state at each is projected from the artifacts.
- **Compose controls.** Stop / resume / re-grant surface as composed `builder-deepagents`
  command lines (the teaming/composer pattern), which the operator runs in their
  terminal. The cockpit shows the *exact* fixed argv it would take.

Stage 1 alone closes most of F3's observability half and is honest about the rest: the
buttons say "compose," because that is what they do.

## 4. Stage 2 — Governed dispatch (contract change; eight gates)

The proposal: STRATUM may **dispatch** exactly three verbs, and only against a run whose
authority already exists on disk:

| Verb | Precondition (fail-closed) | Effect |
|---|---|---|
| Start | Digest-bound approval artifact for the candidate exists and validates | Invokes the same governed run path as `builder-deepagents run-approved` |
| Stop | Run is live in this process | Records a checkpoint event and halts scheduling; never kills mid-write |
| Resume | Checkpoint + still-valid approval (and, under ADR-0008, an unexhausted grant) | Same governed path as `resume-approved` |

Constraints that make this governed rather than convenient:

- **No new authority is minted in the TUI.** The approval the dispatch consumes was
  created by the existing HITL lane; the cockpit only *uses* it, exactly as the CLI does.
  A missing, tampered, or stale approval refuses identically.
- **Same artifacts, same receipts.** A cockpit-started run writes the same envelope,
  ledger events, checkpoints, and receipts as a CLI-started run; nothing distinguishes
  the two in the audit trail except the recorded invocation surface.
- **ConfirmScreen on every dispatch**, naming the run id, candidate digest, and (under
  ADR-0008) the sealed grant's budget — the operator confirms against digests, not vibes.
- **Command-authority registration.** The dispatch surface gets its own tier entry in the
  authority registry, so `builder-platform` truth surfaces report it; `docs/STRATUM.md`'s
  is/is-not table is updated in the same change (docs and code flip together or not at
  all).
- **Config adjustment is compose-only, permanently.** "Adjust config" means: compose a
  new grant/config artifact → the operator approves it → a resume consumes it. In-place
  mutation of a live run's configuration stays impossible by construction.

## 5. Failure modes

| Failure | Behavior |
|---|---|
| Approval missing/tampered at Start | Refusal with the validator's error; nothing scheduled |
| Stop during an in-flight step | Step completes or fails on its own; checkpoint records after; no silent retry |
| Process exits mid-run | On next launch the roster shows the run `CHECKPOINTED`/`FAILED` from disk truth |
| Resume with exhausted grant (ADR-0008) | Refusal event; cockpit composes the re-grant command |

## 6. Sequencing

Stage 1 is ordinary feature work reviewable on its own. Stage 2 depends on operator
acceptance of this document, updates `docs/STRATUM.md`'s contract table in the same PR
that lands the code, and follows the eight promotion gates with its own closure evidence.
If ADR-0008 lands first, Stage 2's Start/Resume verbs inherit the grant preflight for
free; neither document depends on the other's acceptance.
