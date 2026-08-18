#!/usr/bin/env bash
# Run the SAME blocking gate battery (scripts/ci.sh) inside a container that matches the
# Forgejo CI runner's ACTUAL execution environment -- so host-dependent bugs are caught here,
# in seconds-to-minutes, instead of ~30 minutes later on the shared runner.
#
# Why this file exists: on 2026-07-11 the Forgejo runner ran `bash scripts/ci.sh` for the first
# time on a real host and it failed on two tests that pass on every developer's machine. Both
# were REAL bugs, hidden purely by an environment mismatch between "a developer's Mac" and
# "the runner's container":
#   1. The runner executes every step as ROOT (no non-root user exists in the image), and root
#      bypasses `chmod 444` permission bits a test relied on to make a file genuinely unwritable.
#      A non-root developer never sees this: chmod 444 really does block them.
#   2. The runner's terminal is non-interactive (no tty) at Rich's 80-column default, and Rich
#      word-wrapped a long filesystem path at that width, splitting it mid-filename. A developer
#      on a wide terminal, or with a short tmp-dir path, never hits that wrap point.
# Both were fixed in the code, but nothing stopped a THIRD host-dependent bug from being
# introduced tomorrow and passing every developer's local `bash scripts/ci.sh` before reaching
# CI half an hour later. This script closes that gap locally.
#
# What this catches that `bash scripts/ci.sh` alone CANNOT, on a developer's own Mac:
#   * root-vs-non-root behavior (permission bits, ownership checks, sudo-gated code paths)
#   * non-tty / narrow-console Rich rendering (word-wrap, truncation, no ANSI color codes)
#   * Debian/glibc-vs-macOS/BSD userland differences in anything scripts/ci.sh shells out to
#   * a genuinely fresh toolchain/dependency provisioning (catches "works because my local
#     ~/.cargo or .venv already has some stale state" bugs)
# It does NOT catch anything CPU-architecture-specific: this runs under whatever architecture
# Docker resolves node:20-bookworm to on this host (arm64 on Apple Silicon), while the real
# Forgejo runner is presumed x86_64/amd64. That gap is out of scope for this tool.
#
# What this is NOT:
#   * NOT one of the 9 blocking gates in scripts/ci.sh, and deliberately absent from
#     tests/test_ci_gate_parity.py's REQUIRED_GATES tuple (that tuple pins scripts/ci.sh's own
#     gate list; this is a separate, complementary, OPTIONAL tool -- do not add a gate here that
#     isn't already a gate there, and do not wire this script into CI itself: CI already IS the
#     environment this container reproduces, so running this a second time inside CI would just
#     re-run the same battery inside a container inside a container for no new signal).
#   * NOT a substitute for `bash scripts/ci.sh`: it is much slower (real network installs of a
#     Rust toolchain, uv, and every dependency, timed below) and requires Docker. Run the plain
#     battery for routine iteration; run this before a push you want real CI-parity confidence
#     on, or whenever you suspect a host-dependent bug (root, console width, OS differences).
#
# Timing (measured on this session's host: Apple Silicon, Docker Desktop, `node:20-bookworm`,
# `linux/arm64`, fast network, `node:20-bookworm` layers already pulled):
#   * First run (empty Docker volumes -- fresh Rust toolchain, fresh uv, fresh Python install,
#     fresh `uv sync`, fresh `cargo build`, full pytest suite): ~128s (~2 minutes).
#   * Cached rerun (same worktree, Docker volumes retain rustup/cargo/uv/venv state from a
#     prior run -- installers skip themselves, `uv sync` mostly no-ops, `cargo build` is
#     incremental): ~36s.
#   A slower network, a cold `docker pull node:20-bookworm`, or an x86_64 host will both be
#   slower than these numbers -- they are a real measurement on one host, not a guarantee.
#
# Caching model: every persistent bit of state (Rust toolchain, uv binary + Python installs +
# package cache, the container's own venv, the container's own `cargo` target dir) lives in
# named Docker volumes SCOPED TO THIS WORKTREE (tagged by its absolute path). That trades away
# sharing a download cache across concurrent worktrees for zero risk of two concurrent
# `ci-in-container.sh` runs (e.g. in sibling worktrees, per this project's parallel-agent
# workflow) corrupting a shared venv or `cargo` target directory by writing into it at once.
# Nothing here ever touches this worktree's own `.venv` or `target/` on the host: the container
# venv and cargo target dir are redirected (`UV_PROJECT_ENVIRONMENT`, `CARGO_TARGET_DIR`) to
# volumes outside the bind mount, specifically so a Linux/root virtualenv or build tree can never
# leak into (and silently break) the host's own macOS `.venv`/`target/`.
#
# Bind mount, not copy: the CURRENT WORKING TREE (including uncommitted changes) is bind-mounted
# into the container, so this tests the developer's actual diff, not a stale commit.
#
# Worktree support: if the current checkout is a linked `git worktree` (its `.git` is a FILE
# containing an absolute path to the main repo's `.git` directory, e.g. this repo's own
# `git worktree add` workflow), that absolute path is bind-mounted into the container at the
# IDENTICAL absolute path, so the `.git` file's absolute reference still resolves inside the
# container. Without this, every git command inside the container (including the receipt
# mechanism's `git rev-parse HEAD` / `git status --porcelain`) fails with
# "fatal: not a git repository" the moment you run this from a worktree instead of the main
# checkout.
set -o errexit
set -o nounset
set -o pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

