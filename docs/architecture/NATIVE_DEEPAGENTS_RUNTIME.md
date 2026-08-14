# Native Deep Agents runtime contract

Status: Plan Set 2 bounded implementation.

The native lane integrates `deepagents>=0.6.12,<0.7.0` through the official
`deepagents.create_deep_agent` API. Deep Agents owns graph scheduling, subagent
context, and interrupt mechanics. Builder-II continues to own authority, model and
tool admission, WRP obligations, budgets, persisted-state integrity, receipts, and
evidence.

This is a capability-scoped runtime, not ambient agent authority. A readiness
artifact is not approval, approval is not execution, and model or subagent output is
not verification.

## Admission chain

The only supported native chain is:

```text
passive work plan
  -> passing backend-readiness gate
  -> candidate bound to model registry, model policy, limits, and WRP envelope
  -> exact candidate approval plus native-backend acknowledgement
  -> run-approved with at least two minted obligation files
  -> mandatory HITL interrupt and digest-bound checkpoint
  -> resume-approved with the original inputs and exact checkpoint digest
  -> completed native evidence bundle
```

`protocol_fake` remains available as a deterministic structural test double. Its
artifacts never prove that the native factory, upstream task tool, middleware, or
checkpointer ran.

## Adapter ownership

| Concern | Owner and invariant |
|---|---|
| Agent construction | `NativeDeepAgentsRuntime` is the sole Builder-II caller of `create_deep_agent`. |
| Models | One `GatewayBackedChatModel` instance is shared by the parent and children. Every call crosses `ModelExecutionGateway` and emits the existing model envelope/receipt artifacts. |
| Tools | The upstream `task` tool performs bounded delegation. Executable tools are explicitly Builder-governed; the proof tool uses the existing tool policy, envelope, gateway, and receipt chain. |
| Subagents | Each definition is derived from one validated WRP obligation and embeds its parent ref, budget partition, boundary, output contract, and file refs. |
| Filesystem | Upstream filesystem permissions deny read and write for the parent and every child. No shell, Git, direct-provider, or target-repository mutation tool is exposed. |
| Persistence | `DigestBoundCheckpointSaver` serializes the upstream checkpoint, pending writes, and blobs to a digest-bound JSON store. A fresh process can restore it; missing or edited state fails closed. |
| Middleware | `BuilderGovernanceMiddleware` enforces cumulative model/tool budgets, worker concurrency, cancellation, tool admission, and event recording across interrupt/resume. |
| HITL | `builder_request_hitl` is configured with upstream `interrupt_on`. Resume requires the exact current checkpoint-store digest supplied explicitly by the operator. |

## Resource policy

- Default active workers: `2`.
- Configurable worker cap: `4`.
- Model instances: exactly one shared instance per native run.
- Model and tool call budgets: positive candidate-bound limits, reconstructed from
  the persisted event chain on resume.
- Human gates: at least one gate must exist in the sealed root budget.
- Multiple concurrently loaded large local models: prohibited by the shared-model
  construction.

Worker concurrency limits active upstream `task` calls. It does not widen any child
obligation or grant a tool that the parent does not possess.

## Evidence contract

The run writes only below its approved output root:

- `native-events/event-*.json`: monotonic, previous-digest-linked runtime events;
- `model-calls/*`: existing model policy/envelope/receipt artifacts;
- `tool-calls/*`: existing tool policy/envelope/receipt artifacts;
- `native-checkpoint-store.json`: digest-bound upstream state;
- `native-deepagents-evidence.json`: parent/child closure and references to the
  complete event, model, tool, and checkpoint evidence.

Completed evidence validates only when it shows at least two distinct delegated and
completed obligation children, governed model and tool receipts, the required HITL
interrupt/resume sequence, one approved persisted-state digest, and no shell, Git,
target-repository mutation, or direct-provider bypass claim. Native event,
checkpoint, and evidence kinds are registered in both artifact indexing and chain
verification without importing the optional runtime dependency.

## Verification claim

`tests/test_native_deepagents_runtime.py` executes the real upstream graph with a
deterministic Builder-II gateway stub. It proves adapter structure and governance:
two upstream `task` calls, governed model/tool receipts, persisted-state
reconstruction in a fresh runtime, exact-digest resume, parent/child closure,
artifact-index closure, tamper rejection, worker cap, inherited WRP boundaries,
cumulative budgets, and persisted cancellation.

The test does not claim model quality, live-provider quality, target-repository
mutation authority, or authorization for later open-source-v1 plan sets.
