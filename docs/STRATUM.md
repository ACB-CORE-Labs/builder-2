# STRATUM operator console

STRATUM is builder-II's experimental **Textual** instrument panel: observe governed state, compose exact CLI, hand off one Goose runtime. It is **not** an authority origin.

### Start command (preferred)

```bash
uv run builder-stratum
```

Opens the hero splash (~3s, any key skips), then the operator console. Same authority gate as `builder stratum --experimental`.

```bash
uv run builder-stratum --no-guide    # skip first-session walkthrough auto-open
uv run builder-stratum --guide       # force walkthrough
uv run builder-stratum --no-splash   # skip hero image
```

Equivalent long form:

```bash
uv run builder stratum --experimental
```

| Flag | Effect |
|------|--------|
| `--experimental` | **Required** on `builder stratum` (already implied by `builder-stratum`) |
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
| Command Composer (`~`) | Executor of composed commands |
| Suspend + fixed argv to `builder-goose start-readonly` | Spawner of raw `goose` or builtin chooser |
| Honest absence for chain digest (`—`) | Synthesizer of digests or fake tier grants |

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

In STRATUM: **C** shows a read-only projection of capability rows.

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

**G** auto-prepares local scaffolding when needed:

- ensures `.builder/{artifacts,goose,receipts}` exist
- if no valid `read_only` Goose session manifest is present, mints a passive
  `.builder/goose/stratum-auto-readonly.json` (same shape as `builder-goose manifest`)

Then STRATUM suspends and hands off to `builder-goose start-readonly` (still fail-closed on
command authority; start-readonly still does its own receipts and no-mutation postflight).

Optional: mint your own manifest instead of the auto file:

```bash
mkdir -p .builder/goose
uv run builder-goose manifest --target generic --mode read_only \
  --task "readonly inspect" --output .builder/goose/session.json
```

### 7. Launch STRATUM

```bash
uv run builder stratum --experimental
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
| **O** **U** **W** **C** **E** **T** **M** | Instruments |
| **?** | Palette · **~** composer |
| **P** **V** **G** **N** | Prepare compose · validate · goose · next |
| **A/R** | Compose HITL approve/reject (no mutation) |

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
Unimplemented mockup still named in the record: **HITL diff viewer**.
