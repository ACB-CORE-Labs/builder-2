# WRP Authority PR Ceremony Template (P7)

**Status:** process template (RECORDED_ONLY). Not a promotion grant.  
**Use for:** any PR that changes WRP authority, promotion language, live-lane power,
or load-bearing gates. Substrate-only P6 landings may use a lighter Maker package.

## 1. Maker half (before push / PR)

```bash
# Branch from current main
git fetch origin && git checkout -b <lane> origin/main

# Evidence commands (adapt)
uv run pytest tests/test_wrp_*.py tests/scenarios/test_wrp_*.py -q
uv run builder-platform audit-docs
# optional: bash scripts/ci.sh --receipt <path>
```

Write exchange package:

```text
artifacts/wrp_exchange/mastery/<WAVE>/
  README.md
  maker_candidate_manifest.json   # builder-wrp exchange-maker (or create_maker_candidate_manifest)
  governor/                       # empty until G-LEAD
  <optional scores / digests>.json
```

Manifest must set:

- `self_certified: false`
- `requires_governor_cert: true`
- `grants_authority: false`
- real `test_commands` + exit codes (no theater)

## 2. Governor half (G-LEAD)

Antigravity / Gemini-class review:

1. Read Maker digests and boundary claims (planned ≠ executed ≠ verified ≠ promoted).
2. Confirm no silent S3 enablement / `s3_enabled=true` / cloud invoke inflation.
3. Emit `governor/wave_mastery_<WAVE>_cert.json` with PASS | FAIL | PASS_WITH_NOTES.
4. Optional Flash scorecard under `governor/`.

If Governor unavailable: record absence honestly in PR body; do **not** self-issue
promotion PASS. Substrate landings may merge under HUMAN with documented gap.

## 3. HUMAN

- Promotion stages S1–S4: explicit decision artifacts under `planning/evidence/`.
- Merge path: Forgejo `tea` / `git merge --no-ff` + push `main` (not `gh` / github.com).
- Never reuse a blocked decision (e.g. S3 HUMAN blocked) as enablement authority.

## 4. Honesty checklist

- [ ] Docs + gap matrix + progress marker updated in the same change
- [ ] `builder-platform audit-docs` green
- [ ] No claim of S3 `enabled` without new readiness + HUMAN approve
- [ ] Optional backends remain opt-in / fail-closed; M1 defaults pure
- [ ] W5 replay reports include `repo_state_match` when claiming reconstructive mastery
