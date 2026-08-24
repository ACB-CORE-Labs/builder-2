# builder-II Operator Guide

builder-II is a generic governed local agent/developer platform. It provides an operator with target repository profiles, local and cloud model execution gateways, Goose runtime adapters, artifact ledgers, verification guidance, and promotion-gated runtime boundaries.

It is not CORE, not CORE Workbench/UI, and not an autonomous engineer. CORE is supported as a first-class target profile.

---

## 1. Operating Posture & Authority Boundaries

The validated operational posture for builder-II centers on **governed engineering**:
- **Artifacts First:** Every proposal, plan, or recommendation is recorded as a typed JSON artifact and validated against schema and digest integrity.
- **Interactive Approvals:** State mutations (applying patches, rolling back edits, spending budget) require an interactive human-in-the-loop (HITL) confirmation typing the artifact's SHA-256 digest prefix.
- **Single Bounded Invocation:** Subprocesses run through bounded runners (`shell=False`, fixed in-code argv, environment allowlist, timeout, and digest-bound receipts).

### Authority Non-Grants (by Design):
- **No autonomous source writes:** Code edits require explicit, digest-bound operator approval.
- **No unconstrained shell execution:** Arbitrary shell execution is forbidden; verification runners execute fixed profiles only.
- **No hidden memory or vector stores:** Artifact memory atoms are explicit and reviewable.
- **No autonomous Git publishing:** Local commits, remote pushes, and PR creation require distinct, explicit operator actions.
- **No sandbox overstatements:** Verification runners execute with user privileges on trusted local code.

---

## 2. Governed Setup & Onboarding Lane

The governed setup lane plans, checks, and snapshots platform configuration:

```bash
# 1. Inspect and resolve configuration precedence
uv run builder-config schema
uv run builder-config resolve
uv run builder-config validate

# 2. Plan setup overlay and generate rollback snapshot
uv run builder-setup plan --output .builder/setup/plan.json
uv run builder-setup validate-plan .builder/setup/plan.json
uv run builder-setup overlay-plan .builder/setup/plan.json --output .builder/setup/overlay.json
uv run builder-setup validate-overlay-plan .builder/setup/overlay.json
uv run builder-setup rollback-snapshot .builder/setup/overlay.json --output .builder/setup/rollback-snapshot.json
uv run builder-setup validate-rollback-snapshot .builder/setup/rollback-snapshot.json

# 3. Interactive onboarding wizard
uv run builder-setup wizard
```

---

## 3. Standard Governed Workflow

```bash
# 1. Health checks & profile validation
uv run builder doctor
uv run builder-targets validate
uv run builder-agent validate
uv run builder-verification validate

# 2. Context assembly & session preparation
uv run builder-session prepare-package generic \
  --task "Refactor authentication session token validation" \
  --output-dir .builder/session/
uv run builder-session validate-prepare-package .builder/session/
uv run builder-session summarize-prepare-package .builder/session/

# 3. Verification planning & approval
uv run builder-verify plan --target-profile generic --verification-profile platform_status \
  --output .builder/verification/plan.json
uv run builder-verify validate-plan .builder/verification/plan.json
uv run builder-verify approve-plan .builder/verification/plan.json \
  --profile platform_status --approval-actor "operator" --approval-reason "preflight check" \
  --output .builder/verification/approval.json
uv run builder-verify run-approved \
  --plan .builder/verification/plan.json \
  --approval .builder/verification/approval.json \
  --output .builder/verification/receipt.json \
  --profile platform_status

# 4. Patch proposal, approval, application, and rollback
uv run builder-hitl propose-patch --diff-file /path/to/diff.patch --output .builder/patches/proposal.json \
  --description "token validation fix" --reason "security hardening"
uv run builder-hitl approve-patch --proposal .builder/patches/proposal.json --output .builder/patches/approval.json \
  --approved-by "operator"
uv run builder-hitl apply-patch --proposal .builder/patches/proposal.json --approval .builder/patches/approval.json \
  --verification-receipt .builder/verification/receipt.json --output-dir .builder/patches/applied/

# 5. Rollback (when needed)
uv run builder-hitl approve-rollback --rollback-plan .builder/patches/applied/rollback_plan.json \
  --output .builder/patches/rollback-approval.json --approved-by "operator"
uv run builder-hitl rollback --rollback-plan .builder/patches/applied/rollback_plan.json \
  --reverse-patch .builder/patches/applied/rollback.patch \
  --approval .builder/patches/rollback-approval.json --output-dir .builder/patches/rolled-back/
```

---

## 4. Target Profiles

builder-II operates against explicit target repository profiles:
- `generic`: Any standard software repository with no specialized doctrine.
- `builder`: builder-II platform self-development and self-audit.
- `core`: AssetOverflow/core development (target profile only, isolating CGA invariants).

Inspect available profiles:
```bash
uv run builder-targets list
uv run builder-targets show generic
uv run builder-targets validate
```

---

## 5. Model Gateway & Routing Policy

Models are accessed through the governed **Model Execution Gateway**:
- Evaluates task complexity, privacy tier, and budget constraints (`builder-model-policy`).
- Emits immutable route bindings and records budget successor debits.
- Generates digest-bound execution receipts.

```bash
# Render a model routing recommendation
uv run builder-model-policy render --task-intent coding --max-risk local_network \
  --output .builder/model/routing-recommendation.json

# Execute a governed model call
uv run builder-model call --prompt "Review this error trace" --model-alias phi-reasoning \
  --output-receipt .builder/model/call-receipt.json
uv run builder-model validate-receipt .builder/model/call-receipt.json
```

---

## 6. Codename Goose Runtime Adapter

Goose serves as the primary local operator runtime substrate:
- **Session Manifests:** Launch parameters, recipe paths, and security envelopes are declared passively via `builder-goose manifest`.
- **Read-Only Runtime:** Promoted with launch/close receipts and zero-mutation postflight verification (`builder-goose start-readonly`).
- **Recipes:** Reusable playbooks live in `recipes/` (`recipes/core-coding.yaml`, `recipes/subrecipes/plan.yaml`, `explore.yaml`, `implement.yaml`, `review.yaml`, `verify.yaml`, `handoff.yaml`).

---

## 7. Operational Status & Truth Verification

Always verify platform operational status against the ground truth matrix:

```bash
# Check verified capabilities count and pending blockers
uv run builder-platform status
uv run builder-platform matrix

# Audit documentation against false-completion claims
uv run builder-platform audit-docs
```

Refer to [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for the verbatim list of unpromoted capabilities and blockers generated directly from the matrix.

