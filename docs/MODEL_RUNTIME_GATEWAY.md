# Model routing and runtime gateway

Plan Set 5 makes the WRP artifacts the only canonical source of role, ordered
model candidates, providers, risk ceiling, and model budget. Runtime callers
reconstruct an immutable `ModelRouteBinding`; they do not select or widen it.

```text
WRP recommendation + assignment + policy + registry + budget
    -> ModelRouteBinding
    -> ModelExecutionGateway
    -> bounded streaming transport
```

`ModelExecutionGateway` remains the sole model executor. Its invocation engine
owns transport mechanics only: first-public-token streaming, cooperative
cancellation, one retry (two attempts per candidate), WRP-order failover,
health probes, and bounded persistent HTTP connection reuse. A permanent error,
any public output, cancellation, provider/risk drift, or insufficient remaining
worst-case budget prevents retry or failover.

Native Deep Agents receives a prevalidated route and budget. The parent and all
workers share the gateway-backed model adapter. Canonical Goose sessions connect
to a loopback OpenAI-compatible adapter that translates requests into the same
gateway; Goose receives only a route-derived local credential and never receives
the underlying provider secret.

Cloud candidates require an unexpired, canonical-digest approval covering every
provider and the full WRP cost ceiling. Receipts disclose planned and actual
model/provider identity, attempt history, failover reason, timing, pre/post budget
digests, approval reference, egress, and secret token references. Raw secrets are
redacted and never persisted.

## M1-v1 benchmark evidence

`builder-model benchmark --profile m1-v1 --output <directory> ...` consumes the
existing digest-bound WRP recommendation, assignment, execution policy, registry,
budget, and exactly two Deep Agents obligations, reconstructs the immutable route, and emits digest-bound manifest,
raw-sample, report, and model/MCP/runtime receipt evidence. Replay samples remain
diagnostic-only and cannot qualify M1-v1. These artifacts are evidence only:
`artifact_is_authority`, `grants_authority`, and `promotes` are all false.

On Apple Silicon MLX, the default-model acceptance metric is the maximum sampled,
de-duplicated macOS physical footprint for the validated managed server process
set. `/usr/bin/footprint` receives the root PID and every descendant in one call,
so the tool performs shared-memory de-duplication. The collector invokes exactly
`sudo /usr/bin/footprint` with fixed flags, shell disabled, and the validated PID
set. Authentication is handled only by sudo's native visible prompt; Python never
requests, reads, pipes, or stores a password. Baseline, load/warm, and inference
samples are all retained. Process-tree RSS and graphics
categories remain diagnostics and are never added to the physical-footprint
total. The unchanged hard range is 2-7 GiB inclusive.

Control-plane and idle STRATUM memory continue to use process-tree RSS. Warm TTFT
compares the same `ModelExecutionGateway` transport directly with the fully WRP-
governed path, and non-model dispatch p95 uses nearest-rank calculation. Benchmark
dispatch evidence requires 100 successful admitted deterministic service calls;
STRATUM must remain alive for all 30 settled samples; and runtime concurrency is
measured only while the frozen two-worker Deep Agents plus Goose/gateway-reuse
workload executes. Missing or refused evidence is UNAVAILABLE/FAIL, never zero.
Benchmark evidence cannot select a model/provider, expand budget, authorize cloud use, or
promote a capability.

The canonical CLI shape, as exposed by `builder-model benchmark --help`, is:

```text
builder-model benchmark --profile m1-v1 --output <directory> \
  --route-digest <sha256> --policy-digest <sha256> --budget-digest <sha256> \
  --model-recommendation <path> --model-assignment <path> \
  --execution-policy <path> --registry <path> --model-budget <path> \
  --deepagents-obligation <first.json> --deepagents-obligation <second.json> \
  [--model-pid <validated-pid>]
```

The direct and WRP-governed TTFT arms, Native Deep Agents runtime, and Goose
loopback all reuse one `ModelExecutionGateway`. The collector stops at the
Deep Agents HITL checkpoint after both obligations complete; benchmark evidence
does not approve that checkpoint. Goose reuses the resulting route and debit
successor without owning or closing the shared gateway.
