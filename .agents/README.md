# .agents/ — Antigravity configuration for builder-II

This tree configures Gemini/Antigravity advisory guidance for builder-II
development. It uses verified Antigravity paths only (`.agents/skills` and
`.agents/agents`). There is no `.antigravity/` config directory — Antigravity
does not use one.

Builder-II has not been admitted to govern its own development. Project-level
PreToolUse and Stop hooks are therefore intentionally absent: they would turn
unfinished Builder-II closure conventions into repeated authority prompts. The
skills and agent personas below remain advisory; ordinary development uses direct
repository work, focused tests, final local CI, and normal Git review.

## Layout
- `agents/` — four personas (custom agents), switched via `/agents`:
  - `implementation-engineer` — default; fast recon → narrow patch → lesion → test.
  - `evidence-auditor` — skeptical, read-only; traces every claim to its production path.
  - `benchmark-scientist` — freezes methodology before observation; refuses proxies.
  - `final-closure-reviewer` — advisory final reviewer; tries to falsify closure.
- `skills/` — slash-command workflows:
  - `core-plan-implementation` → `/core-plan-implementation`
  - `core-exact-tip-closure` → `/core-exact-tip-closure` (advisory final review)
  - (existing) `core-pre-edit-sweep`, `core-verify-loop`, `core-governed-coding`

## Verified vs inferred
- VERIFIED: skill/agent file locations, `name`/`description` frontmatter, skills→slash
  commands, and `define_subagent`.
- INFERRED/unverified on Antigravity: `agent.md` richer frontmatter (`tools`, `model`,
  `hooks`, …) and `SKILL.md` `allowed-tools`. Hard tool authority should come from
  host settings and the admitted Builder-II product surface, not these fields.
- Config (GEMINI.md/agent.md) is advisory. Mechanical enforcement for external
  target repositories belongs to Builder-II after separate admission, not to this
  repository's bootstrap development configuration.

## Adjacent config (not in this tree)
- `GEMINI.md` (repo root) — always-loaded evidence/claim discipline + this index.
- `AGENTS.md` (repo root, pre-existing) — canonical governance; Antigravity reads it
  natively; Gemini CLI loads it via `@AGENTS.md` in GEMINI.md.
- `~/.gemini/antigravity-cli/settings.json` — set `toolPermission: proceed-in-sandbox`,
  `enableTerminalSandbox: true`, network off (or use Project-level settings).
