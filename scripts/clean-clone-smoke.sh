#!/usr/bin/env bash
# Repeatable clean-clone onboarding smoke gate (plan item 2.7).
#
# Clones the repo fresh into a scratch directory, runs the README "First run"
# golden path end to end, then runs one complete generic governed patch loop
# (propose -> approve -> verify -> apply -> rollback) against a throwaway
# fixture repo -- "their own repo", per the exit-criterion (a) wording. The
# whole run executes with `swift`/`xcodebuild` shadowed by hard-failing
# stubs, so a pass also proves the golden path has no Xcode/Swift toolchain
# dependency (phase0 item 0.6).
#
# Step order note: `apply-patch` REQUIRES a verification receipt as an INPUT
# (builder_ii/governance/hitl/hitl_patch_apply.py), so verification is technically a
# pre-apply gate in the shipped code, not a step that follows apply. This
# script verifies before applying; the plan's "propose -> approve -> apply ->
# verify -> rollback" prose is a narrative simplification of that.
#
# This is a smoke gate, not a security control: the governed patch-approval
# steps still go through the real interactive TTY prompt code path, just fed
# via piped stdin instead of a keyboard -- the same technique this repo's own
# CLI tests already use. It proves the CLI/artifact mechanics work end to
# end; it is not a substitute for a human reviewing a real patch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE="$REPO_ROOT"
WORKDIR=""
KEEP=0
BUDGET_SECONDS=1800
SKIP_MLX=0
CANDIDATE_WHEEL=""
CANDIDATE_WHEEL_SHA256=""
CANDIDATE_EXTRAS="deepagents"
HOST_PROOF=""

usage() {
  cat <<'USAGE'
Usage: bash scripts/clean-clone-smoke.sh [options]

Options:
  --source PATH_OR_URL    Repo to clone (default: this checkout's toplevel).
  --workdir DIR            Scratch directory to clone/work in (default: mktemp -d).
  --keep                   Do not delete the workdir on exit.
  --budget-seconds N        Onboarding-claim ceiling in seconds (default: 1800 / 30 min).
  --skip-mlx                Skip the mlx optional-dependency extra even on Apple Silicon
                             (faster local iteration; the real onboarding path does not skip it).
  --candidate-wheel PATH    Run installed commands from this wheel instead of the clone environment.
  --candidate-wheel-sha256  Required expected SHA-256 for --candidate-wheel.
  --candidate-extras LIST   Wheel extras for the isolated tool install (default: deepagents).
  --host-proof PATH         Write and validate a release host-proof artifact on success.
  -h, --help                 Show this help.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="$2"; shift 2 ;;
    --workdir) WORKDIR="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --budget-seconds) BUDGET_SECONDS="$2"; shift 2 ;;
    --skip-mlx) SKIP_MLX=1; shift ;;
    --candidate-wheel) CANDIDATE_WHEEL="$2"; shift 2 ;;
    --candidate-wheel-sha256) CANDIDATE_WHEEL_SHA256="$2"; shift 2 ;;
    --candidate-extras) CANDIDATE_EXTRAS="$2"; shift 2 ;;
    --host-proof) HOST_PROOF="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$WORKDIR" ]; then
  WORKDIR="$(mktemp -d -t builder-ii-clean-clone-smoke)"
fi
mkdir -p "$WORKDIR"
WORKDIR="$(cd "$WORKDIR" && pwd)"
CLONE_DIR="$WORKDIR/clone"
FIXTURE_DIR="$WORKDIR/patch-loop-target"
STEP_LOG_DIR="$WORKDIR/step-logs"
mkdir -p "$STEP_LOG_DIR"

# A failure always preserves the workdir (regardless of --keep) -- the failure
# message below points at a log file inside it; deleting that out from under the
# operator on the way out would be its own "now what?" dead end.
cleanup() {
  local code="$1"
  if [ "$KEEP" -eq 1 ] || [ "$code" -ne 0 ]; then
    echo "Workdir kept at: $WORKDIR"
  else
    rm -rf "$WORKDIR"
  fi
}
trap 'cleanup $?' EXIT

