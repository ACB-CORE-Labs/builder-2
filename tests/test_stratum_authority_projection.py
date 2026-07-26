"""Pins for `builder_ii.tui.projections.authority` -- the STRATUM action-affordance projection.

Each test names the registry fact it is grounded in (checked live against `get_command_record`,
not assumed), so a future registry change that silently moves one of these commands fails here
first, loudly, rather than surfacing as a STRATUM behavior change nobody can explain.
"""

from __future__ import annotations

from builder_ii.governance.authority import (
    COMMAND_AUTHORITY_REGISTRY,
    check_command_authority,
)
from builder_ii.governance.authority.assurance import ASSURANCE_STATES
from builder_ii.tui.projections.authority import (
    _STATE_TO_MODE,
    COMPOSE_ONLY,
    INVOKE_DIRECT,
    INVOKE_WITH_CONFIRM,
    REFUSE,
    UNWIRED,
    ActionAffordance,
    project_action_affordance,
)


def test_the_affordance_map_is_total_over_the_assurance_lattice() -> None:
    """A state added to `ASSURANCE_STATES` without an entry here must fail loudly, not fall through."""
    assert set(_STATE_TO_MODE) == set(ASSURANCE_STATES)
    assert set(_STATE_TO_MODE.values()) <= {
        INVOKE_DIRECT,
        INVOKE_WITH_CONFIRM,
        COMPOSE_ONLY,
        REFUSE,
    }


def test_passive_registry_commands_derive_invoke_direct() -> None:
    """These commands are all classified PASSIVE_ARTIFACT_VERIFIED today -- checked live below.

    STRATUM currently composes every one of these rather than invoking them, which is a per-action
    UI decision this projection makes checkable, not a claim that the registry demanded compose-only.
    """
    passive_commands = (
        "builder-session prepare-package",
        "builder-session validate-prepare-package",
        "builder-hitl approve-patch",
        "builder-hitl refuse-patch",
        "builder-deepagents assign-subagent",
        "builder-platform matrix",
    )
    for name in passive_commands:
        affordance = project_action_affordance(name)
        assert affordance == ActionAffordance(
            command=name,
            mode=INVOKE_DIRECT,
            because="no flag or state raises assurance above passive",
        )


def test_goose_start_readonly_derives_invoke_with_confirm() -> None:
    """The one command STRATUM already invokes directly (`action_launch_goose`), via ConfirmScreen."""
    affordance = project_action_affordance("builder-goose start-readonly")
    assert affordance == ActionAffordance(
        command="builder-goose start-readonly",
        mode=INVOKE_WITH_CONFIRM,
        because="promotion state is `read_only_runtime_candidate`",
    )


def test_a_forbidden_tier4_command_derives_refuse() -> None:
    """`builder-deepagents delegate` is Tier 4 / forbidden_unpromoted on the live registry."""
    affordance = project_action_affordance("builder-deepagents delegate")
    assert affordance.mode == REFUSE
    assert affordance.because == "tier is `Tier 4`"


def test_an_unregistered_name_is_unwired_not_refused() -> None:
    """Absence of a record is a distinct affordance from a record that denies.

    Collapsing the two is the exact defect this module exists to fix: a prior audit read an unwired
    keybinding as a deliberate boundary and 'fixed' it by editing the registry.
    """
    affordance = project_action_affordance("builder-totally-fictitious-xyz-command")
    assert affordance.mode == UNWIRED
    assert affordance.because == "no command-authority record names this command"


def test_a_refuse_affordance_is_never_more_permissive_than_check_command_authority() -> None:
    """Cross-check against the live enforcement path for every real record in the registry.

    One direction only: `check_command_authority` also fails a HITL-artifact-required command with
    no `approval_ref` supplied, a case this projection does not model (it derives from the assurance
    lattice alone, not from a specific invocation's approval evidence). REFUSE here, though, always
    comes from `BLOCKED_BY_EVIDENCE` (Tier 4 or forbidden/unpromoted) -- a condition
    `check_command_authority` checks unconditionally -- so REFUSE must always agree with denial.
    """
    for record in COMMAND_AUTHORITY_REGISTRY:
        affordance = project_action_affordance(record.name)
        if affordance.mode == REFUSE:
            assert not check_command_authority(record.name).allowed, (
                f"`{record.name}` derives REFUSE but check_command_authority still allows it"
            )


def test_every_live_record_derives_a_defined_affordance() -> None:
    """No record in the live registry produces a mode outside the five named constants."""
    valid_modes = {INVOKE_DIRECT, INVOKE_WITH_CONFIRM, COMPOSE_ONLY, REFUSE, UNWIRED}
    for record in COMMAND_AUTHORITY_REGISTRY:
        affordance = project_action_affordance(record.name)
        assert affordance.mode in valid_modes
        assert affordance.command == record.name
