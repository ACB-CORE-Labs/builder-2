# Open-Source V1 Plan Set 5 — Model Routing Authority and Runtime Performance

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

PLAN_BASE: `5a8b033fa8d2a119cdae731828ea43f81e36df58`

PLAN_BASE_TREE: `1ef04d40499385496fdb09845b95d420b1f211f7`

## Boundary and purpose

Plan Set 3 and Plan Set 4 are closed. More Plan Set 4 hardening is stopped.
This artifact defines one complete Plan Set 5 implementation milestone. It does
not authorize implementation, Plan Set 6 delivery-product implementation,
capability promotion, CORE specialization, or DeepHaven work.

The governing distinction is:

> Performance, streaming, failover, reuse, and routing optimization may never
> weaken model policy, provider disclosure, budget ceilings, authority
> boundaries, or receipt truth.

The approved implementation, if separately authorized against this file's exact
SHA-256 digest, must proceed as one continuous milestone and one implementation
pull request. The internal phases below are engineering order, not additional
approval ceremonies.

```text
WRP plan
    -> exact role/model/budget route
    -> one ModelExecutionGateway
    -> Deep Agents / Goose / internal callers
    -> streaming + cancellation + bounded retry + governed failover
    -> canonical receipts + budgets + provider truth
    -> warm-runtime reuse
    -> frozen M1 benchmark
    -> registered thresholds PASS
```

## Current-code findings at the frozen base

The implementation must preserve and extend these observed foundations:

- `ModelExecutionGateway` is the canonical governed model execution seam. It
  validates registry and execution policy, admits local/cloud calls, records
  client/provider/model identity, creates call envelopes and receipts, performs
  token/price-book accounting, debits model budgets, redacts persisted evidence,
  and prohibits tool, shell, repository, and memory mutation.
- `run_direct_chat()` and the cloud OpenAI-compatible adapter use synchronous
  one-shot `httpx.post()` calls. They have no first-token stream, reusable client,
  retry engine, candidate failover, or gateway-level cooperative cancellation.
- Model routing recommendations already contain an ordered candidate list with
  provider, client, model, alias, risk, cost, source policy, source registry, and
  optional WRP classification binding. Orchestration assignments bind the
  recommendation and copy its first candidate into `bindings.model.selected_candidate`.
- `builder_ii.model_budget` already carries digest-bound token and USD ceilings,
  immutable debit versions, remaining-budget calculation, and pre-call budget
  checks. It is distinct from Ladder-4 event/byte obligation budgets.
- WRP gateway helpers currently accept execution-time `model_id`, `budget`,
  `auto_budget`, registry, and execution policy inputs. They synthesize a one-model
  recommendation and widen `allowed_models` when needed. The cloud helper also
  creates a default budget when none is supplied. These are authority leaks that
  the canonical path must remove.
- The WRP subagent helper accepts a caller-selected `model_id`, derives a child
  budget at execution time, and passes both to gateway nodes. Canonical subagent
  execution must consume the parent WRP route and its allocated budget instead.
- Native Deep Agents correctly uses `GatewayBackedChatModel` and
  `ModelExecutionGateway`, but its candidate and runtime configuration independently
  carry `native_runtime.model_id`; runtime construction does not prove equality to
  the WRP-selected model or bind a model budget route.
- `builder-model call` and `standalone-call` accept `--model`. The former is a
  canonical governed call and must consume or exactly match a WRP route. The latter
  may remain an explicit diagnostic expert lane, but may not emit canonical WRP-run
  routing claims.
- Goose's launcher currently derives `GOOSE_PROVIDER`, `GOOSE_MODEL`, provider
  host, and real provider credentials directly. Its OpenAI-compatible configuration
  already supports a caller-supplied host, so a loopback gateway adapter is
  technically compatible with the supported launcher shape. Canonical Goose
  inference must no longer receive real provider credentials or bypass the gateway.
- Backend health and reuse primitives already exist: backend health probes, served
  model identity checks, Builder-II backend markers, marker/settings comparison,
  and managed backend process startup. Plan Set 5 must reuse these owners.
- No Plan Set 5 TTFT/RSS/runtime benchmark harness or benchmark evidence grammar
  exists. Existing validation benchmarks are unrelated functional validation and
  must not be repurposed as performance proof.

## One authority shape

