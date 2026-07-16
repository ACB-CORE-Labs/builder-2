"""`builder_ii.tui.widget_ids` — the encoding three widget families are addressed by.

The property under test is injectivity, and the cost of losing it is not a cosmetic one: two
widgets claiming one id is a `MountError` at mount time, so the palette would not open at all.
"""

from __future__ import annotations

import re

import pytest

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.tui.widget_ids import TEXTUAL_ID, id_token, widget_id


def _registry_names() -> list[str]:
    return [record.name for record in COMMAND_AUTHORITY_REGISTRY]


def test_naive_replacement_would_collide_which_is_why_id_token_escapes() -> None:
    """Pins the reason the encoding is not the obvious one.

    Substituting every character Textual rejects with `-` is what one writes first. It merges
    `builder hitl` (the root CLI subcommand) with `builder-hitl` (the standalone console script),
    and 26 further such pairs, and Textual answers same-id siblings with `MountError`.

    Asserted from the real registry rather than described in a comment: if these names ever stop
    colliding the escaping has lost its justification, and whoever notices should be told by a test
    rather than have to rediscover it.
    """
    names = _registry_names()
    naive = {re.sub(r"[^a-zA-Z0-9_-]", "-", name) for name in names}
    assert len(naive) < len(names), (
        "naive replacement no longer collides on this registry -- re-derive whether id_token still "
        "needs to escape"
    )
    assert len({id_token(name) for name in names}) == len(names)


def test_id_token_is_injective_over_the_real_command_registry() -> None:
    """Every record must reach its own id. The palette is built from exactly this list."""
    names = _registry_names()
    assert len(names) > 400, "registry unexpectedly small; this lane would prove little"
    ids = {widget_id("palette-entry", name) for name in names}
    assert len(ids) == len(names)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("builder hitl", "builder-hitl"),  # both are real registry entries
        ("builder hitl", "builder_hitl"),
        ("builder-hitl", "builder_hitl"),
        ("a b", "a-b"),
        ("a_b", "a b"),
    ],
)
def test_names_differing_only_by_separator_never_share_an_id(left: str, right: str) -> None:
    assert id_token(left) != id_token(right)


def test_a_literal_underscore_survives_as_itself() -> None:
    """`_` is the escape character, so it must escape itself or the encoding is ambiguous.

    Without this, a capability named `model_exec` and a hypothetical `model` + code point 0x65
    could encode alike.
    """
    assert id_token("model_exec") == "model_5f_exec"
    assert id_token("model_5f_exec") != id_token("model_exec")


def test_every_generated_id_satisfies_textuals_own_id_rule() -> None:
    """A cheap check against the documented rule; `test_stratum_tui.py` proves it by mounting."""
    for name in _registry_names():
        generated = widget_id("palette-entry", name)
        assert TEXTUAL_ID.match(generated), f"{name!r} produced an id Textual would reject: {generated}"
