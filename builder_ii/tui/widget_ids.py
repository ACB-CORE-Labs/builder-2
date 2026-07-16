"""Deterministic DOM ids for widgets built one-per-record from a repeating source.

A palette entry, a spine stage and a capability row are each one widget per record, and a driver
that wants to address one needs to name it. A Textual id is the only stable handle: `classes` are
shared by every sibling, and DOM position shifts the moment the palette is filtered.

The id is derived from the record's own identity, never its index. An index-derived id renames
every entry after the first match as soon as a search filters the list, which is precisely when a
driver is trying to click one.

`id_token` escapes rather than replaces. Replacing each character Textual rejects with `-` reads as
the obvious thing to do and is wrong here: the command registry contains both `builder hitl` (the
root CLI subcommand) and `builder-hitl` (the standalone console script), and 26 further such pairs.
Replacement collapses each pair onto one id and Textual raises `DuplicateIds` at mount -- the
palette would not open at all. Escaping keeps the mapping injective, so two records can never claim
one id. `test_widget_ids.py` pins that against the real registry.
"""

from __future__ import annotations

import re

# Textual validates ids against this character set (`textual.dom`); an id must additionally not
# begin with a digit. Every id here is built through `widget_id`, whose prefix supplies the leading
# character, so the "first character" rule is satisfied by construction rather than by hope.
TEXTUAL_ID = re.compile(r"^[a-zA-Z_\-][a-zA-Z0-9_\-]*$")

_ESCAPE = "_"


def id_token(value: str) -> str:
    """Encode `value` into the characters Textual accepts in an id, injectively.

    Distinct inputs always produce distinct tokens, which is the whole point: a lossy mapping shows
    up as a `DuplicateIds` crash at mount, not as a wrong id.
    """
    out: list[str] = []
    for ch in value:
        if ch.isascii() and (ch.isalnum() or ch == "-"):
            out.append(ch)
        else:
            # Terminated on both sides (`_20_`, not `_20`) so the encoding stays unambiguous for
            # any code point: `_` only ever opens an escape, hex runs until the closing `_`, and a
            # literal `_` encodes to `_5f_`. Unterminated, a literal `_` followed by "2" and a
            # code point 0x52 would both render `_52`.
            out.append(f"{_ESCAPE}{ord(ch):x}{_ESCAPE}")
    return "".join(out)


def widget_id(prefix: str, value: str) -> str:
    """Build a full Textual id. `prefix` fixes the leading character; `value` carries uniqueness."""
    return f"{prefix}-{id_token(value)}"
