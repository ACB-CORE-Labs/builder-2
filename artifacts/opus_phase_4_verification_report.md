# Phase 3 & 4 — TUI Semantic Verification Report

- **Subject:** PR #163 (`tui-claude-exploration-driver` → `main`), merged as `2990a59`
- **Base verified:** `2990a59e86e67ff4566712d36e1048c88c425c0c`
- **Worktree:** `.claude/worktrees/tui-opus-phase-3-4`, branch `claude/tui-opus-phase-3-4`
- **Method:** Textual `run_test(headless=True)` semantic DOM via `scripts/semantic_tui_driver.py`. **Zero `pexpect`.** No ANSI/visual scraping.
- **Status:** findings below are **measured, not self-certified**. See §7.
- **HITL:** operator approved items 1–3 on 2026-07-16 and deferred item 4 (`pexpect` retirement). Executed in §5; decision record in §8.

---

## 1. Verdict

The brief stated the palette vulnerabilities were "surgically neutralized" in PR #163. **Partially true, and the untrue part is the dangerous one.**

| Claim under test | Verdict | Evidence |
|---|---|---|
| Palette no longer misreports commands as `UNKNOWN` | **CONFIRMED** | 463/463 entries carry a real tier badge; 0 render `??` |
| JSONL ledger captures commands + modal transitions | **CONFIRMED** | `SplashScreen → Screen → CommandPaletteScreen`, 468 widgets at modal |
| Command authority "hardcoded string tier literals eradicated" | **FALSE** | `app.py:462` still compared prose to `"TIER_3"`; **0 of 29** flagged |
| Semantic driver free of `pexpect` | **CONFIRMED** (with caveat) | `semantic_tui_driver.py` clean; legacy `scripts/tui_driver.py` still uses it (§6, deferred) |
| Ledger is deterministic | **PARTIAL → FIXED** | state payload was already byte-identical; the `digest` was not, and now is (§3.4) |

**PR #163 fixed the tier *label* and left the authority *flag* dead.** Pre-fix, every command rendered `??`/UNKNOWN — loudly, visibly broken. Post-fix the surface looks authoritative and correct while silently under-reporting authority on 29 commands. **A fix that removes the visible symptom while leaving the invisible defect converts a loud failure into a silent one.** That is a net regression in operator trust even though the diff is an improvement.

---

## 2. Root cause: the fix was applied by a blind regex codemod

`fix_all.py` (156 lines, repo root, **tracked in `main`**, introduced by `e7766a6 "Merge main and fix conflicts"`) is a scratch `re` + `Path.read_text().replace()` codemod. It is the instrument that produced PR #163, and it is committed.

It substituted `"TIER_X"` → `TIER_X` **by text pattern, with no notion of which vocabulary each site belonged to.** One mechanism explains every outcome:

| Site | Matched? | Right vocabulary? | Result |
|---|---|---|---|
| `palette.py::_tier_labels()` | yes | yes | **correctly fixed** |
| `palette.py::_build_entries()` defaults | yes | yes | **correctly fixed** |
| `app.py::HeaderBanner.tier` | yes | **no** — model tier | **corrupted** |
| `test_stratum_tui.py` ×5 `model_tier` mocks | yes | **no** — model tier | **corrupted** |
| `app.py:462 rec.tier in ("TIER_3","TIER_4")` | **no** — tuple form | yes | **missed** |

The codemod fixed what matched, corrupted what matched but meant something else, and missed the one site whose *syntax* differed. There are two unrelated tier vocabularies in this codebase and a regex cannot see the difference:

- `command_authority.VALID_TIERS` — values are **prose**: `TIER_3 == "Tier 3 — HITL-gated execution candidate"`
- `config.MODEL_TIERS == ("primary", "fast")` — a **closed** set, enforced at `config.py:327` with a `ValueError`

---

## 3. Confirmed defects

### 3.1 `requires_authority` was dead — 0 of 29 (**FIXED**, was **HIGH**)

`app.py:462` computed `rec.tier in ("TIER_3", "TIER_4")`. `rec.tier` values are prose, so **the comparison can never be true.**

Registry ground truth (no TUI involved):

