# Open-Source V1 Plan Set 5 — M1 Model-Footprint Method Correction

STATUS: `PLANNED_ONLY_AWAITING_DIGEST_BOUND_HITL_APPROVAL`

ORIGINAL_PLAN_COMMIT: `7277714f28f646c5f7f569defb0d261595c5cd1d`

ORIGINAL_PLAN_SHA256: `2829400d2fe8fdcac303b486bbb42d0fe1c23b5d93383aa64e4a2b0a95c1513e`

ORIGINAL_BASE: `5a8b033fa8d2a119cdae731828ea43f81e36df58`

CORRECTION_SCOPE: `M1-v1 DEFAULT_LOCAL_MODEL_FOOTPRINT measurement instrument only`

## Authority and boundary

This supplemental artifact corrects one technically invalid measurement
instrument in the frozen Plan Set 5 benchmark methodology. It does not modify
`planning/OPEN_SOURCE_V1_PLAN_SET_5.md`, revoke the preserved Plan Set 5
implementation authorization, authorize implementation of this correction, or
authorize Plan Set 6, capability promotion, or merge.

**ALL OTHER PLAN_SET_5 REQUIREMENTS REMAIN BYTE-SEMANTICALLY UNCHANGED.**

Routing authority, streaming, cancellation, retry, failover, warm reuse, Deep
Agents, Goose, budgets, cloud policy, TTFT, dispatch latency, control-plane RSS,
STRATUM RSS, runtime concurrency, and every architecture decision remain governed
by the original frozen plan. Implementation may resume only after this file's
exact SHA-256 digest is independently reviewed and approved.

## Frozen falsification evidence

The qualifying physical observation was:

```text
PLATFORM:
Apple Silicon M1 / 16 GiB unified memory

MODEL:
mlx-community/Qwen2.5-Coder-7B-Instruct-4bit

VALIDATED_MODEL_SERVER_PID:
23601

PROCESS_TREE_PEAK_RSS:
712425472 bytes
approximately 0.663 GiB

MACOS_PHYSICAL_FOOTPRINT:
4394 MiB
approximately 4.291 GiB

IOACCELERATOR_GRAPHICS:
4152 MiB
approximately 4.055 GiB
```

Disposition:

```text
RSS_MEASURES_INTENDED_MODEL_FOOTPRINT = FALSE

REASON:
dominant MLX/Metal unified-memory allocation is charged through macOS
graphics/physical-footprint accounting rather than represented by process-tree
RSS.

ORIGINAL_2_TO_7_GIB_THRESHOLD_INTENT = VALID
ORIGINAL_RSS_INSTRUMENT = INVALID
```