STEP_NUM=0
SKIPPED=()

_step_fail() {
  local desc="$1" code="$2" elapsed="$3" log_file="$4" cmd="$5"
  printf '     FAILED (%ss, exit %s) -- log: %s\n' "$elapsed" "$code" "$log_file"
  printf '     last 40 lines:\n'
  tail -n 40 "$log_file" | sed 's/^/     | /'
  printf '\nSmoke run failed at step %d: %s\n' "$STEP_NUM" "$desc"
  printf 'Reproduce directly:\n    %s\n' "$cmd"
  printf 'Full log: %s\n' "$log_file"
  exit 1
}

step() {
  local desc="$1"; shift
  STEP_NUM=$((STEP_NUM + 1))
  local log_file="$STEP_LOG_DIR/step-$(printf '%02d' "$STEP_NUM").log"
  printf '\n[%02d] %s\n' "$STEP_NUM" "$desc"
  printf '     $ %s\n' "$*"
  local start end code=0
  start=$(date +%s)
  "$@" >"$log_file" 2>&1 || code=$?
  end=$(date +%s)
  if [ "$code" -eq 0 ]; then
    printf '     ok (%ss)\n' "$((end - start))"
  else
    _step_fail "$desc" "$code" "$((end - start))" "$log_file" "$*"
  fi
}

# Runs a single shell-interpreted command string (needed for piped stdin,
# e.g. feeding a digest prefix to an interactive approval prompt).
step_shell() {
  local desc="$1" cmd="$2"
  STEP_NUM=$((STEP_NUM + 1))
  local log_file="$STEP_LOG_DIR/step-$(printf '%02d' "$STEP_NUM").log"
  printf '\n[%02d] %s\n' "$STEP_NUM" "$desc"
  printf '     $ %s\n' "$cmd"
  local start end code=0
  start=$(date +%s)
  bash -c "$cmd" >"$log_file" 2>&1 || code=$?
  end=$(date +%s)
  if [ "$code" -eq 0 ]; then
    printf '     ok (%ss)\n' "$((end - start))"
  else
    _step_fail "$desc" "$code" "$((end - start))" "$log_file" "$cmd"
  fi
}

skip() {
  local desc="$1" reason="$2"
  STEP_NUM=$((STEP_NUM + 1))
  SKIPPED+=("[$STEP_NUM] $desc -- $reason")
  printf '\n[%02d] %s\n     skipped: %s\n' "$STEP_NUM" "$desc" "$reason"
}

section() {
  printf '\n=== %s ===\n' "$1"
}

quote() { printf '%q' "$1"; }

# ---------------------------------------------------------------------------
# Phase 0: no-Swift-toolchain proof. Shadow swift/xcodebuild with binaries
# that fail loudly, then keep this PATH for the rest of the run. If anything
# in the golden path shells out to either, the run fails here instead of
# silently depending on a toolchain most strangers will not have installed
# (see phase0 item 0.6 -- the TUI splash used to compile-run Swift at launch).
# ---------------------------------------------------------------------------
section "Phase 0: no-Swift-toolchain proof"
STUB_BIN="$WORKDIR/no-swift-stub-bin"
mkdir -p "$STUB_BIN"
for tool in swift xcodebuild; do
  cat >"$STUB_BIN/$tool" <<EOF
#!/usr/bin/env bash
echo "ERROR: '$tool' invoked -- the clean-clone golden path must not depend on the Xcode/Swift toolchain" >&2
exit 1
EOF
  chmod +x "$STUB_BIN/$tool"
done
export PATH="$STUB_BIN:$PATH"
echo "Shadowed swift/xcodebuild with hard-failing stubs for the remainder of this run."

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 1; }
}
need git
need uv