Plan Set 5 strengthens the existing Builder-II grammar rather than adding a new
authority vocabulary:

```text
artifact -> validate -> approve -> execute -> receipt
```

WRP plans. Approval admits the exact route and cloud/budget envelope.
`ModelExecutionGateway` executes. Provider transports only transport. Receipts
state what actually happened. Benchmark evidence measures but does not authorize.

Exactly one model executor and one model planner are allowed:

```text
MODEL_EXECUTORS = 1
CANONICAL_EXECUTOR = ModelExecutionGateway

MODEL_PLANNERS = 1
CANONICAL_PLANNER = WRP
```

## Canonical route binding — no new persistent route artifact

The current canonical artifacts can express the Plan Set 5 route when validated
together. Do not introduce a new persistent route schema in this milestone.

Add a typed, immutable in-memory `ModelRouteBinding` projection assembled only
from validated, digest-bound inputs:

- WRP model routing recommendation and its ordered `recommended_candidates`;
- orchestration assignment and `bindings.model.selected_candidate`;
- model execution policy and its recommendation digest;
- model client registry and its source digest;
- the exact `builder_ii.model_budget` version allocated to the run/obligation;
- cloud approval/egress evidence when the route contains cloud candidates;
- session, run, obligation, and role identity from the governed run;
- route parameters already bounded by the policy/registry, including temperature
  and maximum output tokens.

The projection must contain at least:

```text
session_id / run_id / obligation_id / role
routing_recommendation_digest / assignment_digest
policy_digest / registry_digest / budget_digest
ordered candidates with model_alias/model_id/provider_id/client_id/risk
selected candidate
max risk and explicit cloud/provider allowance
cloud approval ref, cost ceiling, and secret token refs when applicable
max input/output/total tokens and max USD
temperature / max_tokens
allowed failover candidates
```

Canonical JSON serialization of that projection produces `route_digest`. The
projection itself remains in memory; its source references and `route_digest` are
bound into the model-call envelope, every attempt record, the final receipt, Deep
Agents evidence, and the Goose adapter request context. Validators reconstruct the
projection from the referenced artifacts and reject any digest or value mismatch.

The first recommendation candidate and assignment selected candidate must match
exactly. The execution policy must already contain every authorized candidate.
No executor may mutate the policy or recommendation to make a call admissible.

For canonical governed execution, prove before any provider I/O:

```text
runtime model == WRP selected model (or current WRP-ordered failover candidate)
runtime provider/client == candidate provider/client
runtime budget == WRP-bound budget version
runtime candidate is in the WRP ordered candidates
runtime risk <= WRP risk ceiling
runtime cloud use == explicit route and approval allowance
execution policy already includes every traversable candidate
all source refs and route_digest validate
```

Any mismatch refuses before provider call. Canonical `auto_budget`, synthesized
one-model recommendations, execution-time model choice, and `allowed_models`
widening become unreachable.

## Implementation scope and exact change ownership

The separately approved milestone may change only the following paths or narrowly
necessary files in the named categories. Before each edit, trace imports and all
callers again at the approved implementation tip.

### Routing authority and gateway

- `builder_ii/routing/model_execution_gateway.py`: remain the sole admission,
  budget, provider-policy, envelope, receipt, and final outcome owner; consume a
  validated route binding; record attempts, timing, cancellation, and failover.
- `builder_ii/routing/model_routing_policy.py`: strengthen recommendation/execution
  policy validation only as required for ordered route traversal and exact source
  binding; do not turn recommendations into authority.
- `builder_ii/routing/model_budget.py`: add projected worst-case attempt admission
  and truthful per-attempt/final debit support without creating budget at execution.
- `builder_ii/routing/model_route_binding.py` (new, preferred name): own the typed
  in-memory projection, canonical digest, construction, and validation. It is not a
  persisted authority artifact.
- `builder_ii/wrp/gateway_nodes.py`, `builder_ii/wrp/subagent_executor.py`, and
  `builder_ii/core/orchestration_assignment.py`: remove canonical execution-time
  model/budget selection and policy widening; construct/forward exact WRP route refs.

### Transport mechanics

- `builder_ii/routing/gateway_invocation.py` (new, preferred name): internal
  transport-mechanics engine for streaming, cancellation checks, bounded reusable
  HTTP clients, timing, retry, ordered candidate traversal, and attempt results.
  It owns no admission, model choice, policy mutation, approval, budget creation,
  or final receipt claims.
