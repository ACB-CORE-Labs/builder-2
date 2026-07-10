#!/usr/bin/env python3
"""Flip assistant / consistency checker for the B4 matrix flip (plan item 1.7).

The completion matrix (``builder_ii/platform_completion_audit.py``) is the source of truth. Several
other sites must move in lockstep with it whenever a capability row's state changes: a pinned count
assert, per-capability assurance-state asserts, and the receipt/postflight/bundle governance
self-stamps in the executor. Missing one of them is the classic "flip commit that fails CI on a
single stale string" loop.

This helper reads the LIVE matrix and checks that every such pinned site agrees with it. It **never
writes** — an auto-writer for truth pins would itself be a truth-inflation vector; evidence-before-flip
stays a human decision. Run it before a flip to see the full edit set, and after a flip to confirm no
pinned string was missed.

    uv run python scripts/b4_flip_assistant.py

Exit 0 = every pinned site is consistent with the matrix. Exit 1 = at least one mismatch.

Reusable at 1.8 / 2.6: change ``FLIP_CAPABILITIES`` and, if the pin locations differ, the readers below.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from builder_ii.platform_completion_audit import (  # noqa: E402
    OPERATIONALLY_VERIFIED,
    REQUIRED_CAPABILITY_ROWS,
    CapabilityRow,
    assurance_state_for_row,
    state_counts,
)

REPO = Path(__file__).resolve().parent.parent
TRUTH_TEST = REPO / "tests" / "test_platform_completion_truth.py"
EXECUTOR = REPO / "builder_ii" / "hitl_patch_apply.py"
MIRROR_DOC = REPO / "docs" / "PLATFORM_COMPLETION_AUDIT.md"

# The capabilities whose promotion this assistant reconciles. The executor self-stamps mirror the
# "HITL patch application" row (apply/rollback share the B4 lane state). "governed demo loop" was
# added by the 1.8 pin edit (row renamed from "CORE demo loop" when the demo lane generalized to
# arbitrary generic targets); it participates in the assurance + mirror checks only.
# "interactive setup wizard" was added by the 2.6 R1 closure flip (builder init, plan item 2.2;
# docs/audits/R1_CLOSURE_AUDIT_2_6.md); it also participates in the assurance + mirror checks only.
# "governed obligation delegation" was added by the Ladder 4 PR-8 closure flip (protocol_fake
# scope; docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md); assurance + mirror checks only.
# "deepagents runtime/subagents" was added when the fall-through default was removed: it names the
# same protocol_fake trunk as "governed obligation delegation" and must never drift from it;
# assurance + mirror checks only.
FLIP_CAPABILITIES = (
    "HITL patch application",
    "rollback execution",
    "governed demo loop",
    "interactive setup wizard",
    "governed obligation delegation",
    "deepagents runtime/subagents",
)
EXECUTOR_STAMP_ROW = "HITL patch application"


class Check:
    def __init__(self, name: str, ok: bool, detail: str) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail


def _rows_by_capability() -> dict[str, CapabilityRow]:
    return {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}


def check_count(checks: list[Check]) -> None:
    expected = state_counts(REQUIRED_CAPABILITY_ROWS)[OPERATIONALLY_VERIFIED]
    text = TRUTH_TEST.read_text(encoding="utf-8")
    m = re.search(r'operationally_verified_count"\]\s*==\s*(\d+)', text)
    if m is None:
        checks.append(Check("count pin", False, "could not locate operationally_verified_count assert"))
        return
    pinned = int(m.group(1))
    checks.append(
        Check(
            "count pin",
            pinned == expected,
            f"matrix OPERATIONALLY_VERIFIED={expected}, test pins {pinned}"
            + ("" if pinned == expected else "  <-- update the assert (and its comment)"),
        )
    )


def check_assurance(checks: list[Check]) -> None:
    rows = _rows_by_capability()
    text = TRUTH_TEST.read_text(encoding="utf-8")
    for capability in FLIP_CAPABILITIES:
        row = rows.get(capability)
        if row is None:
            checks.append(Check(f"assurance[{capability}]", False, "capability row missing from matrix"))
            continue
        expected = assurance_state_for_row(row)
        m = re.search(re.escape(f'rows["{capability}"]["assurance_state"] == "') + r'(\w+)"', text)
        if m is None:
            checks.append(Check(f"assurance[{capability}]", False, "no assurance assert found in truth test"))
            continue
        pinned = m.group(1)
        checks.append(
            Check(
                f"assurance[{capability}]",
                pinned == expected,
                f"matrix assurance={expected}, test pins {pinned}"
                + ("" if pinned == expected else "  <-- update the assert"),
            )
        )


def check_executor_stamps(checks: list[Check]) -> None:
    rows = _rows_by_capability()
    row = rows.get(EXECUTOR_STAMP_ROW)
    if row is None:
        checks.append(Check("executor stamps", False, f"{EXECUTOR_STAMP_ROW} row missing"))
        return
    expected = row.state
    text = EXECUTOR.read_text(encoding="utf-8")
    # The governance self-stamps that must mirror the matrix row state. Catch both the
    # dict-literal form (`"capability_state": "X"`) and the assignment form
    # (`receipt["governance"]["capability_state"] = "X"`), plus build_standard_governance("X").
    stamps = re.findall(r'build_standard_governance\("([A-Z_]+)"\)', text)
    stamps += re.findall(r'capability_state"\]?\s*[:=]\s*"([A-Z_]+)"', text)
    if not stamps:
        checks.append(Check("executor stamps", False, "no governance self-stamps found in executor"))
        return
    mismatched = sorted({s for s in stamps if s != expected})
    checks.append(
        Check(
            "executor stamps",
            not mismatched,
            f"matrix row state={expected}, executor stamps={sorted(set(stamps))}"
            + ("" if not mismatched else f"  <-- mismatched: {mismatched}"),
        )
    )


def check_mirror_doc(checks: list[Check]) -> None:
    # docs/PLATFORM_COMPLETION_AUDIT.md is the hand-maintained human mirror; test_platform_completion_audit
    # pins one `| capability | `state` | next_pr |` line per row. A flip that forgets it fails CI on
    # that doc, so the assistant checks it too.
    rows = _rows_by_capability()
    text = MIRROR_DOC.read_text(encoding="utf-8")
    for capability in FLIP_CAPABILITIES:
        row = rows.get(capability)
        if row is None:
            checks.append(Check(f"mirror[{capability}]", False, "capability row missing from matrix"))
            continue
        expected_line = f"| {capability} | `{row.state}` | {row.next_pr} |"
        present = expected_line in text
        checks.append(
            Check(
                f"mirror[{capability}]",
                present,
                f"expects `{expected_line}`"
                + ("" if present else "  <-- update the docs/PLATFORM_COMPLETION_AUDIT.md table row"),
            )
        )


def main() -> int:
    checks: list[Check] = []
    check_count(checks)
    check_assurance(checks)
    check_executor_stamps(checks)
    check_mirror_doc(checks)

    print("B4 flip consistency check (matrix = source of truth; this tool never writes)\n")
    for c in checks:
        print(f"  [{'PASS' if c.ok else 'MISMATCH'}] {c.name}: {c.detail}")
    ok = all(c.ok for c in checks)
    print("\n" + ("ALL PINNED SITES CONSISTENT WITH THE MATRIX." if ok else "MISMATCH — reconcile the sites above before committing the flip."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