if [ -n "$CANDIDATE_WHEEL" ]; then
  CANDIDATE_WHEEL="$(cd "$(dirname "$CANDIDATE_WHEEL")" && pwd)/$(basename "$CANDIDATE_WHEEL")"
  [ -f "$CANDIDATE_WHEEL" ] || { echo "candidate wheel not found: $CANDIDATE_WHEEL" >&2; exit 2; }
  [ -n "$CANDIDATE_WHEEL_SHA256" ] || { echo "--candidate-wheel-sha256 is required" >&2; exit 2; }
  if command -v shasum >/dev/null 2>&1; then
    ACTUAL_WHEEL_SHA256="$(shasum -a 256 "$CANDIDATE_WHEEL" | awk '{print $1}')"
  else
    ACTUAL_WHEEL_SHA256="$(sha256sum "$CANDIDATE_WHEEL" | awk '{print $1}')"
  fi
  [ "$ACTUAL_WHEEL_SHA256" = "$CANDIDATE_WHEEL_SHA256" ] || {
    echo "candidate wheel digest mismatch: expected $CANDIDATE_WHEEL_SHA256, got $ACTUAL_WHEEL_SHA256" >&2
    exit 1
  }
fi

# ---------------------------------------------------------------------------
# Phase 1: clean clone
# ---------------------------------------------------------------------------
section "Phase 1: clean clone"
step "clone $SOURCE" git clone "$SOURCE" "$CLONE_DIR"
cd "$CLONE_DIR"
step "record clone HEAD" git rev-parse HEAD

# ---------------------------------------------------------------------------
# Phase 2: install + env (README "Install" / first lines of "First run")
# ---------------------------------------------------------------------------
section "Phase 2: install"
if [ -n "$CANDIDATE_WHEEL" ]; then
  export UV_TOOL_DIR="$WORKDIR/uv-tools"
  export UV_TOOL_BIN_DIR="$WORKDIR/uv-tool-bin"
  mkdir -p "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"
  CANDIDATE_SPEC="$CANDIDATE_WHEEL"
  if [ -n "$CANDIDATE_EXTRAS" ]; then
    CANDIDATE_SPEC="$CANDIDATE_WHEEL[$CANDIDATE_EXTRAS]"
  fi
  step "uv tool install exact candidate wheel" uv tool install --python 3.12.13 --force "$CANDIDATE_SPEC"
  export PATH="$UV_TOOL_BIN_DIR:$PATH"
