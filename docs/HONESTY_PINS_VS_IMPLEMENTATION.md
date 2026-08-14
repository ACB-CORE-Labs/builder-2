# Honesty pins vs implementation

**Status:** doctrine (load-bearing for last-mile and WRP).  
**Not** a promotion grant.

## The confusion to kill

Two different things get collapsed into one phrase:

| Concept | Meaning | Correct engineering response |
| --- | --- | --- |
| **Honesty pin** | A validator / default that rejects *false claims* (e.g. `spawn_executed=true` with no work, `cloud_provider_invoke` without mode/gates, `s3_enabled=true` without ceremony). | Keep pins. Never invent authority. |
| **Implementation** | The real code path that performs governed work and *can* set flags true when evidence and gates exist. | **Implement fully.** Do not leave logic unbuilt because “the pin is false by default.” |

**Honesty pins are not a reason to defer building muscle.**

Defaults that say `false` mean “no claim yet / unearned,” **not** “capability must not exist in the codebase.”

## Rules

1. **Default false is a claim about the artifact, not a ban on code.**  
   A lifecycle record with no seam evidence correctly claims `spawn_executed=false`. That does not mean AgentFactory may never bind to a real subagent loop.

2. **Earned true requires evidence, not ceremony-as-procrastination.**  
   When gates exist (budget, HITL approval, kill-switch, ledger digests, approval_path for cloud), the implementation path must be present and testable offline (stubs / injected transport). Operator keys and live promotion ceremonies activate production use; they do not postpone writing the path.

3. **Pins reject false inflation, not true capability.**  
   - Reject: `spawn_executed=true` without `seam_execution` digests.  
   - Accept: `spawn_executed=true` with subagent-loop + plan digests + approved_by + gateway_mode.  
   - Reject: `cloud_provider_invoke=true` with `gateway_mode=record`.  
   - Accept: `gateway_mode=invoke_cloud` + approval + hard spend cap + egress record.

4. **Separate surfaces stay separate.**  
   - Lifecycle record `s3_enabled=false` ≠ “do not implement session-scoped S3 enablement.”  
   - Class U report `s3_enabled=false` ≠ “do not implement multi-agent harness.”  
   - Global registry defaults remaining false is fail-closed product policy, not incomplete engineering.

5. **Permanent non-goals are different.**  
   Arbitrary HITL free-form command execution is **REMOVED FROM DESIGN** (MASTERPIECE). That is not an honesty pin; it is intentional non-capability. Do not implement it.

## Code map (examples)

| Surface | Default / pin | Implemented path |
| --- | --- | --- |
| AgentFactory lifecycle | `spawn_executed=false` without evidence | `spawn_agent(seam_execution=…)` → earned true |
| Subagent loop | N/A | `run_governed_subagent_loop` → may earn spawn |
| WRP gateway | default `record` | `invoke_local` / `invoke_cloud` modes |
| Cloud | env allow_cloud off | `cloud_chat.py` + invoke_cloud gates |
| S3 | global default false | `s3_enablement.py` session binding when Class U held |

## Language ban (in code/docs for new work)

Avoid:

- “always false” when an earned path exists  
- “DEFERRED until HUMAN” meaning “don’t write the code”  
- “honesty pin” as a synonym for “not implemented”

Prefer:

- “default false (unearned)”  
- “earned under gates”  
- “implementation complete; activation gated”

## Tests that protect this doctrine

- `tests/test_last_mile_non_goals.py` — default lifecycle unearned; command exec still removed  
- `tests/test_wrp_agent_factory_lifecycle.py` — default + earned spawn paths  
- `tests/test_honesty_pins_vs_implementation.py` — structural pins of this doctrine  

*Soli Deo gloria.*