```
records                          : 463
rec.tier in ("TIER_3","TIER_4")  ->  0    <- what app.py:462 computed
rec.tier in (TIER_3, TIER_4)     -> 29    <- ground truth
sample rec.tier                  : 'Tier 2 — operator-managed setup/runtime helper'
```

Semantic DOM agrees independently — `⚡` was unreachable dead code:

```
                    entries   ⚡ flagged   badges
BEFORE (main)     :   463        0        {T0:77, T1:317, T2:40, T3:26, T4:3}
AFTER  (fixed)    :   463       18        {T0:77, T1:317, T2:40, T3:26, T4:3}
```

**On 18 vs 29 — the fix is complete; the naive expectation was wrong.** `PaletteEntry.render()` has two branches, and only the permitted branch emits `auth_glyph`; a refused command shows `⊘ <reason>`. A TIER_4 command therefore *structurally cannot* render `⚡` — all three are `allowed=False`. Reconciled against the registry:

```
authority-requiring (T3+T4) : 29
  permitted -> render ⚡     : 18
  refused   -> render ⊘     : 11   (3×T4 + 8×T3)
DOM measured : 18 ⚡ + 11 ⊘ = 29
Registry     : 18 ⚡ + 11 ⊘ = 29     RECONCILED: True
```

Both displays are truthful. The flag is now correct for all 29.

### 3.2 The covering lane did not exist (**FIXED**, was **HIGH**)

`grep -rn "requires_authority|⚡" tests/` returned **nothing**. That is why the defect survived a PR that edited the same file. Per `CLAUDE.md` §6.5: *no covering lane = a finding*.

Worse, the test *named* `test_stratum_palette_authority` is fiction — it mocks away the exact thing under test:

- `mock_registry.__iter__.return_value = [mock_record]` — replaces 463 real records with **one** `MagicMock`
- `mock_record.tier = TIER_0` — the TIER_3/TIER_4 path is never exercised
- `mock_check` replaces `check_command_authority`, the governance decision itself
- asserts `cmd["reason"] == "mock reason"` — i.e. that its own fixture echoes back

**Mutation proof** (both lanes, same broken tree, `reproduce.sh` §C):

| Lane | vs BROKEN code | vs FIXED code | Detection power |
|---|---|---|---|
| `test_stratum_palette_authority` (mocked) | **PASS** | PASS | **zero** |
| `test_palette_flags_every_authority_requiring_command_in_the_real_registry` (new) | **FAIL** | PASS | real |

The full suite was **green throughout** (2316 passed) with 29/29 authority flags dead. *"Tests pass"* was never evidence here.

### 3.3 `HeaderBanner.tier` holds a foreign vocabulary (**FIXED**, **LOW** — latent)

PR #163 set `app.py:50` to `command_authority.TIER_0`. But `app.py:220` does `self.banner.tier = self.settings.model_tier`, and `settings.model_tier ∈ MODEL_TIERS == ("primary","fast")`.

**Not a live regression** — line 220 overwrites it at mount, and the live header correctly renders `primary` (verified in DOM). The defect is that the field's default is a value `load_settings` would itself **reject**, and it implies to the next reader that this slot displays authority tier. Fixed to `"unknown"`, mirroring the sibling `self.model` placeholder.

### 3.4 Ledger `digest` hashes the wrong thing (**FIXED**, was **MEDIUM**)

The `state` payload **is** deterministic — two runs of an identical mount serialise byte-identically (`af123f135e81a838`). The driver then folds `uuid4` `run_id` and `time.time()` **into the digest**:

```
run1 MOUNT state sha : af123f135e81a838
run2 MOUNT state sha : af123f135e81a838     IDENTICAL STATE: True
run1 digest          : 04eb53882b3e1c1f
run2 digest          : 7e82a089ebdad787     digest equal: False
```

So the digest answered *"which run was this?"*, never *"did the UI change?"* — destroying the one property that makes a ledger diffable run-over-run, when the deterministic state needed for a real state digest was already in hand. There was also no `prev_digest` chain: lines could be **deleted or reordered undetected**, despite the "immutable, append-only" claim.