- `builder_ii/routing/direct_chat.py` and
  `builder_ii/adapters/openai_compat/cloud_chat.py`: become local/cloud
  OpenAI-compatible transports beneath the engine, with injectable deterministic
  transports for tests. Backward-compatible non-streaming calls consume the stream
  internally and return the accumulated response.

The conceptual structure is:

```text
ModelExecutionGateway (authority and truth)
    -> GatewayInvocationEngine (transport mechanics only)
        -> local OpenAI-compatible transport
        -> cloud OpenAI-compatible transport
```

### Runtime reuse and health

- `builder_ii/routing/backends.py` and `builder_ii/routing/backend_state.py`: reuse
  current health, served-model identity, marker, listener, and managed-process
  controls; add only the bounded reuse/switch/refusal behavior required below.
- Existing settings/runtime context owners may be adjusted narrowly to make client
  and server lifecycle explicit. Do not add shell-based process discovery.

### Deep Agents and Goose

- `builder_ii/adapters/deepagents/native_runtime.py` and
  `builder_ii/adapters/deepagents/deepagents_execution.py`: replace independent
  model identity/budget inputs with a validated route binding; preserve upstream
  execution, obligation, checkpoint, interrupt, and evidence owners.
- `builder_ii/adapters/goose/goose_launcher.py`,
  `builder_ii/adapters/goose/goose_runtime_harness.py`, and narrowly necessary
  files under `builder_ii/adapters/goose/`: point canonical Goose inference at the
  loopback adapter, bind session/route identity, and keep existing Plan Set 3
  recipe, MCP, target, close, and receipt governance unchanged.
- `builder_ii/adapters/goose/model_gateway_adapter.py` (new, preferred name): thin
  bounded OpenAI-compatible loopback adapter translating Goose chat-completion
  requests and streamed responses to/from `ModelExecutionGateway`.

### CLI, benchmark, tests, and truth surfaces

- `builder_ii/cli/model_cli.py`: make canonical `call` consume a route package or
  require `--model` to equal the selected route exactly; retain `standalone-call`
  only as clearly diagnostic/non-canonical.
- New narrowly scoped modules under `builder_ii/benchmark/` and CLI registration
  for `builder-model benchmark --profile m1-v1 --output <artifact-dir>`.
- Focused unit, integration, adversarial, schema, CLI, Deep Agents, Goose, and
  benchmark tests under `tests/` plus deterministic fixtures/profiles.
- Affected operator/model docs, command-authority generated truth,
  `platform_completion_audit.py`, completion-matrix pins, and docs-truth pins only
  as necessary to state actual implemented/verified status. No promotion row flips.

## Streaming contract

Use provider streaming when supported. One request records monotonic timestamps:

```text
request_started_at
first_public_chunk_at
completed_at

TTFT = first_public_chunk_at - request_started_at
```

The first public chunk is the first non-empty user-visible response content. Hidden
reasoning, metadata, usage records, keepalives, empty deltas, and transport framing
do not count. The engine yields bounded public chunks; the gateway accumulates the
canonical final response and creates one final receipt. It must not persist one
governance artifact per token.

Envelope/receipt validation must cover `streaming`, first-token latency when a
public chunk exists, total latency, public output chunk count, completion state,
attempt history, actual candidate identity, and response digest. Partial output is
never successful completion. Non-streaming compatibility consumes the same engine
and truthfully records `streaming = false`.

## Cooperative cancellation contract

Add one cancellation token/signal abstraction shared by gateway callers and checked:

```text
before provider request
while waiting for the response/stream
between chunks
before retry
before failover
before final success emission
```

Cancellation closes the response/stream and stops consumption. It causes no retry,
no failover, no success event, and no completed response claim. The final receipt is
digest-bound and records `status = cancelled`, `complete = false`, bounded partial
output metadata/content if retained, timing, actual attempt identity, and budget
effects actually incurred. Cancellation is distinct from provider failure.

Deep Agents' existing run cancellation must propagate to the gateway token; Goose
client disconnect/cancellation must propagate through the loopback adapter. A race
between final chunk and cancellation resolves under a single synchronized terminal
state so success after accepted cancellation is impossible.

