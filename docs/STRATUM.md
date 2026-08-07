# STRATUM operator console

STRATUM is builder-II's experimental **Textual** instrument panel: observe governed state, compose exact CLI, hand off one Goose runtime. It is **not** an authority origin.

### Start command (preferred)

```bash
uv run builder-stratum
```

Opens the hero splash (~3s, any key skips), then the operator console. Gated by the
command-authority registry's `builder stratum` record on every launch path (`builder stratum`,
`builder-stratum`, `builder-platform tui`, `python -m builder_ii.tui`) — there is no flag that
skips or is required for this; the registry is consulted unconditionally.

```bash
uv run builder-stratum --no-guide    # skip first-session walkthrough auto-open
uv run builder-stratum --guide       # force walkthrough
uv run builder-stratum --no-splash   # skip hero image
```

Equivalent long form:

```bash
uv run builder stratum
```

| Flag | Effect |
|------|--------|
| `--no-guide` | Skip first-session walkthrough auto-open |
| `--guide` | Force walkthrough open (even if dismissed before) |
| `--no-splash` | `builder-stratum` only: skip opening hero |

**Splash quality (macOS):** by default STRATUM floats the real `images/builder-ii-splash-hero.jpeg`
in a borderless Cocoa window (~3.5s) via `swift` — full image quality, not terminal pixels.
Disable native: `BUILDER_SPLASH_NATIVE=0`. Opt into low-res terminal image: `BUILDER_SPLASH_TERMINAL_IMAGE=1`.

Env opt-out: `STRATUM_SKIP_GUIDE=1`  
In-app opt-out: press **X** while the walkthrough is open (writes `.builder/stratum_guide_dismissed`).  
Re-open anytime: **0**

Full reference: in-app **H** (multi-page help).

**New builders:** start with [`GETTING_STARTED.md`](GETTING_STARTED.md) (setup order, STRATUM map, and how to configure **recipes**, **deepagents**, **orchestration**, and **models/providers**).  
Smoked CLI loop: [`FIRST_SESSION.md`](../FIRST_SESSION.md). Golden path / demos: [`OPERATOR_QUICKSTART.md`](OPERATOR_QUICKSTART.md).

---

## What STRATUM is / is not

| Is | Is not |
|----|--------|
| Read-only view of registries + `.builder/artifacts` | Writer of session/HITL/assignment artifacts |
| Command Composer (`C`) | Executor of composed or arbitrary commands |
| Suspend + fixed argv to `builder-goose start-readonly` (**G**) | Spawner of raw `goose` or builtin chooser |
| Governed run dispatcher (**Ctrl+G**): fixed argv to `builder-goose run-governed`, behind grant-or-confirm | Originator of authority for the run it starts |
| Honest absence for chain digest (`—`) | Synthesizer of digests or fake tier grants |

### On HITL decisions (A / R)

The gate keys reach `builder-hitl` directly now instead of composing a line to paste. They do it by
**suspending and handing over the terminal**, which is deliberate: `approve-patch` prints the patch
digest and asks the operator to type its prefix, and that typed prefix *is* the approval evidence.
A console that collected it would be manufacturing the very thing the artifact claims a human
supplied — so STRATUM gets the operator to the decision and never makes it for them.

This is also why patch approval can **never** be covered by a standing ratification grant: the
point is registered `human_approval_mint`, and the registry structurally refuses a grantable kind
for anything under `builder-hitl`. Dispatch is delegable; deciding is not.

The keys are gated on the affordance projection (`tui/projections/authority.py`). A command the
registry does not derive `invoke_direct` for falls back to composing, exactly as before, and an
unbound gate still refuses without offering anything.

### On dispatch (Ctrl+G)

STRATUM can now start governed work: type a task, and it mints a passive `read_only` session
manifest (delegated to a non-TUI module — `builder_ii/tui/` still writes no files) and spawns
`builder-goose run-governed` with a fixed argv, `shell=False`, **without suspending**. The run
streams onto the hash-chained session ledger the run cockpit already tails, so it is watchable
while it happens.

Starting work is not authorizing it. Everything that decides permissibility happens elsewhere and
again: `enforce_command_authority` before anything is minted, the governed CLI's own manifest
validation (anything not `read_only` is refused before a process exists), the MCP server's
per-call deny-by-default policy with its path-jailed read-only tool set, and the no-mutation
postflight that fails the run on any content digest that moved.

**Where the pause goes is the operator's choice, not the console's.** The dispatch consults the
ratification point `stratum.dispatch.goose_run`:

- a standing grant covers it → the run proceeds, and the toast names the grant so the operator can
  see (and `builder-govern revoke`) what is answering for them;
- no grant → a `ConfirmScreen` naming the task, the manifest path and digest, and the exact argv;
- policy demands an approval artifact → refused, with `builder-govern approve` composed.

Both branches emit the same artifacts, receipts and chained events. The auto-ratified branch
additionally records the grant digest on the ratification ledger, so it is *more* traceable than
the prompted one, never less. See [`RATIFICATION_GRANTS.md`](RATIFICATION_GRANTS.md).

**Artifact root:** `<project_root>/.builder/artifacts` for the process you launched. Another clone = another empty or different spine.

---

## First-session walkthrough (verified commands)

