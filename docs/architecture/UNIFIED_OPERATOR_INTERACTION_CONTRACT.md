# Unified operator interaction contract

Status: design contract. It specifies projection and interaction behavior but
grants no runtime, approval, mutation, delivery, or promotion authority.

## User grammar

The normal user learns five commands: `init`, `start`, `resume`, `inspect`, and
`doctor`. Everything else is a contextual action or an expert/automation surface.

The daily loop is:

```text
start a task -> converse -> inspect relevant work -> intervene at attention
-> review validated results -> resume or close
```

Normal operation does not expose artifact kinds, authority tiers, command names,
or lifecycle bookkeeping unless the user asks to inspect them.

## Default information hierarchy

The Lens answers only:

| Question | Projection |
| --- | --- |
| What is the goal? | exact current task and target |
| What is happening? | calm activity label plus active agent/tool/model |
| What needs me? | ranked attention items |
| What happens next? | one recommended admissible intent |
| What proves it? | evidence health and latest validated receipt |

Canonical lifecycle state remains present in `RunView`; the frontend may add a
calm activity label but may not rewrite or infer the stage.

## Attention and interruption

Priority is:

```text
corrupt or foreign evidence
recovery ambiguity
non-delegable human authority
budget, model, provider, or tool escalation
verification or delivery decision
informational state
```

Safe reads, passive analysis, and admitted delegation continue without prompting.
Mutation, rollback, external effects, escalation outside the run envelope,
corruption, or uncertain recovery become explicit attention items.

An initial patch gate shows intent, path count, pre-apply verification, and rollback
readiness. One gesture reveals target/base/tree, full diff, digest, expiry, receipts,
policy, provenance, and ledger history.

## Governed action contract

An action is a typed client of an existing authority-bearing command, never an
executor vocabulary of its own. It binds one authority record, exact run state,
typed inputs, artifact digests, interaction mode, consequences, cancellation,
expected outputs, and owning validators.

The action sequence is:

```text
RunView -> derive -> recheck authority/bindings -> disclose consequence
-> owning command -> reload -> validate -> event -> updated RunView
```

The four interaction modes are `inline_query`, `background_stream`,
`floating_tty`, and `refuse`. Tier 3 HITL remains in the owning CLI TTY. No UI
control collects or persists an approval digest.

## Layout contract

Wide terminals use Goose plus one adaptive Lens. Narrow terminals use full-screen
Goose plus a status line and Lens overlay. Diff, approval, verification, agent,
evidence, and recovery views are temporary focused surfaces.

Required constraints:

- no more than two permanent panes;
- no more than five global chords or seven visible actions;
- complete keyboard access and no color-only state;
- full evidence in one gesture;
- no routine command copying or second terminal application; and
- closing a UI/workspace surface never silently closes the canonical run.

## Failure language

The UI distinguishes refused, failed, cancelled-before-effect,
cancelled-after-contact, mutation-uncertain, corrupt, orphaned, interrupted,
recoverable, and terminal. It never collapses these into a generic failure or
success. Every non-terminal state has a recovery action or a precise explanation
that recovery is unavailable.

## Visual validation

Semantic Pilot tests, deterministic fixed-size captures, real PTY interaction, and
supervised dogfood are required. Visual captures prove layout and usability only;
canonical validators and receipts prove governed state.