## Bounded retry contract

Freeze:

```text
MAX_ATTEMPTS_PER_CANDIDATE = 2
```

This means one initial attempt and at most one retry for a candidate. Retry only a
transient failure before first public output: connection failure, connect/read
timeout, HTTP 429, or HTTP 5xx. Do not retry policy/budget/approval denial, invalid
route/model/provider, credential-policy failure, permanent 4xx, cancellation, or
any failure after first public output.

Before retry, cancellation and route health are rechecked and the model budget
must admit the projected worst-case next-attempt input, output, total-token, and USD
cost. All attempts share the exact WRP-bound budget lineage. No retry may create,
increase, replace, or reset a budget. Every attempt and refusal is recorded in the
final receipt with candidate identity, ordinal, reason, timing, public-output state,
and measured/estimated cost.

## Governed failover contract

Failover is traversal of WRP's already ordered candidates, never discovery or
executor selection. After exhausting the primary under the retry rule, the engine
may consider only the next candidate in the frozen route and only after the gateway
revalidates policy, risk, provider/cloud approval, health, credentials, and remaining
worst-case budget.

Rules:

```text
no candidate outside the route
no provider/client outside the route
no risk above the route ceiling
no implicit local-to-cloud escalation
no failover after public output
no failover after cancellation
no failover that exceeds remaining budget
no policy mutation to admit a candidate
```

An unhealthy primary with an authorized equal/lower-risk secondary may traverse.
An unhealthy primary with no authorized secondary refuses with remediation. Health
is an input to an already authorized choice and creates no authority.

Cloud traversal is allowed only when the original WRP route already contains the
cloud candidate and binds explicit cloud allowance, provider, unexpired approval,
hard cost ceiling, and secret-source token reference. A local failure can never
create cloud authority.

The final receipt binds planned primary, actual model/provider/client, attempt and
failover counts, candidate sequence, failover reason, route digest, cloud egress,
and budget before/after state.

## Warm runtime and HTTP reuse contract

For an already-running healthy Builder-II-managed local server serving the exact
selected model and endpoint identity, reuse the runtime and record its marker/PID
identity. Do not start another server. Two active Deep Agents workers using one
route share one gateway runtime context and one model server.

The default flow permits at most one resident large local model runtime. If a route
requires a different large local model while one is resident, do not launch a
second. Either reuse a route-compatible resident model already authorized by WRP,
perform an explicitly governed stop/switch through existing managed runtime controls,
or refuse with exact remediation. A stale, foreign, mismatched, or unverifiable
marker fails closed.

Use a bounded reusable `httpx.Client`/transport pool owned by an explicit gateway
runtime context. Configure finite connection counts and timeouts, make concurrency
safety explicit, and provide deterministic `close`/context-manager lifecycle.
Do not use a process-global hidden client, persist credentials in artifacts, or
permit an unbounded pool. Warm benchmarks include both server and HTTP reuse.

## Goose gateway decision — frozen

Canonical Plan Set 5 Goose inference uses a thin OpenAI-compatible loopback adapter:

```text
Goose
    -> OpenAI-compatible Builder-II loopback endpoint
    -> ModelExecutionGateway
    -> validated WRP route
    -> approved local/cloud provider transport
```

The adapter is not a second executor, planner, policy engine, budget owner, or
authority. It accepts only a bounded chat-completion subset required by the tested
Goose version, maps the request to the already-bound route/session, propagates
streaming and disconnect cancellation, and translates the gateway result back.
Unknown routes, request model mismatch, unsupported request fields, missing session
binding, and stale/foreign bindings refuse before provider call.

For canonical launch, Goose receives the loopback URL, the WRP-selected public model
identifier (validated exactly), session/route identity, and a scoped non-provider
local adapter credential if authentication is required. It does not receive real
cloud API keys, bearer tokens, provider endpoints, or permission to choose another
provider/model. Provider secrets remain solely inside Builder-II's cloud adapter.

Preserve the Plan Set 3 governed recipe, MCP-only tool extension, compatibility
probe, target admission, launch receipt, transcript/interruption, and close/postflight
path. The adapter owns model HTTP translation only. If implementation-time testing
against the supported Goose version disproves this frozen interface with no
technically equivalent single-gateway configuration, stop under the named early-stop
condition rather than retaining the bypass.