if ! command -v docker >/dev/null 2>&1; then
  printf 'ERROR: docker is required by scripts/ci-in-container.sh and was not found on PATH.\n' >&2
  exit 2
fi

IMAGE="node:20-bookworm"

# Docker volume names must match [a-zA-Z0-9][a-zA-Z0-9_.-]*; collapse the worktree's absolute
# path into a safe, human-legible tag so caches stay scoped to THIS checkout (see header comment
# on why per-worktree scoping, not a globally shared cache, is the deliberate choice here).
WORKTREE_TAG="$(printf '%s' "$REPO_ROOT" | tr -c 'a-zA-Z0-9' '-' | sed -E 's/-+/-/g; s/^-//; s/-$//')"
VOL_PREFIX="builder-ii-cic-${WORKTREE_TAG}"

DOCKER_ARGS=(
  run --rm
  -v "${REPO_ROOT}:/workspace"
  -w /workspace
  -v "${VOL_PREFIX}-cargo:/root/.cargo"
  -v "${VOL_PREFIX}-rustup:/root/.rustup"
  -v "${VOL_PREFIX}-local-bin:/root/.local/bin"
  -v "${VOL_PREFIX}-uv-cache:/root/.cache/uv"
  -v "${VOL_PREFIX}-uv-share:/root/.local/share/uv"
  -v "${VOL_PREFIX}-venv:/root/.venv-ci-container"
  -v "${VOL_PREFIX}-cargo-target:/root/.cargo-target-ci-container"
  -e "UV_PROJECT_ENVIRONMENT=/root/.venv-ci-container"
  -e "CARGO_TARGET_DIR=/root/.cargo-target-ci-container"
)

