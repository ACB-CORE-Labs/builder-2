#!/usr/bin/env bash
# setup_cloud_env.sh -- cloud environment bootstrap for builder-II.
#
#   1. Install Astral uv (deterministic package manager) if missing.
#   2. Point BUILDER_TARGET_REPO at this repo itself (no external CORE clone).
#   3. Deterministic dependency sync: uv sync --all-groups --locked.
#   4. Install the Codename Goose CLI via scripts/install-goose.sh (best effort).
#   5. Bootstrap Ollama and pull the model roster; if Ollama cannot run on this
#      host, fall back to the groq backend with BUILDER_MODEL_ALIAS=groq-gpt-oss-120b.
#
# All machine-local state lands in .env (gitignored). GROQ_API_KEY is checked
# but never written by this script -- the operator supplies it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"
ENV_FILE="$REPO_ROOT/.env"

OLLAMA_HOST_URL="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_HEALTH_TIMEOUT_S=30
# Roster tags: gemma4:e4b matches the builder-II Ollama roster (builder_ii/core/models.py);
# qwen2.5-coder is the requested coding lane.
OLLAMA_ROSTER=("gemma4:e4b" "qwen2.5-coder")

warn() { printf 'WARNING: %s\n' "$*" >&2; }

step() {
  echo
  echo "==> [$1/5] $2"
}

# Idempotent KEY=VALUE upsert into .env -- never clobbers unrelated keys.
set_env_kv() {
  local key="$1" value="$2" tmp
  touch "$ENV_FILE"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    tmp="$(mktemp)"
    sed "s|^${key}=.*|${key}=${value}|" "$ENV_FILE" >"$tmp"
    mv "$tmp" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

ollama_healthy() {
  curl -fsS --max-time 3 "$OLLAMA_HOST_URL/api/tags" >/dev/null 2>&1
}

echo "=========================================================="
echo "          INITIALIZING BUILDER-II CLOUD ENVIRONMENT       "
echo "=========================================================="

# ---------------------------------------------------------------------------
step 1 "Installing uv (if missing)..."
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  echo "uv already installed: $(uv --version)"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  uv --version
fi

# ---------------------------------------------------------------------------
step 2 "Setting target repo link (builder-II targets itself)..."
set_env_kv BUILDER_TARGET_REPO .
echo "BUILDER_TARGET_REPO=. recorded in .env"

# ---------------------------------------------------------------------------
step 3 "Running deterministic uv sync..."
if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
  echo "error: pyproject.toml not found in $REPO_ROOT. Run this from the builder-II root." >&2
  exit 1
fi
# Provision the pinned interpreter (.python-version) the same way CI does --
# actions/setup-python is deliberately not used on the Forgejo runner either.
# A stale preinstalled uv may not know the pinned CPython build; astral.sh and
# GitHub API can be proxy-blocked in cloud containers, so recover via PyPI.
if ! uv python install; then
  warn "uv could not provision the pinned interpreter; upgrading uv from PyPI and retrying."
  python3 -m pip install --user --upgrade --break-system-packages uv >/dev/null 2>&1 \
    || python3 -m pip install --user --upgrade uv >/dev/null 2>&1 \
    || warn "Could not upgrade uv via PyPI."
  hash -r
  uv python install
fi
# --all-groups pulls the dev group (ruff/mypy/bandit/pytest) that scripts/ci.sh
# requires; --locked enforces bit-for-bit parity with uv.lock.
if uv sync --all-groups --locked; then
  echo "Locked sync complete (uv.lock honoured exactly)."
else
  warn "uv sync --locked failed (lock drift?); falling back to unlocked sync. Determinism NOT guaranteed."
  uv sync --all-groups
fi

# ---------------------------------------------------------------------------
step 4 "Installing Goose CLI (best effort)..."
if command -v goose >/dev/null 2>&1; then
  echo "goose already installed: $(goose --version)"
elif [ -f "$REPO_ROOT/scripts/install-goose.sh" ]; then
  bash "$REPO_ROOT/scripts/install-goose.sh" || warn "Goose install failed; continuing (Goose is an adapter substrate, not required for the gate battery)."
else
  warn "scripts/install-goose.sh missing; skipping Goose install."
fi

# ---------------------------------------------------------------------------
step 5 "Bootstrapping Ollama and model roster (groq fallback if unavailable)..."
OLLAMA_READY=false

if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh || warn "Ollama install failed on this host."
fi

if command -v ollama >/dev/null 2>&1; then
  if ! ollama_healthy; then
    echo "Starting ollama serve in the background..."
    (ollama serve >/dev/null 2>&1 &) || true
  fi
  for _ in $(seq 1 "$OLLAMA_HEALTH_TIMEOUT_S"); do
    if ollama_healthy; then
      OLLAMA_READY=true
      break
    fi
    sleep 1
  done
fi

if [ "$OLLAMA_READY" = true ]; then
  echo "Ollama healthy at $OLLAMA_HOST_URL -- pulling model roster..."
  for model in "${OLLAMA_ROSTER[@]}"; do
    ollama pull "$model" || warn "Could not pull $model (continuing)."
  done
  ACTIVE_LANE="ollama (builder-II default backend; roster: ${OLLAMA_ROSTER[*]})"
else
  warn "Ollama unavailable on this host -- switching default model lane to the groq backend."
  set_env_kv BUILDER_MODEL_BACKEND groq
  set_env_kv BUILDER_MODEL_ALIAS groq-gpt-oss-120b
  set_env_kv BUILDER_MODEL_TIER primary
  ACTIVE_LANE="groq fallback (BUILDER_MODEL_ALIAS=groq-gpt-oss-120b)"
  if [ -z "${GROQ_API_KEY:-}" ] && ! grep -qE '^GROQ_API_KEY=.+' "$ENV_FILE"; then
    warn "GROQ_API_KEY is not set. Add it to .env or the environment before launching model sessions."
  fi
fi

echo
echo "=========================================================="
echo "  CLOUD ENVIRONMENT READY FOR CLAUDE & GOOSE WORK"
echo "  Active model lane: $ACTIVE_LANE"
echo "=========================================================="