**Fixed with two digests, not one — a deliberate deviation from the literal directive.** `state_digest` binds only the `state` payload (identical states → identical digests → diffable). `entry_digest` binds the whole entry *including* `prev_digest`, and is the chain link. Had a single state-bound digest doubled as the link — the literal reading of "rebind the digest to the state payload" — the chain would be **forgeable**: the digest would not commit to `prev_digest`, so deleting line N and re-pointing line N+1 at line N-1 would leave every digest still verifying. The split is what delivers the *stated intent* ("guaranteeing that lines cannot be deleted or reordered undetected"), which the single-field version does not.

Verified — the chain now spans the file, and two runs of the same splash mount emit the same `state_digest`:

```
seq=0 MOUNT  run=c3b60e44 prev=None     entry=081c78a4 state=5b18ce08
seq=1 ACTION run=c3b60e44 prev=081c78a4 entry=15090da3 state=2b506696
seq=2 ACTION run=c3b60e44 prev=15090da3 entry=91b951de state=35f267b1
seq=3 MOUNT  run=4d9c2913 prev=91b951de entry=1cf4ba57 state=5b18ce08   <- different run, same state_digest
seq=4 ACTION run=4d9c2913 prev=1cf4ba57 entry=f0312548 state=25cb8fc0
```

Tamper matrix — every case **DETECTED**, pinned in `tests/test_tui_audit_ledger.py` (19 lanes):

| Tamper | Caught by |
|---|---|
| delete an event | `seq` position mismatch |
| reorder two events | `seq` position mismatch |
| edit the state payload | `state_digest` mismatch |
| edit state **+** recompute `state_digest` | `entry_digest` mismatch |
| **delete + re-point `prev_digest` + renumber `seq`** | `entry_digest` mismatch ← the forgery the split exists to stop |

### 3.5 `builder_ii.tui_audit_ledger_event` was a half-built artifact (**FIXED**, was **MEDIUM**)

The kind had **no paired `validate-*`** and **no `docs/ARTIFACT_INDEX.md` entry**. Repo doctrine is *artifact → digest → paired validator → downstream consumes*.

Added `scripts/validate_tui_audit_ledger.py` and registered the kind in `docs/ARTIFACT_INDEX.md` (`builder-platform audit-docs` passes). It is a plain script like its sibling `scripts/validate_tui_exploration.py`, so it adds **no `[project.scripts]` entry and therefore no `command_authority` surface** — `tests/test_command_authority.py` enforces that every console script carries an authority record, and a dev-facing validator should not buy a governed surface it does not need. Same reasoning `gate_battery_receipt` records for its own `python -m` validator.

Digest computation lives in `builder_ii/governance/ledger/tui_audit_ledger.py` and is imported by **both** writer and validator. A validator re-implementing the writer's hashing cannot detect drift between them — it only proves two copies of the same bug agree.

The ledger still writes to `.builder/`, gitignored at `.gitignore:9`, so it remains ephemeral by design; `reproduce.sh` regenerates it.

### 3.6 `fix_all.py` committed to repo root (**FIXED** on approval, was **HIGH** — hygiene)

Originally surfaced rather than acted on: **I did not author it.** Removed under operator approval (`3811bd6`); recoverable from history. Dead code that rewrites source files by regex if executed, and its stale duplicate of the ledger code made `grep` for the artifact kind return a phantom second implementation.

---

## 4. Determinism: "100% deterministic" is not achievable as stated

Measured across identical runs — **22 of 24 main-screen widgets are byte-identical**. The two that differ do so **by construction**:

| Widget | Why it cannot be deterministic |
|---|---|
| `stratum-header` | renders `datetime.now().strftime("%H:%M")` |
| `mechanical-sympathy` | renders live host RAM |

Redacting them would make the ledger lie about what the UI shows. Reported rather than suppressed. The splash-screen mount (no clock, no HUD) **is** fully deterministic, which is what §3.4's state digest would bind.

---

## 5. Changes made in this phase