The RSS observation remains falsification evidence. It is not retroactively a
pass. MLX uses Apple Silicon unified memory, and macOS physical-footprint
accounting includes ledgered graphics allocations that RSS does not represent
adequately. The macOS `footprint` tool also de-duplicates shared objects when
measuring multiple processes. Relevant technical references are the
[MLX unified-memory documentation](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html),
the [`footprint(1)` manual](https://manp.gs/mac/1/footprint), and the corroborating
[MLX issue showing divergent framework and macOS graphics/footprint accounting](https://github.com/ml-explore/mlx/issues/3896).

## Successor model-footprint methodology

This section replaces only the original `Default local model memory`
methodology subsection.

### Identity gate

Before memory measurement, prove:

```text
backend == mlx-lm
platform == macOS
architecture == Apple Silicon / arm64
model == declared m1-v1 default local model
```

Identify the exact Builder-II-managed model server through the existing backend
marker, listener identity, served-model identity, and process-ownership checks.
A foreign, ambiguous, stale, exited, reused, or mismatched process identity is
`UNAVAILABLE / FAIL`. The collector must never guess a process.

### Primary acceptance instrument

Use the read-only macOS `/usr/bin/footprint` tool for the validated root PID and
its descendants, using the target macOS release's exact equivalent of:

```text
/usr/bin/footprint
    --pid <validated-model-server-pid>
    --targetChildren
    --format bytes
```

Prefer stable machine-readable output and validate its parser deterministically.
The acceptance value is:

```text
DE_DUPLICATED_MODEL_SERVER_TREE_PHYSICAL_FOOTPRINT_BYTES
```

The process-set measurement must use `footprint`'s shared-memory de-duplication.
It must not sum per-process `phys_footprint`, sum process RSS, add RSS to graphics
allocations, or add IOAccelerator categories to physical footprint.

### Sampling and acceptance statistic

Preserve the original temporal methodology by sampling:

```text
baseline
during model load
during warm-up
throughout measured inference
```

Record:

```text
baseline physical footprint
steady-warm physical footprint
maximum sampled physical footprint
```

The acceptance statistic is:

```text
MODEL_FOOTPRINT_ACCEPTANCE_BYTES =
maximum sampled de-duplicated physical footprint
```

Do not subtract baseline for acceptance.

The threshold and units are unchanged:

```text
PASS:
2 GiB <= MODEL_FOOTPRINT_ACCEPTANCE_BYTES <= 7 GiB

1 GiB = 1024^3 bytes
```

There is no tolerance, relaxation, or reinterpretation.

## RSS retained as diagnostic evidence

Continue measuring the existing process-tree RSS values:

```text
RSS_BASELINE
RSS_STEADY_WARM
RSS_PEAK
```

For default-local-model footprint these values are `DIAGNOSTIC /
NON-ACCEPTANCE`. They preserve cross-platform evidence and the observed
divergence, but they do not decide the 2–7 GiB gate.

## Graphics categories are diagnostic components

Where available, retain `footprint` category evidence for:

```text
IOAccelerator
IOAccelerator (graphics)
Owned physical footprint (unmapped) (graphics)
other relevant graphics/Metal categories
```

These are explanatory subcomponents only. They must never be added to physical
footprint because physical-footprint accounting already incorporates the relevant
graphics sub-ledgers. Double-counting is forbidden.

## Methods explicitly unchanged

This correction does not apply to either RSS gate below:

```text
CONTROL_PLANE_RSS_EXCLUDING_MODEL_RUNTIME
    -> process-tree RSS
    -> PASS < 1 GiB

IDLE_STRATUM_RSS
    -> process-tree RSS
    -> PASS maximum <= 250 MiB
```

The TTFT methodology is also unchanged. The provisional direct-transport result
is non-canonical. Resumed qualification must compare:

```text
DIRECT BASELINE:
ModelExecutionGateway without WRP / Deep Agents orchestration

GOVERNED:
the same ModelExecutionGateway with the full WRP governed route
```

Use the same model, prompt, `max_tokens`, temperature, warm transport, sample
count, and alternating pair order required by the original frozen methodology.
No other benchmark method changes.

## Minimal evidence-schema correction

The successor implementation may minimally extend the benchmark manifest and
report with:

```text
model_memory_acceptance_metric = macos_physical_footprint

model_physical_footprint:
    baseline_bytes
    steady_warm_bytes
    peak_bytes
    acceptance_bytes

model_rss_diagnostic:
    baseline_bytes
    steady_warm_bytes
    peak_bytes

graphics_memory_diagnostics:
    ioaccelerator_bytes
    ioaccelerator_graphics_bytes
    owned_unmapped_graphics_bytes
```

No new hard thresholds are authorized. Both artifacts remain evidence, not
authority:

```text
artifact_is_authority = false
grants_authority = false
promotes = false
```

## Deterministic qualification requirements

Before rerunning the physical M1 benchmark, add deterministic coverage for:

```text
footprint parser
byte-unit parsing
process identity
child-process inclusion
shared-memory de-duplication at the collector boundary
missing footprint binary
non-zero footprint exit
malformed output
foreign PID
PID exit/reuse race
model identity drift
sampling and maximum calculation
2 GiB inclusive lower boundary
7 GiB inclusive upper boundary
below-boundary failure
above-boundary failure
RSS retained as diagnostic only
IOAccelerator not added twice
manifest methodology digest
report methodology binding
```

Use frozen fixture output where generic CI cannot invoke the real macOS tool.
Physical M1 qualification remains the real acceptance evidence.

## Resume and denied boundaries

After exact-digest approval, resume the preserved Plan Set 5 implementation from
the existing implementation worktree. Do not restart or re-plan it. Implement the
corrected collector and deterministic tests, rerun physical qualification with
the canonical gateway-based TTFT comparison, remediate ordinary in-scope failures,
then complete documentation, matrix reconciliation, exact-tip receipt-backed
local CI, commit, push, and the single Plan Set 5 pull request.

Until that approval:

```text
CORRECTION_IMPLEMENTATION = NOT_AUTHORIZED
PLAN_SET_5_IMPLEMENTATION_RESUME = NOT_AUTHORIZED
PLAN_SET_6 = NOT_AUTHORIZED
CAPABILITY_PROMOTION = NOT_AUTHORIZED
MERGE = NOT_AUTHORIZED
```

This correction does not authorize a ChatGPT/Codex subscription transport,
credential scraping, Codex-as-hidden-provider execution, a second executor, or a
generic subprocess beneath the model gateway.