## Native Deep Agents route binding

The canonical flow is:

```text
WRP route
    -> NativeDeepAgentsRuntime
    -> GatewayBackedChatModel
    -> ModelExecutionGateway
```

Candidate creation binds the recommendation, assignment, policy, registry, model
budget, and cloud approval refs required to reconstruct `ModelRouteBinding`.
Runtime creation validates all refs and route digest before constructing upstream
Deep Agents. `native_runtime.model_id` may remain only as a convenience copy that
must equal the selected candidate; it is not an independent input. Workers and
subagents inherit the route/budget lineage and cannot choose models, candidates,
providers, or budgets. Existing obligation, tool, concurrency, checkpoint, HITL,
cancellation, and evidence controls remain authoritative.

## Cloud disclosure and secret contract

Cloud remains explicitly harder-gated than local. Every cloud attempt and final
receipt exposes:

```text
provider_id / client_id / model_id
endpoint_kind / network = true
approval_ref / budget_ref / hard cost ceiling
actual measured or estimated cost
secret_source_token_ref
route_digest and attempt/failover identity
```

Cloud retry/failover remains within the original approval scope and cost ceiling.
Persisted envelopes, attempts, receipts, benchmark artifacts, errors, and logs must
never contain authorization headers, raw API keys, bearer tokens, or resolved secret
environment values. Secret pattern scanning/redaction and adversarial artifact-tree
scans qualify this invariant. Token references may be persisted; secret values may not.

## M1-v1 benchmark command and evidence

Add one canonical expert command:

```text
builder-model benchmark --profile m1-v1 --output <artifact-dir>
```

It may perform explicitly requested governed model calls and measurements. It may
not install software, pull models, log in to providers, mutate target repositories,
grant authority, change policy/budgets, promote capability, or invent unavailable
measurements.

Introduce paired evidence artifacts only because methodology must be frozen before
measurement and results must be independently validated afterward:

```text
builder_ii.model_runtime_benchmark_manifest
builder_ii.model_runtime_benchmark_report
```

These are evidence, not authority. The manifest binds the approved `m1-v1`
methodology before observation. The report binds manifest digest, exact Git commit
and tree, Builder-II version, platform/architecture/chip/RAM/OS/Python, backend,
provider/client/model, route/policy/registry/budget digests, sample counts, warm-up
policy, formulas, raw sample refs/digests, registered thresholds, actual results,
and PASS/FAIL/MEASURED/UNAVAILABLE per metric. Both set
`artifact_is_authority = false`, `grants_authority = false`, and `promotes = false`.

Raw samples are bounded JSON/JSONL evidence referenced by digest. Validators must
recompute statistics from them, validate environment/process identity, reject
foreign/substituted samples, and refuse a report whose methodology differs from
the manifest.

## Frozen M1-v1 methodology

The following methodology is part of this plan digest and may not change after
results are observed without a newly frozen and approved Plan Set 5 digest.

### Warm governance/orchestration TTFT overhead

- Use the same deterministic public prompt, model, output limit, temperature, and
  sequential sample order for direct-gateway baseline and fully governed WRP route.
- The direct baseline still uses `ModelExecutionGateway`; it omits WRP/Deep Agents
  orchestration around the call but never bypasses gateway provider/budget truth.
- Preload the exact model and reuse the same bounded warm HTTP transport class.
- Run one unmeasured warm-up per path, then at least 10 measured paired samples,
  alternating the order within each pair to limit temporal bias.
- TTFT uses the streaming definition in this plan. Compare medians.
- `overhead_percent = (governed_median_ms - direct_median_ms) /
  direct_median_ms * 100`.
- If direct median is zero/non-positive, the result is invalid, not PASS.
- PASS when overhead is at most 20 percent.

### Non-model policy/tool dispatch

- Use at least 100 deterministic, admitted, non-model dispatch samples through the
  canonical policy/tool dispatch seam with provider/model calls disabled.
- Use a monotonic clock; measure the same bounded operation and exclude fixture
  setup, process launch, and artifact-directory cleanup.
- Sort observed latencies and use nearest-rank p95: rank `ceil(0.95 * n)`, one-based.
- Publish p50, p95, maximum, and raw samples.
- PASS when p95 is below 150 ms.

### Default local model memory

