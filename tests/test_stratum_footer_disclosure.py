"""Footer progressive disclosure (audit F5): the always-on footer shows only the core loop.

~30 footer chips read as a cockpit wall and bury the five keys a first session actually
needs. Advanced bindings stay live but show=False: H carries the full keymap, and the HITL
gate light names A/R/I/D at the one moment they mean anything. This pins both halves so a
future Binding(...) added with show=True by reflex fails here and gets a deliberate
decision instead.
"""

from __future__ import annotations

from builder_ii.tui.app import StratumApp
from builder_ii.tui.widgets.signals import HITLGateIndicator

#: the curated always-visible core: navigate, palette, CLI, pin, help, guide, pipeline.
_EXPECTED_SHOWN = {
    "escape",
    "q",
    "question_mark",
    "c",
    "space",
    "h",
    "0",
    "p",
    "v",
    "g",
    "n",
}

#: keys that must stay bound (the keymap truth pin covers their actions) but stay out of
#: the always-on footer.
_EXPECTED_HIDDEN = {"m", "o", "u", "z", "w", "y", "b", "e", "t", "a", "r", "i", "d", "f", "s", "l", "slash", "tab"}


def _bindings() -> list:
    return [b for b in StratumApp.BINDINGS if getattr(b, "key", None) is not None]


def test_footer_shows_exactly_the_core_loop() -> None:
    shown = {b.key for b in _bindings() if b.show}
    assert shown == _EXPECTED_SHOWN, (
        f"footer drift: shown={sorted(shown)} expected={sorted(_EXPECTED_SHOWN)} — "
        "a new always-on footer chip needs a deliberate decision, not a reflex show=True"
    )


def test_advanced_keys_stay_bound_but_hidden() -> None:
    by_key = {b.key: b for b in _bindings()}
    for key in _EXPECTED_HIDDEN:
        assert key in by_key, f"advanced key {key!r} lost its binding entirely"
        assert not by_key[key].show, f"advanced key {key!r} leaked back into the footer"


def test_open_hitl_gate_names_its_keys() -> None:
    indicator = HITLGateIndicator()
    indicator.gate_open = True
    indicator.gate_label = "pending approval on disk"
    text = str(indicator.render())
    for token in ("A approve", "R reject", "I inspect", "D diff"):
        assert token in text, f"open gate must name {token!r} (keys are footer-hidden)"
    assert "compose only" in text, "gate hint must not imply the keys grant authority"

    indicator.gate_open = False
    closed = str(indicator.render())
    assert "A approve" not in closed, "closed gate must not advertise approval keys"
