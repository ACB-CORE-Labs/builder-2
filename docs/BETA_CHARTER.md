# Beta Charter

This is the charter for builder-II's beta: who it's for, what feedback is actually being asked
for, what feedback is explicitly out of scope (because it's already known and tracked elsewhere),
and how to send it. It exists so beta participants and the operator share the same expectations
before anyone starts poking at the platform — see
[`docs/MANIFESTO.md`](MANIFESTO.md) for why the project is built the way it is, and
[`docs/ROADMAP.md`](ROADMAP.md) / [`docs/CAPABILITY_PROMOTION.md`](CAPABILITY_PROMOTION.md) for
what's currently promoted vs. speculative — this charter doesn't restate that state, it points to
where it lives.

## What "beta" means here

The builder-II repository is currently **private** and has no public issue tracker. This is a
closed beta: participation means the operator gave you direct repository access, not that the
project is publicly announced or open for drive-by contribution. Nothing here implies or schedules
a publication date — see [`docs/promotions/public_cut_over.md`](promotions/public_cut_over.md) for
the (deferred, operator-only) open-sourcing cut-over readiness checklist and current status.

Capability state is not restated in this document, because it changes as work lands and a stale
copy here would itself become a doc-truth violation. Before reporting something as broken, check
what state it's actually in:

```bash
builder-platform status
builder-platform matrix
uv run builder-platform audit-docs
```

If a command's behavior doesn't match what a doc claims for it, that mismatch — not just the
underlying bug — is itself useful feedback (see "Docs-truth accuracy" below).

## Who this is for

Trusted collaborators comfortable reading source, working from a terminal, and treating the
matrix/`status` output as ground truth over any doc's prose. This beta is not aimed at people
looking for a polished product experience; it's aimed at people willing to exercise the governed
patch loop on a real repository and report back on where the governance model, the CLI, or the
docs didn't hold up.

## Scope: what the verification lane covers (D7)

The bounded verification runner targets **trusted local repositories with a Python/pytest test
suite**, invoked with a fixed argv and no shell. That boundary is a design decision (see
[`docs/RUNTIME_PROMOTION.md`](RUNTIME_PROMOTION.md) and [`SECURITY.md`](../SECURITY.md)'s threat
model notes), not a beta-scale limitation waiting to be discovered. Feedback about non-Python
targets, other test runners, or sandboxing is welcome as a feature request, but it isn't a bug
report against the current scope.

## The governed demo loop — the fastest way to see the whole thing

If you want one concrete path to exercise end-to-end, start with the demo loop
(`builder-platform demo-loop`, `validate-demo-loop`, `wow`). It runs the full propose → approve →
apply → verify → rollback loop against a temporary detached worktree of a local repository — your
own operator-designated target, or the `core` target profile if you have it checked out. Your
source checkout is never mutated: exactly one approved, temporary documentation-marker patch is
applied and then rolled back, inside a throwaway worktree. It makes no commit, no push, no model
call, and no Goose or MCP interaction.

Command names above are stable. Run `builder-platform demo-loop --help` for the current flag
shape (`--target-repo`, `--target-name`, `--marker-path`) and check `builder-platform matrix` for
this capability's row — the matrix, not this charter, is the ground truth for its state.
Feedback on this loop is especially valuable — it's the path built specifically to be run by
someone who isn't the primary operator.

## What feedback is wanted

In rough priority order:

1. **Governance model legibility.** Does the propose → approve → apply → verify → rollback loop
   make sense as you actually use it? Where did the load-bearing distinctions (planned ≠ executed
   ≠ verified ≠ promoted; artifact ≠ authority) feel real, and where did they feel like paperwork
   around something that "just worked anyway"?
2. **Onboarding friction.** Clean-clone to a first governed patch loop
   (`bash scripts/clean-clone-smoke.sh` is the scripted version of this path). Broken commands,
   confusing error messages, missing prerequisites, anything the docs assumed you'd already know.
3. **HITL ergonomics.** The interactive approval moment (typing the patch-digest prefix instead of
   `[y/N]`) and the patch apply/rollback lane — does the friction feel proportionate to what it's
   protecting, or just annoying?
4. **Docs-truth accuracy.** Any doc claim that doesn't match what a command actually does.
   `builder-platform audit-docs` catches known false-completion phrasing mechanically; it can't
   catch everything, and a human reading against real command output will find gaps it can't.
5. **CLI discoverability.** With dozens of `builder-*` console scripts, can you find the command
   you need without reading source? `builder-platform status` / `next` / `golden-path` and
   [`docs/OPERATOR_COMMAND_SURFACE.md`](OPERATOR_COMMAND_SURFACE.md) are the intended answer —
   report where that answer fails.
6. **Artifact and validator correctness.** Malformed artifacts that a `validate-*` command
   accepts, or well-formed ones it rejects; chain-verification gaps; digest mismatches that
   shouldn't occur.

When reporting, say what state you expected a capability to be in versus what you observed —
ideally with the matrix row name. "This doesn't work" means something different for a
`PLANNED_ONLY` artifact than for a command the matrix marks `OPERATIONALLY_VERIFIED`; the second
one is the actual bug.

## What's out of scope for this beta

These are already known gaps, tracked on the post-beta ladder in
[`planning/CORE_PAR_MASTER_COMPLETION_PLAN.md`](../planning/CORE_PAR_MASTER_COMPLETION_PLAN.md).
Reporting them isn't harmful, but it won't surface anything the operator doesn't already know:

- CodeVault Tier-1 content-derived encoding (today it's layout-geometry only)
- Container/VM isolation for the verification lane
- A non-Mac local-model backend (MLX is Mac-first by design for this beta)
- STRATUM TUI real wiring (gated behind the command-authority registry, not a beta-facing surface)
- Governed orchestration / deepagents delegation-lane promotion
- The secrets-preserving Goose config `merge` operation (manual config wiring is the documented
  beta path — see [`docs/CONFIG_ONBOARDING.md`](CONFIG_ONBOARDING.md))
- Full Linux CI parity

## How to send feedback (current phase)

Since there's no public tracker yet, send feedback directly to whoever gave you repository access.
Include: the command you ran, what you expected (with the matrix/doc reference if you have one),
and what actually happened. If the project moves to a public host, this section will be superseded
by issue templates and a triage cadence at that host — until then, this is the only channel.

## Related, not yet written

- A known-limitations doc generated from the truth matrix (companion to this charter — this
  charter says what feedback is wanted; that doc will say precisely what's missing and why).
- Issue intake templates and a triage cadence, once there's a public host to intake into.