- Qualify the declared default local model on the physical 16GB Apple Silicon M1.
- Identify the exact model-server PID and descendants using Builder-II-managed
  marker/listener/process identity; refuse ambiguous or foreign ownership.
- Sample resident set size before load, during load, during warm-up, and throughout
  measured calls. Aggregate the model-server process tree without double-counting.
- Report baseline, steady warm, and peak RSS plus model identity.
- PASS when the selected default model runtime footprint lies from 2 GB through
  7 GB inclusive. Use binary units (`1 GiB = 1024^3 bytes`) and report bytes and GiB.

### Control-plane RSS excluding model runtime

- Identify the Builder-II control-plane PID tree for the full governed benchmark.
- Explicitly exclude the validated model-server PID tree and refuse overlap or
  ambiguous identity.
- Sample throughout route validation, streaming, retry/failover fixtures, Deep
  Agents orchestration, and report generation; use peak aggregated RSS.
- PASS when peak is strictly below 1 GiB.

### Idle STRATUM RSS

- Launch STRATUM normally with no model runtime and no benchmark-only feature flags.
- Allow five normal refresh cycles to settle, then collect 30 one-second samples
  from the STRATUM process tree.
- Report p50/p95/maximum; use the maximum as the acceptance statistic.
- PASS when maximum is at most 250 MiB (`250 * 1024^2 bytes`).

### Default large-model concurrency

- Execute the full default two-worker Deep Agents route plus Goose/gateway reuse
  integration path while observing Builder-II-managed model-server identities.
- Count distinct resident large-model runtime process trees at every sample point.
- PASS only when the maximum count is at most one. Missing/ambiguous process identity
  is UNAVAILABLE/FAIL, never assumed zero.

### Published measurements without invented thresholds

Record, with environment, sample count, warm-up rule, p50/p95/maximum or median as
appropriate, and raw sample refs:

- cold TTFT: cold server/client start through first public chunk;
- warm TTFT and output throughput in public output tokens/second;
- memory peak as defined above;
- Deep Agents delegation overhead relative to the same governed gateway call;
- interruption latency from accepted interrupt to terminal interrupted evidence;
- resume latency from admitted resume to first resumed public chunk/event;
- governed-tool latency through the canonical admitted tool seam.

These metrics are `MEASURED` or `UNAVAILABLE` with truthful reasons. Plan Set 5 does
not assign them additional pass thresholds.

## Registered hard thresholds

The master completion plan thresholds are frozen unchanged:

```text
DEFAULT_LOCAL_MODEL_FOOTPRINT:                 2 GiB-7 GiB inclusive
CONTROL_PLANE_RSS_EXCLUDING_MODEL_RUNTIME:     < 1 GiB
IDLE_STRATUM_RSS:                              <= 250 MiB
WARM_GOVERNANCE/ORCHESTRATION_TTFT_OVERHEAD:   <= 20 percent
NON_MODEL_POLICY/TOOL_DISPATCH_P95:            < 150 ms
DEFAULT_SIMULTANEOUS_LARGE_MODEL_RUNTIMES:     <= 1
```

Do not lower, reinterpret, or replace these thresholds after measurement.

## Deterministic qualification before physical M1 measurement

Ordinary local CI must not pretend to prove physical-hardware thresholds. Add
deterministic tests for:

- route construction/reconstruction, source substitution, canonical digest, WRP
  selected candidate, policy set, risk, cloud approval, and budget equality;
- refusal before provider I/O for model/provider/client/budget/policy/route mismatch;
- streaming parsing, first-public-chunk timing, accumulation, compatibility mode,
  partial-output failure, and receipt validation under fake clocks/transports;
- cancellation at every checkpoint and terminal-state races;
- retry classification, attempt limit, public-output prohibition, and projected
  remaining-budget admission;
- ordered failover, health inputs, risk/provider/cloud bounds, receipt history, and
  refusal when no candidate remains;
- reusable HTTP client limits, explicit close, concurrent callers, and credential
  non-persistence;
- backend marker, exact served-model reuse, stale/foreign marker refusal, governed
  switch/refusal, same-route worker sharing, and one-large-runtime enforcement;
- Deep Agents route equality, inherited model budget, cancellation propagation,
  and no worker/subagent route choice;
- Goose loopback request binding, supported subset, streaming, disconnect
  cancellation, no provider credential exposure, and existing Plan Set 3 launch/
  close invariants;