| Commit | File | Change |
|---|---|---|
| `635e72a` | `builder_ii/tui/app.py` | `requires_authority` bound to `TIER_3`/`TIER_4` constants (§3.1); `HeaderBanner.tier` → `"unknown"`, bogus `command_authority` import dropped (§3.3) |
| `635e72a` | `tests/test_stratum_tui.py` | 5 `model_tier` mocks → `"primary"` (a real `MODEL_TIERS` value); **+3 lanes** |
| `3811bd6` | `fix_all.py` | **deleted** (§3.6) |
| `98f68d4` | `builder_ii/governance/ledger/tui_audit_ledger.py` | **new** — `state_digest`/`entry_digest`/`prev_digest`, chain head resume, validator (§3.4) |
| `98f68d4` | `scripts/validate_tui_audit_ledger.py` | **new** — the paired validator (§3.5) |
| `98f68d4` | `scripts/semantic_tui_driver.py` | writes chained events; payload key unified to `state`; dead `get_inspection_app` import dropped |
| `98f68d4` | `docs/ARTIFACT_INDEX.md` | registers `builder_ii.tui_audit_ledger_event` |
| `98f68d4` | `tests/test_tui_audit_ledger.py` | **new** — **+19 lanes**, full tamper matrix |
| `c30e8ce` | `scripts/semantic_tui_driver.py` | legacy-ledger refusal as structured JSON; optional `ledger_path` (§5.1) |
| `c30e8ce` | `tests/scenarios/test_tui_exploration.py` | ledger isolated to `tmp_path`; **+2 lanes** (§5.1) |

### 5.1 Two defects the chain introduced — caught by verifying, not by reviewing

Both were found by running the gates against the **committed** tree, and neither would have been visible in the diff:

1. **The driver died with a traceback on any pre-existing ledger.** Every ledger already on disk predates the chain and carries no `entry_digest`, so `read_chain_head` raised out of `run_exploration`. Refusing is correct — appending to an unverifiable tail leaves a gap nothing could later detect — but a raw `ValueError` breaks the driver's "always emits JSON" contract, on first run after upgrade, for precisely the people who had used it before. Now `{"error": "LEDGER_CHAIN_UNREADABLE", ...}` naming the remedy.
2. **The chain made the ledger path load-bearing, and a test depended on it.** `test_semantic_tui_driver_initial_state` invoked the driver in the repo, so it wrote to the real gitignored `.builder/` ledger on every suite run and could be failed by a stale file having nothing to do with the driver — which is exactly how it failed once here. The driver now accepts `ledger_path`; the tests use `tmp_path`.

The second is the more instructive: a change to *how state is recorded* silently coupled an unrelated test to accumulated disk state. Nothing about the diff said so.

New lanes — each **derives** its expectation from the real registry and **refuses to pass vacuously**:

1. `test_palette_flags_every_authority_requiring_command_in_the_real_registry` — drives the real registry; asserts `expected` non-empty *first*, because `set() == set()` would otherwise pass while proving nothing.
2. `test_palette_tier_labels_cover_exactly_the_registry_vocabulary` — set equality with `VALID_TIERS` in both directions; a sixth tier cannot be added without a label, and no label may claim a tier the registry cannot emit.
3. `test_header_model_tier_is_not_a_command_authority_tier` — pins the two vocabularies disjoint.

**Untouched:** `mock_record.tier = TIER_0` (correct vocabulary — command-authority record tier).

---

## 6. Open findings — NOT fixed, no authority claimed

| # | Finding | Sev |
|---|---|---|
| — | **DEFERRED by operator:** `scripts/tui_driver.py` still uses `pexpect`; CLAUDE.md documents it as the smoke path. Retiring it touches `docs/CAPABILITY_PROMOTION.md` — a promotion boundary, handled in a dedicated governance sweep | MED |
| — | `scripts/semantic_tui_driver.py:56` swallows render exceptions (`except Exception: pass`), so a widget that cannot render is indistinguishable from one with no text — silent omission reported as absence. Out of approved scope | MED |
| — | The driver skips `display=False` widgets entirely, so "hidden" and "absent" are indistinguishable in the ledger | LOW |
| — | Driver has no text truncation; a large render can flood the ledger and any reader's context | LOW |
| — | Driver's `notify` hook hardcodes `timeout=5.0`, overriding Textual's `NOTIFICATION_TIMEOUT` default; the observer mutates the observed | LOW |
| — | Driver reports `status:"success"` for a keypress that did nothing (splash ate `?`; see §7 log) | ~~LOW~~ → **fixed**, see §9 |
| — | `SplashScreen` consumes the first keypress; driver cannot pass `show_splash`/`skip_guide`, so every run burns one | ~~LOW~~ → **CRITICAL, misrated here.** See §9.1 |
| — | `palette.py` docstring says "fuzzy search"; `on_input_changed` implements substring | LOW |
| — | `PaletteEntry`/`SpineItem`/`CapabilityItem`/~~`FooterKey`~~ all have `id=None` — unaddressable by selector | ~~LOW~~ → **fixed**; `FooterKey` misattributed, see §9.2 |
| — | `PaletteEntry.render()` unknown-tier fallback uses `p["dim"]` (fail-open); should render `p["fail"]` | LOW |
| — | Pre-existing Pyright errors in `app.py` (`push_screen` callback variance). Not in CI's gate set | INFO |

