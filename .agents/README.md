# .agents/ — Antigravity configuration for builder-II

This tree configures Gemini/Antigravity to preserve fast implementation while
imposing a stronger evidence/closure protocol. Uses **verified Antigravity paths
only** (`.agents/skills`, `.agents/agents`, `.agents/hooks.json`). There is no
`.antigravity/` config directory — Antigravity does not use one.

## Layout
- `agents/` — four personas (custom agents), switched via `/agents`:
  - `implementation-engineer` — default; fast recon → narrow patch → lesion → test.
  - `evidence-auditor` — skeptical, read-only; traces every claim to its production path.
  - `benchmark-scientist` — freezes methodology before observation; refuses proxies.
  - `final-closure-reviewer` — sole PASS authority; tries to falsify closure.
- `skills/` — slash-command workflows:
  - `core-plan-implementation` → `/core-plan-implementation`
  - `core-exact-tip-closure` → `/core-exact-tip-closure` (mandatory final gate)
  - (existing) `core-pre-edit-sweep`, `core-verify-loop`, `core-governed-coding`
- `hooks.json` — mechanical gates:
  - `qualification-gate` (`PreToolUse`, matcher `run_command`) — forces review of
    qualification/benchmark commands unless a frozen manifest + clean exact tip exist.
  - `closure-stop-gate` (`Stop`) — forces `/core-exact-tip-closure` + the GEMINI.md
    pre-completion checklist before allowing stop.
- `scripts/` — hook handlers (STUBS). Wire these to `builder_ii_validation_rs`:
  - `qualification_gate.sh`
  - `closure_stop_gate.sh`

## Verified vs inferred
- VERIFIED: skill/agent file locations, `name`/`description` frontmatter, skills→slash
  commands, hooks.json events (`PreToolUse`/`Stop`) + `decision` values, `define_subagent`.
- INFERRED/unverified on Antigravity: `agent.md` richer frontmatter (`tools`, `model`,
  `hooks`, …) and `SKILL.md` `allowed-tools`. Hard tool authority should come from
  `settings.json` (`toolPermission`, `enableTerminalSandbox`) + hooks, not these fields.
- Config (GEMINI.md/agent.md) is advisory. Mechanical enforcement still requires
  repo-level validators in `builder_ii_validation_rs`; the hook scripts call them.

## Adjacent config (not in this tree)
- `GEMINI.md` (repo root) — always-loaded evidence/claim discipline + this index.
- `AGENTS.md` (repo root, pre-existing) — canonical governance; Antigravity reads it
  natively; Gemini CLI loads it via `@AGENTS.md` in GEMINI.md.
- `~/.gemini/antigravity-cli/settings.json` — set `toolPermission: proceed-in-sandbox`,
  `enableTerminalSandbox: true`, network off (or use Project-level settings).