Run these in a terminal from the **same** repo root you will use for STRATUM.

### 1. Install

```bash
uv sync
```

### 2. Platform truth matrix

```bash
uv run builder-platform matrix
```

In STRATUM: **Z** shows a read-only projection of capability rows.

### 3. Operator next

```bash
uv run builder-platform next
```

In STRATUM: **N** composes the top safe command (does not run it).

### 4. Prepare package (fills the spine)

```bash
uv run builder-session prepare-package generic -o .builder/session --task "first stratum session"
```

STRATUM **P** only collects choices and composes this family of command — it does not write the package.

### 5. Validate prepare package

```bash
uv run builder-session validate-prepare-package .builder/session
```

In STRATUM: **V** re-checks on-disk chain validity and composes the validate command.

### 6. Read-only Goose (G)

**G** behavior:

1. If a valid `read_only` Goose session manifest already exists under `.builder/goose` → hand off
   immediately to `builder-goose start-readonly`.
2. If none exists → **ask** (ConfirmScreen) before writing anything. On **yes**:
   - ensures `.builder/{artifacts,goose,receipts}`
   - mints passive `.builder/goose/stratum-auto-readonly.json`
   - then hands off to `start-readonly`
3. On **no** / cancel → opens the command composer with a manual `builder-goose manifest …` line
   (STRATUM still does not run it).

Still fail-closed on command authority; start-readonly still does its own receipts and
no-mutation postflight. Auto-prep never runs silently.

Optional: mint your own manifest so **G** skips the prompt:

```bash
mkdir -p .builder/goose
uv run builder-goose manifest --target generic --mode read_only \
  --task "readonly inspect" --output .builder/goose/session.json
```

### 7. Launch STRATUM

```bash
uv run builder stratum
# skip guide:  --no-guide
# force guide: --guide
```

---

## Keymap (essentials)

| Key | Action |
|-----|--------|
| **0** | First-session walkthrough |
| **H** / **F1** | Help ( **[** / **]** pages: keymap · walkthrough · boundaries ) |
| **X** | Dismiss walkthrough auto-open (when guide is open) |
| **TAB** | Cycle Spine · Center · Signals |
| **j/k** | Spine move · **SPC** pin/inspect |
| **O** **U** **W** **Z** **E** **T** **M** | Instruments |
| **?** | Palette · **C** composer |
| **P** **V** **G** **N** | Prepare compose · validate · goose (interactive, suspends) · next |
| **Ctrl+G** | Run a governed task: type it, dispatch, stream in the cockpit (no suspend) |
| **L** | Run cockpit: runs roster + live ledger transcript ( **, .** select run ) |
| **A/R** | HITL approve/refuse — suspends and hands the terminal to `builder-hitl`, which asks for the digest prefix · **D** diff (read-only) |

---

## Reading the spine and chain bar

- **Empty / dim stages:** that kind is not present under *this* tree’s artifacts.
- **Chain valid FALSE:** `verify_artifact_chain` found invalid or schema-drifted files — inspect errors outside STRATUM; do not invent green.
- **DIGEST —:** verification report exposes no ambient chain digest; absence is intentional.
- **AUTH NOT EVALUATED:** STRATUM does not grant authority.

---

## Configuring work (recipes / agents / models)

STRATUM does not install recipes or providers. Use CLI + files, then inspect:

| Topic | Outside STRATUM | Inside STRATUM |
|-------|-----------------|----------------|
| Goose recipes + manifest | Edit `recipes/**/*.yaml`; `builder-goose manifest` | **W** recipes + manifest status + compose; **G** hand-off |
| Deepagents | `forge`, `readiness`, `work-plan`, `assign-subagent` | **U** roster/readiness + compose catalog; again for assign picker |
| Orchestration | `plan` → validate → dry-run → obligations | **Y** plans/obligations + compose |
| Models / providers | `.env` `BUILDER_MODEL_*`; `builder-model-policy`; `builder models` | **O** local config + registry + routing + compose |
| CodeVault | `builder-code-vault` demo/frame/status | **B** frames + compose |
| HITL | `builder-hitl *` | Rail gate light; **I** bind pending; **A/R** compose only |

Full how-to: [`GETTING_STARTED.md` §5](GETTING_STARTED.md#5-how-builder-ii-configures-work).

## Troubleshooting

| Symptom | Cause | What to do |
|---------|--------|------------|
| Spine empty in worktree | No JSON in that worktree’s `.builder/artifacts` | Run prepare-package *here*, or launch STRATUM from the tree that has artifacts |
| `awaiting_generation` on pin | Kind not on disk | Emit artifact via CLI, then pin again |
| `BadIdentifier` on agents | Fixed: profile names with `.` sanitized for widget ids | Use current `teaming.py` |
| Toast `builder builder-platform…` | Fixed: compose normalizer | Prefer `builder-platform …` / `uv run …` |
| Guide keeps returning | Dismiss file missing / not using --no-guide | **X** or `--no-guide` or `STRATUM_SKIP_GUIDE=1` |

---

## Governance record

Command authority: `builder stratum` (TIER_2, operator-managed, experimental).  
The **HITL diff viewer** (**D**) renders the bound patch proposal's unified diff read-only; it applies nothing.