# Linked-worktree support (see header comment). `git rev-parse --path-format=absolute
# --git-common-dir` returns the MAIN repo's .git directory even when run from a linked
# worktree; when that path falls outside REPO_ROOT, the worktree's `.git` FILE points at an
# absolute host path the container cannot otherwise see, so mount it at the same path.
if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  GIT_COMMON_DIR="$(git -C "$REPO_ROOT" rev-parse --path-format=absolute --git-common-dir)"
  case "$GIT_COMMON_DIR" in
    "$REPO_ROOT"/*|"$REPO_ROOT")
      : # ordinary (non-worktree) checkout -- already covered by the main bind mount
      ;;
    *)
      printf 'Linked git worktree detected: also bind-mounting %s\n' "$GIT_COMMON_DIR"
      DOCKER_ARGS+=(-v "${GIT_COMMON_DIR}:${GIT_COMMON_DIR}")
      ;;
  esac
fi

DOCKER_ARGS+=("$IMAGE" bash -c "$(cat <<'CONTAINER_SCRIPT'
set -o errexit
set -o nounset
set -o pipefail

echo "[ci-in-container] checking container identity..."
ACTUAL_USER="$(whoami)"
if [ "$ACTUAL_USER" != "root" ]; then
  echo "FATAL: expected to run as root (the Forgejo runner's node:20-bookworm has no non-root user), got: $ACTUAL_USER" >&2
  exit 97
fi
echo "[ci-in-container] confirmed whoami == root"

# Root-bypass sanity check: this is the SAME mechanism that hid bug #1 above. Prove it live,
# every run, so a future reader can see the exact condition this tool exists to reproduce.
PERM_PROBE="$(mktemp)"
printf 'probe\n' > "$PERM_PROBE"
chmod 444 "$PERM_PROBE"
if echo "appended-by-root" >> "$PERM_PROBE" 2>/dev/null; then
  echo "[ci-in-container] confirmed: root bypasses chmod 444 on this filesystem (matches the CI failure mode)"
else
  echo "FATAL: root did NOT bypass chmod 444 as expected -- this container no longer reproduces the CI failure mode this tool exists to catch" >&2
  rm -f "$PERM_PROBE"
  exit 98
fi
rm -f "$PERM_PROBE"

# Make PATH include both toolchains' bin dirs BEFORE the command -v cache checks below, so a
# CACHED run (state already present in the mounted volumes, but a brand new container process
# with a fresh PATH) is correctly detected as already-installed instead of reinstalling every
# time. `source $HOME/.cargo/env` / `source $HOME/.local/bin/env` below are then redundant with
# this export but are kept anyway, deliberately, to match the exact provisioning sequence
# ci.yml documents and a developer would run by hand.
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

git config --global --add safe.directory "*" >/dev/null 2>&1 || true

if command -v rustc >/dev/null 2>&1; then
  echo "[ci-in-container] rustup toolchain already present (cached volume) -- skipping install"
else
  echo "[ci-in-container] installing rustup..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
fi
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"

if command -v uv >/dev/null 2>&1; then
  echo "[ci-in-container] uv already present (cached volume) -- skipping install"
else
  echo "[ci-in-container] installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
[ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"

echo "[ci-in-container] rustc: $(rustc --version)"
echo "[ci-in-container] uv: $(uv --version)"

echo "[ci-in-container] uv python install"
uv python install

echo "[ci-in-container] uv sync --all-groups --extra deepagents"
uv sync --all-groups --extra deepagents

echo "[ci-in-container] bash scripts/ci.sh"
mkdir -p .builder/artifacts
bash scripts/ci.sh --receipt .builder/artifacts/ci-in-container-gate-battery-receipt.json
CONTAINER_SCRIPT
)")

printf '================================================================\n'
printf 'ci-in-container: blocking gate battery, run inside node:20-bookworm as root\n'
printf '  (CI-runner-parity check -- heavier and slower than `bash scripts/ci.sh` alone;\n'
printf '   see this script'"'"'s header comment for what it catches and why it exists.\n'
printf '   ~2 min first run / ~35s cached rerun, measured on this session'"'"'s host -- see header.)\n'
printf 'worktree: %s\n' "$REPO_ROOT"
printf '================================================================\n'

START_TS=$(date +%s)
set +o errexit
docker "${DOCKER_ARGS[@]}"
DOCKER_EXIT=$?
set -o errexit
END_TS=$(date +%s)

printf '================================================================\n'
if [ "$DOCKER_EXIT" -eq 0 ]; then
  printf 'ci-in-container: PASS (exit 0) in %ss\n' "$((END_TS - START_TS))"
else
  printf 'ci-in-container: FAIL (exit %s) in %ss\n' "$DOCKER_EXIT" "$((END_TS - START_TS))"
fi
printf 'receipt (if the battery reached scripts/ci.sh): .builder/artifacts/ci-in-container-gate-battery-receipt.json\n'
printf '================================================================\n'

exit "$DOCKER_EXIT"