---

## 7. Governance statement — this report does not certify itself

Per the brief's *"do not self-certify correctness"*:

- **The gate receipt is not proof.** `artifacts/opus_phase_4_evidence/gate_receipt.json` is `capability_state: RECORDED_ONLY`, and its own governance block hard-pins `artifact_is_authority: false`, `independent_observer: false`, `merge_authority: operator`. The same host that ran the gates wrote the receipt. It closes transcription error, commit mismatch and dirty-tree ambiguity. **It does not close dishonesty.**
- **The receipt certifies the committed tree, and says which one.** `working_tree_clean: true`, `head_sha_before == head_sha_after == c30e8ce`, 9/9 gates exit 0. An earlier run of the same battery reported `working_tree_clean: false` at `2990a59` — green on a *dirty* tree, which proves nothing about any commit. That is why the battery was re-run after committing rather than the first receipt being shipped. A receipt cannot certify the commit that contains it; this one certifies its parent.
- **The load-bearing evidence is adversarial, not affirmative.** The strongest result here is that the codebase's *own* test suite passes on broken code (§3.2). That is evidence *against* the suite — the opposite of self-certification.
- **Independently reconcilable.** The DOM measurement (18 `⚡`) and the registry (18 permitted) are separate sources that agree. Every number is regenerable by a third party: `bash artifacts/opus_phase_4_evidence/reproduce.sh`.
- **One prior claim of mine was wrong and is retracted.** In the previous audit I reported TAB focus-cycling as a permanent no-op. It was a false positive — a completed 5-widget focus lap misread as zero movement. `action_cycle_focus` is genuinely unreachable (Screen resolves `tab` before App), but focus *does* cycle. Recorded here because an audit that hides its own errors is not an audit.

Gates: `9/9 PASSED` at `c30e8ce`, clean tree — rust build, bytecode compile, docs truth audit, completion truth matrix, secret scan, ruff, targeted mypy, targeted bandit, full suite (**2340 passed, 2 skipped**). Reconciles exactly: baseline `main` 2316 + 3 palette + 19 ledger + 2 driver = 2340. `audit-docs` independently accepts the new `ARTIFACT_INDEX` entry.

**Known flake, not introduced here.** `test_stratum_app_theme_chargers` and `test_semantic_tui_driver_initial_state` can both raise `textual.pilot.WaitForScreenTimeout` under `pytest -n auto` when the host is oversubscribed. Characterised rather than waved at: it reproduced only while a second full battery ran concurrently (58s and 55s wall-clock), and four consecutive unloaded runs are clean at 2340 (20–28s). Both pass in isolation. The mechanism I *could* have introduced — `read_chain_head` reading the ledger on every start — was measured at **0.26 ms** and ruled out.

### Evidence bundle — `artifacts/opus_phase_4_evidence/`

| File | Contents |
|---|---|
| `reproduce.sh` | Regenerates every number in §1–§4 from a clean tree |
| `gate_receipt.json` | `builder_ii.gate_battery_receipt`, `RECORDED_ONLY`, validates via `python -m builder_ii.gate_battery_receipt --validate` |
| `tui_audit_ledger.jsonl` | Raw event ledger, rescued from gitignored `.builder/` |

---

## 8. HITL decision record

Findings were reported first and executed only on approval; nothing here was self-authorized.

