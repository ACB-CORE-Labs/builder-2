---
name: core-handoff
description: Write HANDOFF-grok43-YYYY-MM-DD.md using docs/handoff_template.md with exact test output, files touched, invariants verified, next steps.
---

# CORE Session Handoff

1. Read `docs/handoff_template.md`
2. Write `HANDOFF-grok43-YYYY-MM-DD.md` at repo root
3. Include: exact `builder verify` / pytest output, every file changed, invariants table, open tasks (specific), architectural decisions
4. No placeholders — this is the only continuity for stateless agents