elif [ "$SKIP_MLX" -eq 0 ] && [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
  step "uv sync --extra mlx" uv sync --extra mlx
else
  step "uv sync" uv sync
fi
step "cp .env.example .env" cp .env.example .env

# .env.example now defaults to the self-contained "builder" profile with
# BUILDER_TARGET_REPO=. (plan 2.5), so the copied file alone would work. The smoke
# gate still writes an explicit .env with the absolute clone path so the run is
# deterministic regardless of future .env.example edits — this pins the exact
# environment the rest of the gate is proving.
cat >"$CLONE_DIR/.env" <<ENV_EOF
BUILDER_TARGET_REPO=$CLONE_DIR
BUILDER_TARGET_PROFILE=builder
BUILDER_ARTIFACT_ROOT=.builder/artifacts
BUILDER_RUNTIME_MODE=passive
ENV_EOF
echo "Rewrote .env for a self-contained target (no sibling 'core' checkout in a bare clone; see comment above)."

run() {
  if [ -n "$CANDIDATE_WHEEL" ]; then
    "$@"
  else
    uv run --project "$CLONE_DIR" "$@"
  fi
}

run_python() {
  if [ -n "$CANDIDATE_WHEEL" ]; then
    "$UV_TOOL_DIR/builder-ii/bin/python" "$@"
  else
    uv run --project "$CLONE_DIR" python "$@"
  fi
}

run_approval_shell() {
  local prefix="$1"; shift
  if [ -n "$CANDIDATE_WHEEL" ]; then
    printf '%s\n' "$prefix" | "$@"
  else
    printf '%s\n' "$prefix" | uv run --project "$CLONE_DIR" "$@"
  fi
}

ART="$CLONE_DIR/.smoke-artifacts"
mkdir -p "$ART/setup" "$ART/setup-artifacts" "$ART/r1-closure" "$ART/verification" "$ART/session"

# ---------------------------------------------------------------------------
# Phase 3: README "First run" golden path (non-interactive, non-mutating)
# ---------------------------------------------------------------------------
section "Phase 3: golden path"
step "builder-setup plan" run builder-setup plan --output "$ART/setup/plan.json"
step "builder-setup validate-plan" run builder-setup validate-plan "$ART/setup/plan.json"
step "builder-setup overlay-plan" run builder-setup overlay-plan "$ART/setup/plan.json" --output "$ART/setup/overlay.json"
step "builder-setup validate-overlay-plan" run builder-setup validate-overlay-plan "$ART/setup/overlay.json"
step "builder-setup rollback-snapshot" run builder-setup rollback-snapshot "$ART/setup/overlay.json" --output "$ART/setup/rollback-snapshot.json"
step "builder-setup validate-rollback-snapshot" run builder-setup validate-rollback-snapshot "$ART/setup/rollback-snapshot.json"

skip "builder-setup wizard / builder onboarding" "interactive typer.prompt flow; not part of a scripted golden-path gate"

step "builder doctor" run builder doctor
step "builder models" run builder models
step "builder-targets validate" run builder-targets validate
step "builder-targets list" run builder-targets list
step "builder-agent validate" run builder-agent validate
step "builder-agent profiles" run builder-agent profiles

skip "scripts/install-tools.sh required" "performs real Homebrew installs against the host; excluded from a repeatable/hermetic gate by design"
STATUS_LOG="$STEP_LOG_DIR/tool-status.log"
run builder-tools check --tier tier1 >"$STATUS_LOG" 2>&1 || true
echo "builder-tools check --tier tier1 (informational, non-fatal): $STATUS_LOG"

if [ -n "$CANDIDATE_WHEEL" ]; then
  step "builder-release command surface" run builder-release --help
else
  step "historical verify_v0_release.py compatibility" run python scripts/verify_v0_release.py
fi
step "builder-platform matrix" run builder-platform matrix
step "builder-platform status" run builder-platform status
step "builder-platform audit-docs" run builder-platform audit-docs

step "builder-config schema" run builder-config schema
step "builder-config resolve" run builder-config resolve
step "builder-config validate" run builder-config validate

step "builder-setup init" run builder-setup init --output-dir "$ART/setup-artifacts"
step "builder-setup validate-onboarding-intent" run builder-setup validate-onboarding-intent "$ART/setup-artifacts/onboarding-intent.json"

step "builder-platform r1-closure" run builder-platform r1-closure --output-dir "$ART/r1-closure"
step "builder-platform validate-r1-closure" run builder-platform validate-r1-closure "$ART/r1-closure/r1-closure-report.json"

VPLAN="$ART/verification/verification-execution-plan.json"
VAPPROVAL="$ART/verification/verification-execution-approval.json"
step "builder-verify plan" run builder-verify plan --target-profile builder --verification-profile builder_full --target-repo "$CLONE_DIR" --artifact-root "$ART/verification" --output "$VPLAN"
step "builder-verify validate-plan" run builder-verify validate-plan "$VPLAN"
step "builder-verify approve-plan" run builder-verify approve-plan "$VPLAN" --profile platform_status --approval-actor "Clean-Clone Smoke" --approval-reason "2.7 clean-clone smoke gate" --output "$VAPPROVAL"
step "builder-verify validate-approval" run builder-verify validate-approval "$VAPPROVAL" --plan "$VPLAN"

step "builder-session prepare-package" run builder-session prepare-package builder --task "clean-clone smoke: audit the selected target repo" --output-dir "$ART/session/"
step "builder-session validate-prepare-package" run builder-session validate-prepare-package "$ART/session/"
step "builder-session summarize-prepare-package" run builder-session summarize-prepare-package "$ART/session/"

# ---------------------------------------------------------------------------
# Phase 4: one complete generic governed patch loop on a throwaway fixture
# repo (their "own repo", per exit criterion (a)) -- propose -> approve ->
# verify -> apply -> rollback, with receipts at every step.
#
# The verification receipt reuses the plan/approval from Phase 3 (target
# profile "builder", profile "platform_status"): apply_hitl_patch validates
# any schema-valid verification_execution_receipt without cross-checking it
# against the patch's own target repo (only the special-cased CORE-demo
# receipt kind does that binding). Using platform_status here proves the
# real artifact chain end to end without requiring a pytest suite inside the
# throwaway fixture repo or the D7 execution-risk acknowledgment path.
# ---------------------------------------------------------------------------
section "Phase 4: generic governed patch loop"
step "init fixture repo" git init "$FIXTURE_DIR"
git -C "$FIXTURE_DIR" config user.email "smoke@example.invalid"
git -C "$FIXTURE_DIR" config user.name "Clean-Clone Smoke"
git -C "$FIXTURE_DIR" checkout -q -b main
printf '# Fixture repo\n\nUsed by the clean-clone smoke gate.\n' >"$FIXTURE_DIR/README.md"
git -C "$FIXTURE_DIR" add README.md
step "commit fixture repo initial state" git -C "$FIXTURE_DIR" commit -q -m "initial commit"

printf '# Fixture repo\n\nUsed by the clean-clone smoke gate.\n\nSmoke-test patch line.\n' >"$FIXTURE_DIR/README.md"
step "capture patch diff" bash -c "git -C $(quote "$FIXTURE_DIR") diff > $(quote "$WORKDIR/diff.patch") && [ -s $(quote "$WORKDIR/diff.patch") ]"
git -C "$FIXTURE_DIR" checkout -q -- README.md

cd "$FIXTURE_DIR"

PREFIX_LEN=$(run_python -c "from builder_ii.governance.hitl.hitl_patch_approval import APPROVAL_CONFIRMATION_PREFIX_LENGTH as n; print(n)")

PROPOSAL="$WORKDIR/proposal.json"
APPROVAL="$WORKDIR/approval.json"
RECEIPT="$ART/verification/verification-execution-receipt.json"
APPLY_OUT="$WORKDIR/apply-out"
ROLLBACK_APPROVAL="$WORKDIR/rollback-approval.json"
ROLLBACK_OUT="$WORKDIR/rollback-out"

step "propose-patch" run builder-hitl propose-patch --diff-file "$WORKDIR/diff.patch" --output "$PROPOSAL" \
  --description "clean-clone smoke: append a line to README.md" --reason "prove the generic governed patch loop end to end"

PATCH_PREFIX=$(run_python -c "import json; print(json.load(open('$PROPOSAL'))['patch_digest'][:$PREFIX_LEN])")
if [ -n "$CANDIDATE_WHEEL" ]; then
  approve_patch_cmd="printf '%s\n' $(quote "$PATCH_PREFIX") | builder-hitl approve-patch --proposal $(quote "$PROPOSAL") --output $(quote "$APPROVAL") --approved-by $(quote "Clean-Clone Smoke")"
else
  approve_patch_cmd="printf '%s\n' $(quote "$PATCH_PREFIX") | uv run --project $(quote "$CLONE_DIR") builder-hitl approve-patch --proposal $(quote "$PROPOSAL") --output $(quote "$APPROVAL") --approved-by $(quote "Clean-Clone Smoke")"
fi
step_shell "approve-patch" "$approve_patch_cmd"

step "builder-verify run-approved" run builder-verify run-approved --plan "$VPLAN" --approval "$VAPPROVAL" --output "$RECEIPT" --profile platform_status

step "apply-patch" run builder-hitl apply-patch --proposal "$PROPOSAL" --approval "$APPROVAL" --verification-receipt "$RECEIPT" --output-dir "$APPLY_OUT"

ROLLBACK_PLAN="$APPLY_OUT/rollback_plan.json"
ROLLBACK_PREFIX=$(run_python -c "
import json
from builder_ii.governance.hitl.hitl_rollback_approval import canonical_json_digest
data = json.load(open('$ROLLBACK_PLAN'))
print(canonical_json_digest(data)[:$PREFIX_LEN])
")
if [ -n "$CANDIDATE_WHEEL" ]; then
  approve_rollback_cmd="printf '%s\n' $(quote "$ROLLBACK_PREFIX") | builder-hitl approve-rollback --rollback-plan $(quote "$ROLLBACK_PLAN") --output $(quote "$ROLLBACK_APPROVAL") --approved-by $(quote "Clean-Clone Smoke")"
else
  approve_rollback_cmd="printf '%s\n' $(quote "$ROLLBACK_PREFIX") | uv run --project $(quote "$CLONE_DIR") builder-hitl approve-rollback --rollback-plan $(quote "$ROLLBACK_PLAN") --output $(quote "$ROLLBACK_APPROVAL") --approved-by $(quote "Clean-Clone Smoke")"
fi
step_shell "approve-rollback" "$approve_rollback_cmd"

step "rollback" run builder-hitl rollback --rollback-plan "$ROLLBACK_PLAN" --reverse-patch "$APPLY_OUT/forward_patch_for_reverse_apply.patch" --approval "$ROLLBACK_APPROVAL" --output-dir "$ROLLBACK_OUT"

step "assert fixture repo restored to pre-apply state" bash -c "[ -z \"\$(git -C $(quote "$FIXTURE_DIR") status --porcelain)\" ]"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section "Summary"
ELAPSED=$SECONDS
echo "Steps run: $STEP_NUM"
if [ "${#SKIPPED[@]}" -gt 0 ]; then
  echo "Intentionally skipped:"
  for line in "${SKIPPED[@]}"; do
    echo "  - $line"
  done
fi
echo "Elapsed: ${ELAPSED}s (budget: ${BUDGET_SECONDS}s)"
if [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
  echo "FAIL: exceeded the ${BUDGET_SECONDS}s onboarding-claim budget."
  exit 1
fi
echo "PASS: clean clone through one complete governed patch loop (propose -> approve -> verify -> apply -> rollback), no Xcode/Swift toolchain dependency."
if [ -n "$HOST_PROOF" ]; then
  [ -n "$CANDIDATE_WHEEL" ] || { echo "--host-proof requires --candidate-wheel" >&2; exit 2; }
  HOST_LANE="linux_golden_path"
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    HOST_LANE="macos_apple_silicon_golden_path"
  fi
  run builder-release host-proof --output "$HOST_PROOF" --lane "$HOST_LANE" \
    --wheel "$(basename "$CANDIDATE_WHEEL")" --wheel-sha256 "$CANDIDATE_WHEEL_SHA256" \
    --command "candidate wheel digest" --command "uv tool install" \
    --command "platform audits" --command "governed patch apply rollback loop"
  run builder-release validate-evidence "$HOST_PROOF"
  echo "Validated host proof: $HOST_PROOF"
fi
if [ "$KEEP" -eq 1 ]; then
  echo "Next: read $STEP_LOG_DIR for full per-step logs ($WORKDIR was kept)."
else
  echo "Next: nothing to inspect -- the scratch workdir is removed on a clean pass. Re-run with --keep to preserve $WORKDIR for inspection."
fi