- benchmark schema, artifact digest/ref validation, fake-clock formulas, nearest-rank
  percentiles, RSS process-tree aggregation/exclusion, units, sample counts,
  methodology immutability, and non-authority pins;
- command authority, docs truth, platform matrix truth, and diagnostic versus
  canonical CLI claims.

## Mandatory adversarial qualification

The implementation and final evidence must prove all lesions below.

### WRP authority

- Deep Agents/Goose/runtime model differs from WRP selected candidate: refuse before
  provider call.
- Runtime budget or budget digest differs from WRP binding: refuse.
- Execution policy excludes the selected or traversed candidate: refuse; never add it.
- Canonical route asks for `auto_budget`: refuse.
- Foreign, stale, substituted, or digest-mismatched route source: refuse.
- Caller attempts to reorder candidates or raise risk/cloud ceiling: refuse.

### Cloud

- Local-only primary fails: no cloud failover.
- Provider/client absent from route, cloud opt-in absent, approval missing/expired/
  substituted, or cost ceiling insufficient: refuse before egress.
- Raw secret anywhere in persisted output/evidence tree: qualification fails.
- Token-ref secret source with no persisted value: passes the disclosure check.

### Streaming and cancellation

- Cancellation before request produces zero provider calls.
- Cancellation while waiting/before first public chunk yields cancelled with no
  retry/failover.
- Cancellation after partial output yields cancelled; partial output is never success.
- Metadata/empty/hidden chunks do not set first-public-chunk time.
- Success event/receipt after accepted cancellation is impossible.

### Retry and failover

- Transient pre-output failure receives exactly one bounded retry.
- Permanent 4xx, policy denial, cancellation, or failure after public output receives none.
- Insufficient remaining worst-case budget prevents retry/failover.
- Attempt limit exhaustion emits truthful failure and complete attempt history.
- Unhealthy primary plus WRP-approved equal/lower-risk secondary may traverse.
- Candidate outside route, risk escalation, implicit local-to-cloud, or failover
  after partial output refuses.
- Receipt binds actual model/provider/client, reason, sequence, and costs.

### Warm reuse

- Healthy same-model server reuses the exact runtime/PID identity.
- Two workers on one route share gateway runtime context and server.
- A different large local model request cannot create a second default runtime.
- Stale/mismatched/foreign marker fails closed with remediation.
- Client pool remains bounded and closes deterministically.

### Receipt truth

- Attempt history, monotonic timing, planned/actual identity, budget pre/post debit,
  failover reason, cancellation/complete state, cloud egress, source refs, and route
  digest are canonical and validator-recomputable.
- Failed/cancelled/partial calls never emit `model_call_executed` success.
- Benchmark PASS cannot mutate or replace receipt, policy, admission, or verification.

## Physical M1 qualification and exit gate

After deterministic tests pass on the exact candidate tip, run the frozen `m1-v1`
manifest once for qualification on the declared physical Apple Silicon M1 16GB
environment. Correct ordinary implementation/performance defects inside the approved
design and rerun candidate qualification as necessary, preserving failed reports as
truthful historical evidence. Do not change the methodology or thresholds to obtain
a pass.

Plan Set 5 closes only when a validator-recomputed report from the exact candidate
commit/tree marks every registered hard threshold PASS and all policy, receipt,
admission, verification, secret, Deep Agents, and Goose qualification lanes pass.
Any hard-threshold FAIL or UNAVAILABLE keeps Plan Set 5 open.

## Implementation cadence after separate approval

```text
approved exact Plan Set 5 digest
-> refresh and prove main/base custody
-> isolated exact-base implementation worktree
-> routing-authority closure
-> gateway streaming engine and reusable transport
-> cooperative cancellation
-> bounded retry and governed failover
-> warm-runtime reuse
-> Deep Agents route binding
-> Goose loopback gateway binding
-> benchmark artifacts, runner, and validators
-> focused tests and adversarial lesions
-> deterministic benchmark qualification
-> physical M1 qualification and optimization until thresholds pass
-> docs / command authority / matrix reconciliation without promotion
-> exact-tip receipt-backed bash scripts/ci.sh
-> final diff, scope, secret, and evidence audit
-> one implementation commit series/branch
-> push and one Plan Set 5 pull request only under the approved milestone delivery
-> hosted review handoff; merge remains a distinct actual event and must be reported truthfully
```

