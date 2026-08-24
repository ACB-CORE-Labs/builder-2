# Open-Source v1 Release Proof

The canonical release proof is one exact-candidate bundle of kind
`builder_ii.release_proof_bundle`. It binds the proposed `1.0.0` package and
`v1.0.0` tag identity to an exact commit/tree, `uv.lock`, built wheel and sdist,
supported-host installation proofs, local CI, integrated sabotage outcomes,
Plan Set 5 benchmark evidence, generated documentation truth, demo evidence,
and hosted rehearsal custody.

A valid bundle is evidence for human review. It is not capability promotion,
tag authority, GitHub Release authority, or package-publication authority.

## Supported v1 hosts

- macOS Apple Silicon: supported and the primary performance/MLX target.
- Linux: supported governance/runtime lane, without MLX parity.
- Windows and WSL2: unsupported for v1.
- Python: `>=3.12.13,<3.13`.

The macOS and Linux lanes install the same wheel bytes and run the complete
governed golden path. A development-checkout test cannot substitute for either
installed-wheel proof.

## Candidate workflow

```bash
bash scripts/build-release-candidate.sh dist/release-candidate

bash scripts/clean-clone-smoke.sh \
  --candidate-wheel dist/release-candidate/builder_ii-1.0.0-py3-none-any.whl \
  --candidate-wheel-sha256 <sha256> \
  --candidate-extras deepagents,apple \
  --host-proof .builder/release-evidence/macos.json

bash scripts/release-linux-candidate.sh \
  dist/release-candidate/builder_ii-1.0.0-py3-none-any.whl \
  <sha256> .builder/release-evidence/linux.json

bash scripts/release-sabotage-battery.sh \
  dist/release-candidate/builder_ii-1.0.0-py3-none-any.whl \
  <sha256> .builder/release-evidence/release-sabotage.json

uv run builder-release build-bundle --repo . \
  --dist-dir dist/release-candidate \
  --evidence-dir .builder/release-evidence \
  --output-dir dist/open-source-v1-proof

uv run builder-release validate-bundle-directory \
  dist/open-source-v1-proof --repo .
```

The bundle builder refuses a dirty candidate, missing or failed required lane,
duplicate lane or distribution type, symlinked evidence, wrong distribution
metadata, mismatched digest, moved source/lock identity, or an authorizing
governance claim. Every lane is schema-specific, binds the exact candidate
commit/tree and wheel digest, and carries runtime versions, elapsed time,
skips, logs, and typed predecessor references where a canonical receipt or
report exists. `payload_custody` covers every copied constituent byte outside
the self-describing bundle manifest; independent validation reconstructs that
set, rehashes it, validates the canonical chain report, and refuses extra,
missing, duplicate, or substituted files.

## Required evidence lanes

The required results are exact-tip local CI, Linux golden path, macOS Apple
Silicon golden path, integrated release sabotage, docs audit, platform matrix,
Plan Set 5 benchmark readback, flagship demo/rehearsal, hosted custody of
rehearsal PRs #1/#2, and artifact-chain validation. Required lanes must be
`PASS`; `SKIP` and `NOT_RUN` are explicit non-green states.

The local-CI lane must resolve to the canonical gate-battery receipt at the
bundle commit, with a stable clean tip and every blocking gate passed without a
skip. Host lanes are not interchangeable: macOS requires Darwin arm64 plus the
Deep Agents and Apple/MLX extras; Linux requires Linux plus Deep Agents and an
explicit no-MLX result. Benchmark, docs/matrix, sabotage, demo, rehearsal
custody, and artifact-chain lanes resolve their admitted reports or logs and
are revalidated from the copied bytes.

## Historical V0 compatibility

`builder_ii.v0_release_manifest` and `scripts/verify_v0_release.py` remain
readable so sealed historical evidence continues to validate. They prove only
the former passive/no-runtime spine and are not a second current release truth
system. New release qualification uses `builder-release` and the v1 bundle.
