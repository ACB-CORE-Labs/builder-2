# Orchestration Obligations (Law 1 Tickets)

Orchestration Obligations are deterministic, digest-bound artifacts that represent a bound delegation of authority to a subagent or tool runner. They enforce **Law 1: No speech without a ticket.** 

## Design

An obligation artifact (`builder_ii.orchestration_obligation`) contains:
- `obligation_kind`: The class of work (e.g., `planning_step`, `interactive_ops`, `mutation`, `verification`).
- `lane`: The governed execution lane, derived from the active `builder_ii.orchestration_lane_policy`.
- `task`: The prompt or assignment description.
- `output_contract`: The evidence and artifact kinds the discharge must produce to satisfy the obligation.
- `budget_partition`: Hard bounds on `max_subagents`, `max_events`, `max_output_bytes`, and `max_human_gates`.

## Lifecycle

1. **Minting:** An obligation is statically minted via `builder-orchestration mint-obligation`. The lane policy is evaluated, the budget is recorded, and the artifact is cryptographically sealed (digest pinned). 
2. **Execution (The Seal):** The sealed obligation is consumed by a runner. The runner enforces the budget envelope dynamically, refusing to exceed `max_events` or `max_subagents`. 
3. **Discharge:** The runner produces the artifacts and evidence required by the `output_contract`.
4. **Validation:** The discharge is verified against the obligation's contract. If the evidence matches, the obligation transitions to `SATISFIED`.

## CLI Surface

See `docs/COMMAND_AUTHORITY.md` for exact capabilities and promotion states.
- `builder-orchestration mint-obligation`
- `builder-orchestration validate-obligation`
- `builder-orchestration lane-policy`
- `builder-orchestration validate-lane-policy`
- `builder-orchestration status`
- `builder-orchestration why`