Internal phases are not approval gates. Exact-tip qualification evidence is valid
only for the commit/tree it names. GitHub-hosted workflows are not gates; local
`bash scripts/ci.sh --receipt <path>` (or the exact then-current receipt-capable
canonical form) is the required final gate.

## Early-stop conditions

Stop before complete implementation only if evidence proves one of:

- a second model executor is genuinely required;
- WRP cannot be the sole planner without redesigning a previously approved authority boundary;
- supported Goose cannot use the loopback gateway or any technically equivalent
  single-gateway design without violating its supported contract;
- this frozen benchmark methodology is technically invalid;
- a registered hard threshold is physically infeasible for the declared default
  configuration and therefore requires changing the master contract;
- Plan Set 6 product authority becomes necessary; or
- the approved base changes materially before implementation begins.

Ordinary bugs, focused/full test failures, correctable performance misses, benchmark
optimization, and repairs inside this scope are not early-stop conditions.

## Explicit denied boundaries

```text
SECOND_MODEL_EXECUTOR             = NONE
SECOND_MODEL_PLANNER              = NONE
DEEPAGENTS_MODEL_SELECTION        = NOT_AUTHORIZED
DEEPAGENTS_BUDGET_SELECTION       = NOT_AUTHORIZED
EXECUTOR_POLICY_WIDENING          = UNREACHABLE
CANONICAL_AUTO_BUDGET             = UNREACHABLE
SILENT_CLOUD_FAILOVER             = UNREACHABLE
UNAPPROVED_PROVIDER_SWITCH        = UNREACHABLE
RAW_SECRET_PERSISTENCE            = UNREACHABLE
DEFAULT_TWO_LARGE_LOCAL_MODELS    = UNREACHABLE
GENERIC_SHELL                     = UNREACHABLE
AUTO_MODEL_INSTALL_OR_PULL        = NOT_AUTHORIZED
AUTO_PROVIDER_LOGIN               = NOT_AUTHORIZED
PLAN_SET_6_LOCAL_COMMIT_PRODUCT   = NOT_AUTHORIZED
PLAN_SET_6_PUSH_PRODUCT           = NOT_AUTHORIZED
PLAN_SET_6_PR_PRODUCT_ACTION      = NOT_AUTHORIZED
CAPABILITY_PROMOTION              = NOT_AUTHORIZED
CORE_GLOBAL_SPECIALIZATION        = NOT_AUTHORIZED
DEEPHAVEN_WORK                    = NOT_AUTHORIZED
```

Performance evidence may report PASS, FAIL, MEASURED, or UNAVAILABLE. It may not
authorize execution, cloud access, budget increase, provider selection, failover,
verification, promotion, or release. The benchmark runner must never mutate policy
or methodology to make a measurement pass.

## Verification requirements for the implementation milestone

Use the smallest focused lanes throughout development, then on the settled exact tip:

1. run all focused routing/gateway/budget/transport/backend/Deep Agents/Goose/
   benchmark/adversarial tests named by the implementation diff;
2. run `builder-platform audit-docs` and `builder-platform matrix` when their
   generated truth or documentation is affected;
3. validate benchmark manifest, raw evidence, and report independently;
4. run the physical M1 profile and prove every hard threshold PASS;
5. run the repository's exact receipt-backed `bash scripts/ci.sh` final gate once
   the candidate tip is settled;
6. inspect the final diff, commit/tree, artifact refs/digests, secret scan, status,
   and denied boundaries before publication.

Passing tests does not promote a capability. Matrix or promotion state changes
require their separately governed evidence and are not authorized by this plan.

## HITL stop

This file is passive planning evidence. Stop after creating it, validating its
exact base/path/content, computing its SHA-256, and committing the planning-only
change on a feature branch if authorized by the planning mission. Do not implement
source, tests, benchmark code, runtime adapters, docs truth changes, push, PR, merge,
or promotion in this planning pass.

A human approval artifact must bind this file's exact SHA-256, identify Plan Set 5
as one combined milestone, bind the implementation base commit/tree, authorize the
path/category envelope above, preserve every denied boundary and threshold/method,
and carry the required validity/expiry data. Only that independently reviewed,
digest-bound approval authorizes implementation.
