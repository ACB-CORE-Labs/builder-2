"""STRATUM action affordance — derives what a keybinding may do from command authority.

The compose-only default on most of `app.py`'s `action_*` handlers was a UI decision, not always a
registry one: nine call sites ended in a bare `CLIPassthroughScreen(...)`, and
`enforce_command_authority` was called from exactly one of them (`action_launch_goose`). Nothing
distinguished "compose-only because the registry demands it" from "compose-only because nobody
wired the direct path" -- an unwired affordance wearing the costume of a governance boundary. A
prior external audit read that costume as license and flipped two TIER_4 records to TIER_3 by hand
to "unblock" agent autonomy, when the actual gap was legibility, not permission.

`project_action_affordance` closes that gap by reading the same assurance lattice
`explain_assurance_for_record` already computes and turning it into one of five affordances. It
derives; it does not decide what STRATUM does with the answer. An `INVOKE_DIRECT` affordance is
necessary, never sufficient, license for a call site to skip the compose step -- `builder stratum`'s
own command-authority record must still declare any new direct invocation, the way it already
declares the one Goose exception.
"""

from __future__ import annotations

from dataclasses import dataclass

from builder_ii.governance.authority.assurance import AssuranceState
from builder_ii.governance.authority.authority_registry import get_command_record
from builder_ii.governance.authority.signet_verifier import explain_assurance_for_record

#: The registry would allow this to run the moment the key is pressed -- no confirm, no compose.
INVOKE_DIRECT = "invoke_direct"
#: The registry would allow this to run after an interactive accept (`ConfirmScreen`).
INVOKE_WITH_CONFIRM = "invoke_with_confirm"
#: STRATUM composes the CLI line; the operator reviews, edits, and runs it in a terminal.
COMPOSE_ONLY = "compose_only"
#: The registry denies this command outright -- forbidden, unpromoted, or safety-critical.
REFUSE = "refuse"
#: No command-authority record names this command at all. Absence, not a boundary.
UNWIRED = "unwired"

# Every assurance state maps to exactly one affordance. Totality over `ASSURANCE_STATES` is pinned
# in `tests/test_stratum_authority_projection.py` -- a state added to the lattice without an entry
# here fails loudly instead of falling through to a default.
_STATE_TO_MODE: dict[AssuranceState, str] = {
    "PASSIVE_ARTIFACT_VERIFIED": INVOKE_DIRECT,
    "LOCAL_STATE_MUTATION_VERIFIED": INVOKE_DIRECT,
    "READ_ONLY_RUNTIME_VERIFIED": INVOKE_WITH_CONFIRM,
    "BOUNDED_EXECUTION_VERIFIED": INVOKE_WITH_CONFIRM,
    "MUTATION_WITH_ROLLBACK_VERIFIED": COMPOSE_ONLY,
    "LIVE_PROVIDER_VERIFIED": COMPOSE_ONLY,
    "DEMO_ONLY_VERIFIED": COMPOSE_ONLY,
    "BLOCKED_BY_EVIDENCE": REFUSE,
    "SAFETY_CRITICAL_PROHIBITED": REFUSE,
}


@dataclass(frozen=True)
class ActionAffordance:
    """What a STRATUM keybinding may do with a governed command, and the one fact that says why."""

    command: str
    mode: str
    because: str


def project_action_affordance(command_name: str) -> ActionAffordance:
    """Derive `command_name`'s affordance from the live command-authority registry.

    Mirrors `explain_assurance_for_record`'s own promise that the state alone is not reviewable: this
    carries the single fact that produced the mode (`because`) alongside it. An unregistered name is
    `UNWIRED`, distinct from `REFUSE` -- `check_command_authority` folds both into `allowed=False`,
    which is the right yes/no answer for a gate but destroys exactly the distinction a reader needs
    to tell a designed refusal from an unfinished feature.
    """
    record = get_command_record(command_name)
    if record is None:
        return ActionAffordance(
            command=command_name,
            mode=UNWIRED,
            because="no command-authority record names this command",
        )

    derivation = explain_assurance_for_record(record)
    return ActionAffordance(command=command_name, mode=_STATE_TO_MODE[derivation.state], because=derivation.because)
