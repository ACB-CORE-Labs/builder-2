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
#:
#: `ctrl+g` (run a governed task) was added here deliberately, which is what this pin exists to
#: force. It earns a permanent chip because it *is* the core loop now -- state a task, watch the
#: governed run stream in the cockpit -- and a capability that exists but is invisible is the
#: exact failure the streamed-run lane was built to fix. It sits beside `g`, which remains the
#: interactive session that suspends the terminal; the two are different enough to both be named.
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
    "ctrl+g",
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
    for token in ("A approve", "R refuse", "I inspect", "D diff"):
        assert token in text, f"open gate must name {token!r} (keys are footer-hidden)"
    # The keys reach `builder-hitl` now, so "compose only" would be false. What the hint must
    # still do is name where the decision is actually made, so the operator does not read the
    # keys as STRATUM deciding.
    assert "builder-hitl" in text, "gate hint must name the governed command the keys hand off to"

    indicator.gate_open = False
    closed = str(indicator.render())
    assert "A approve" not in closed, "closed gate must not advertise approval keys"