| # | Decision | Outcome |
|---|---|---|
| 1 | Commit the §3.1/§3.3 fixes + 3 lanes, and delete `fix_all.py` | **APPROVED** → `635e72a`, `3811bd6` |
| 2 | Rebind ledger digest to `state`; add `prev_digest` chain | **APPROVED** → `98f68d4` (implemented as **two** digests — see §3.4 for why one is forgeable) |
| 3 | Create the validator; register the kind in `ARTIFACT_INDEX` | **APPROVED** → `98f68d4` |
| 4 | Retire `pexpect` `scripts/tui_driver.py` | **DEFERRED** — promotion boundary, dedicated sweep |

**One deviation from a literal directive, stated plainly.** Item 2 said to rebind *the* digest to the state payload and add `prev_digest`. Implemented as two fields instead, because the single-field version does not achieve the directive's own stated guarantee — it leaves the chain forgeable (§3.4). The intent was honored; the letter was not.

---

## 9. Corrections to this report — issued 2026-07-16, at `2efa0d0`

§7 says an audit that hides its own errors is not an audit. Three of this report's claims were falsified by the follow-on hardening pass, and are corrected here rather than quietly edited away.

### 9.1 The splash finding was correct and its severity was wrong — the driver never observed STRATUM

This report rated the splash **LOW**, describing the cost as one burned keypress. Measured directly, the cost was the entire instrument:

| | before | after |
|---|---|---|
| `active_screen` recorded | `SplashScreen` | `Screen` |
| widgets recorded | 5 (`Center`/`Static`/`Vertical`) | 37 |
| driver wall-clock | 6.48s | 1.60s |

`on_mount` pushes `SplashScreen`, so `app.screen` **is** the splash, and the driver reads `app.screen`. Every state it ever recorded was the loading screen — so §5's ledger, and the whole hash chain §3.4 built over it, chained states of a splash. The covering lane asserts only that `initial_state`, `widgets` and `active_screen` are *present*, and a splash has all three, so it stayed green throughout.

This is the same error PR #163 made and this report criticised it for: **I found the visible symptom (a burned keypress), fixed nothing, and never asked what the splash owned.** Rating it LOW is what let it survive a report specifically looking for measurement artifacts.

### 9.2 `FooterKey` is Textual's, not builder-II's — a misattribution originating here

§6 listed `FooterKey` beside `PaletteEntry`/`SpineItem`/`CapabilityItem` as though all four were builder-II widgets. It is `textual.widgets._footer.FooterKey`, constructed inside Textual's own `Footer.compose`; this codebase never instantiates it and cannot give it an id without subclassing `Footer` and reimplementing a compose that reaches into `active_bindings`/`KeyGroup`/`data_bind`. The other three are now addressable; `FooterKey` is not, needs not to be (a driver presses the key rather than clicking its label), and should not have been listed.

### 9.3 The "known flake" had a mechanism, and it was not host load

§7 attributed `WaitForScreenTimeout` in `test_stratum_app_theme_chargers` and `test_semantic_tui_driver_initial_state` to host oversubscription, having ruled out `read_chain_head` at 0.26 ms. The characterisation was accurate and the conclusion was incomplete. Same host, same moment, one test:

| run | wall-clock |
|---|---|
| `test_stratum_app_theme_chargers` | **6.36s** |
| same, `BUILDER_SPLASH_NATIVE=0` | **0.93s** |

The splash compiles and runs a Swift program to float the hero JPEG in a real Cocoa panel whenever `swift` is on `PATH` and the JPEG exists — both true here, and `headless=True` does not prevent it. The suite was **launching GUI windows**, and a pilot blocked ~5.4s on one has seconds of slack to lose before it times out; an oversubscribed box takes them. Load was the trigger, not the cause. The two tests I called flaky are precisely the two that reach that subprocess — a correlation I noted and did not chase.

Fixed at the four call sites and closed as a class by `conftest.py` defaulting `BUILDER_SPLASH_NATIVE=0`. Full suite at `2efa0d0`: **2357 passed, 2 skipped in 16.10s** under `pytest -n auto` — the configuration that was red at 68s on the previous HEAD.

**Standing caveat, unchanged.** The `-n auto` worker count still derives from `nproc` rather than available capacity, so a heavily contended host can still make this suite's verdict a function of what else is running. That is a live risk for a merge gate and is the operator's call, not addressed here.
