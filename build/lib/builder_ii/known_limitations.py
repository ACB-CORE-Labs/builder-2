"""Known-limitations document generated from the completion truth matrix (plan item 4.2).

The matrix (``platform_completion_audit.REQUIRED_CAPABILITY_ROWS``) is the source of truth for
what is and is not operational; this module renders the beta-facing "what this will NOT do for
you" view of it. The committed ``docs/KNOWN_LIMITATIONS.md`` must equal this renderer's output —
a pinned test enforces that, so the document cannot drift from the matrix (same pattern as
``docs/COMMAND_AUTHORITY.md``).

The verification-lane scope language below is the ratified D7 wording: the bounded runner
constrains *what gets invoked*, never *what invoked code can do*. It must never be described as
a sandbox.
"""

from __future__ import annotations

from builder_ii.platform_completion_audit import (
    OPERATIONALLY_VERIFIED,
    REQUIRED_CAPABILITY_ROWS,
    CapabilityRow,
    assurance_state_for_row,
    state_counts,
)

KNOWN_LIMITATIONS_DOC_PATH = "docs/KNOWN_LIMITATIONS.md"

_HEADER = """\
# Known Limitations

What builder-II will NOT do for you today. Generated from the completion truth matrix
(`builder_ii/platform_completion_audit.py`) by `builder-platform known-limitations`; a pinned
test fails CI if this document drifts from the matrix. Regenerate with:

```bash
uv run builder-platform known-limitations --output docs/KNOWN_LIMITATIONS.md
```

For the full per-capability view (including what IS verified), see
[`docs/PLATFORM_COMPLETION_AUDIT.md`](PLATFORM_COMPLETION_AUDIT.md); for what feedback the beta
wants, see [`docs/BETA_CHARTER.md`](BETA_CHARTER.md).
"""

_VERIFICATION_SCOPE = """\
## Verification-lane target scope (read this one first)

The HITL-approved verification lane (`builder-verify run-approved`) and every surface built on
it target **trusted local Python-with-pytest repositories only**.

- The bounded runner constrains **what gets invoked** — fixed argv, `shell=False`,
  env-allowlisted subprocess, digest-bound approval, range-checked timeout. It never constrains
  **what invoked code can do**: running pytest over a repository executes that repository's code
  (including transitive `conftest.py` and plugin code) on your host with your user privileges.
- It is **not a sandbox**, and no builder-II surface may describe it as one. Target-code-executing
  profiles require a schema-enforced execution-risk acknowledgment on the approval artifact
  before the runner will spawn anything.
- Container/VM isolation is post-beta ladder work. Until then: do not point verification lanes at
  repositories you would not run on your machine yourself.

The same trust boundary applies to the governed demo loop's target repositories: the demo mutates
only a disposable detached worktree, but preflight and repo scanning still read the repository you
designate.
"""

_STANDING_BOUNDARIES = """\
## Standing non-authority boundaries (by design, not by gap)

These are not missing features; they are refusals the governance model depends on:

- No commit or push automation, ever, in any lane.
- No autonomous writes: every mutation lane requires an explicit digest-bound operator approval.
- No hidden memory or vector stores; artifact memory is explicit, validated, and replayable.
- Model output is never approval; a valid artifact is never authority; subagent output is never
  truth.
- Receipts are digest-chained evidence for review, not cryptographic proof — builder-II makes no
  signature claims.
"""

_ASSURANCE_NOTE = """\
## How to read `OPERATIONALLY_VERIFIED`

`OPERATIONALLY_VERIFIED` is a per-capability state, never a platform-wide clearance. Each
verified row carries a sharper `assurance_state` (e.g. `MUTATION_WITH_ROLLBACK_VERIFIED`,
`DEMO_ONLY_VERIFIED`, `PASSIVE_ARTIFACT_VERIFIED`) that is authoritative for risk
interpretation — a live provider call, a temporary demo loop, and a passive artifact renderer
are not equivalent just because they share the legacy completion label.
"""


def _limitation_lines(rows: tuple[CapabilityRow, ...]) -> list[str]:
    lines: list[str] = []
    for row in rows:
        if row.state == OPERATIONALLY_VERIFIED:
            continue
        lines.append(f"- **{row.capability}** — `{row.state}` (assurance `{assurance_state_for_row(row)}`)")
        for blocker in row.blockers:
            lines.append(f"  - {blocker}")
    return lines


def render_known_limitations_markdown(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> str:
    counts = state_counts(rows)
    verified = counts[OPERATIONALLY_VERIFIED]
    not_verified = len(rows) - verified
    sections = [
        _HEADER,
        _VERIFICATION_SCOPE,
        _STANDING_BOUNDARIES,
        _ASSURANCE_NOTE,
        (
            "## Not operational today (from the matrix)\n\n"
            f"{verified} of {len(rows)} matrix capabilities are operationally verified; the "
            f"{not_verified} below are not. Each entry lists the matrix state and its recorded "
            "blockers verbatim.\n\n" + "\n".join(_limitation_lines(rows)) + "\n"
        ),
    ]
    return "\n".join(sections)
