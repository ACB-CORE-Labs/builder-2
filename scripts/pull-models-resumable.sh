#!/usr/bin/env bash
# Resumable MLX model downloads for throttled/intermittent networks.
#
# Features:
#   - autonomous retry loop;
#   - captive portal / network-intercept detection;
#   - strict background-process cleanup on Ctrl+C;
#   - Hugging Face cache resume semantics;
#   - governed builder-II model aliases for M1 16GB.
#
# Compatible with macOS /bin/bash 3.2.
set -euo pipefail

# --- LIFECYCLE MANAGEMENT ---
# If the script exits or is aborted, kill background jobs to prevent ghost hf processes.
trap 'kill -9 $(jobs -p) 2>/dev/null || true' EXIT INT TERM

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

# Network/cache behavior. Keep Xet high-performance off by default because this
# lane is optimized for flaky public/library Wi-Fi and captive portals.
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_XET_HIGH_PERFORMANCE=0
export PYTHONUNBUFFERED=1

HF="${ROOT}/.venv/bin/hf"
if [[ ! -x "$HF" ]]; then
    HF="$(command -v hf || true)"
fi
if [[ -z "$HF" ]]; then
    echo "Missing Hugging Face CLI. Run: uv sync" >&2
    exit 1
fi

MODE="${1:-status}"
RETRY_DELAY="${RETRY_DELAY:-15}"
MAX_RETRIES="${MAX_RETRIES:-100}"

# ANSI colors / UI elements.
C_BLUE="\033[38;5;39m"
C_GREEN="\033[38;5;119m"
C_WARN="\033[38;5;214m"
C_ERR="\033[38;5;196m"
C_RESET="\033[0m"
CLEAR_LINE="\r\033[K"

known_aliases() {
    echo "phi-reasoning qwen-coder gemma-fast gemma-primary llama codegeex qwen-coder-14b qwen3-coder-heavy deepseek"
}

repo_for_alias() {
    case "$1" in
        phi-reasoning|phi|fast)
            echo "${CORE_AGENT_MLX_MODEL_PHI:-mlx-community/Phi-4-mini-reasoning-4bit}"
            ;;
        qwen-coder|qwen|primary)
            echo "${CORE_AGENT_MLX_MODEL_QWEN:-mlx-community/Qwen2.5-Coder-7B-Instruct-4bit}"
            ;;
        gemma-fast|legacy-fast)
            echo "${CORE_AGENT_MLX_MODEL_FAST:-mlx-community/gemma-4-e4b-it-4bit}"
            ;;
        gemma-primary|legacy-primary)
            echo "${CORE_AGENT_MLX_MODEL_PRIMARY:-mlx-community/gemma-4-12B-it-4bit}"
            ;;
        gemma-optiq|optiq)
            echo "${CORE_AGENT_MLX_MODEL_GEMMA_OPTIQ:-mlx-community/gemma-4-12B-it-OptiQ-4bit}"
            ;;
        llama|llama31)
            echo "${CORE_AGENT_MLX_MODEL_LLAMA:-mlx-community/Meta-Llama-3.1-8B-Instruct-4bit}"
            ;;
        codegeex|cgx)
            echo "${CORE_AGENT_MLX_MODEL_CODEGEEX:-mlx-community/codegeex4-all-9b-4bit}"
            ;;
        qwen-coder-14b|qwen14)
            echo "${CORE_AGENT_MLX_MODEL_QWEN14:-mlx-community/Qwen2.5-Coder-14B-Instruct-4bit}"
            ;;
        qwen3-coder-heavy|qwen3)
            echo "${CORE_AGENT_MLX_MODEL_QWEN3_CODER:-mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit}"
            ;;
        deepseek|deepseek-coder)
            echo "${CORE_AGENT_MLX_MODEL_DEEPSEEK:-mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit}"
            ;;
        *)
            return 1
            ;;
    esac
}

cache_slug() {
    local repo="$1"
    echo "${HOME}/.cache/huggingface/hub/models--${repo//\//--}"
}

cache_status_one() {
    local alias="$1"
    local repo
    if ! repo="$(repo_for_alias "$alias")"; then
        echo -e "${C_ERR}Unknown alias: $alias${C_RESET}" >&2
        return 1
    fi
    local dir
    dir="$(cache_slug "$repo")"
    printf "${C_BLUE}%-20s${C_RESET} %s\n" "$alias" "$repo"
    if [[ ! -d "$dir" ]]; then
        echo "  cache: (missing)"
        return 0
    fi
    local total incomplete safes
    total="$(du -sh "$dir" 2>/dev/null | cut -f1 || true)"
    incomplete="$(find "$dir" -name '*.incomplete' 2>/dev/null | wc -l | tr -d ' ')"
    safes="$(find "$dir/snapshots" -name '*.safetensors' 2>/dev/null | wc -l | tr -d ' ')"
    echo "  cache: ${total:-?} | safetensors: ${safes} | incomplete_blobs: ${incomplete}"
    if [[ "${incomplete}" != "0" ]]; then
        find "$dir/blobs" -name '*.incomplete' -exec ls -lh {} \; 2>/dev/null | head -5 || true
    fi
}

# Semantic check for active internet. Detects many captive portals.
check_network() {
    curl -s -o /dev/null -w "%{http_code}" http://clients3.google.com/generate_204 | grep -q "204"
}

# In-place dynamic countdown.
dynamic_countdown() {
    local seconds="$1"
    local i
    for ((i=seconds; i>0; i--)); do
        printf "${CLEAR_LINE}${C_WARN}Pausing for %02ds before retry...${C_RESET}" "$i"
        sleep 1
    done
    printf "${CLEAR_LINE}"
}

# Braille spinner for network polling.
wait_for_network() {
    if ! check_network; then
        echo -e "\n${C_WARN}Network dropped or captive portal detected.${C_RESET}"
        echo -e "${C_WARN}Waiting for connection to be restored. Check your browser.${C_RESET}"

        local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
        local i=0

        while ! check_network; do
            printf "${CLEAR_LINE}${C_BLUE}%s${C_RESET} Polling network state..." "${frames[i]}"
            i=$(( (i + 1) % 10 ))
            sleep 0.2
        done
        printf "${CLEAR_LINE}${C_GREEN}Network restored. Resuming operations...${C_RESET}\n"
    fi
}

purge_stale_locks() {
    local repo="$1"
    local cache_repo_name
    cache_repo_name="models--${repo//\//--}"
    local lock_path="${HOME}/.cache/huggingface/hub/.locks/${cache_repo_name}"
    if [[ -d "$lock_path" ]]; then
        rm -rf "$lock_path" 2>/dev/null || true
    fi
}

pull_repo() {
    local alias="$1"
    local repo
    if ! repo="$(repo_for_alias "$alias")"; then
        echo -e "${C_ERR}Unknown alias: $alias${C_RESET}" >&2
        echo "Known aliases: $(known_aliases) gemma-optiq"
        exit 1
    fi

    echo -e "\n${C_BLUE}=======================================================================${C_RESET}"
    echo -e "${C_BLUE}Initiating: ${repo}  (${alias})${C_RESET}"
    echo -e "${C_BLUE}=======================================================================${C_RESET}"

    local attempt=1
    while true; do
        purge_stale_locks "$repo"
        wait_for_network

        "$HF" download "$repo" &
        local hf_pid=$!
        local hf_exit_code=0
        local intercept_detected=0

        while kill -0 "$hf_pid" 2>/dev/null; do
            if ! check_network; then
                echo -e "\n${C_WARN}Network intercept detected. Severing hung hf process...${C_RESET}"
                kill -9 "$hf_pid" 2>/dev/null || true
                wait "$hf_pid" 2>/dev/null || true
                intercept_detected=1
                break
            fi
            sleep 3
        done

        if [[ "$intercept_detected" -eq 0 ]]; then
            wait "$hf_pid" 2>/dev/null || true
            hf_exit_code=$?
        else
            hf_exit_code=1
        fi

        if [[ "$hf_exit_code" -eq 0 ]]; then
            echo -e "${C_GREEN}Successfully synced: ${repo}${C_RESET}"
            cache_status_one "$alias"
            break
        fi

        echo -e "\n${C_ERR}Download interrupted (exit ${hf_exit_code}). Attempt ${attempt} of ${MAX_RETRIES}.${C_RESET}"
        if (( attempt >= MAX_RETRIES )); then
            echo -e "${C_ERR}Max retries reached for ${repo}. Aborting.${C_RESET}"
            exit 1
        fi

        dynamic_countdown "$RETRY_DELAY"
        wait_for_network
        attempt=$((attempt + 1))
    done
}

status_all() {
    echo "Recommended M1 16GB lanes: phi-reasoning + qwen-coder"
    echo "Candidate/heavy lanes are explicit opt-in; do not use them as defaults."
    echo ""
    local alias
    for alias in $(known_aliases); do
        cache_status_one "$alias"
        echo ""
    done
}

case "$MODE" in
    status)
        status_all
        ;;
    fast)
        pull_repo phi-reasoning
        ;;
    primary)
        pull_repo qwen-coder
        ;;
    recommended)
        pull_repo phi-reasoning
        pull_repo qwen-coder
        ;;
    all-safe)
        pull_repo phi-reasoning
        pull_repo qwen-coder
        pull_repo gemma-fast
        pull_repo gemma-primary
        pull_repo llama
        ;;
    candidates)
        echo -e "${C_WARN}Candidate downloads may fail if an MLX community conversion was renamed.${C_RESET}"
        pull_repo codegeex || true
        pull_repo qwen-coder-14b || true
        pull_repo qwen3-coder-heavy || true
        pull_repo deepseek || true
        ;;
    legacy-gemma|gemma-all)
        pull_repo gemma-fast
        pull_repo gemma-primary
        pull_repo gemma-optiq
        ;;
    alias)
        pull_repo "${2:?usage: bash scripts/pull-models-resumable.sh alias <model-alias>}"
        ;;
    *)
        if repo_for_alias "$MODE" >/dev/null 2>&1; then
            pull_repo "$MODE"
            exit 0
        fi
        echo "Usage: bash scripts/pull-models-resumable.sh [status|fast|primary|recommended|all-safe|candidates|legacy-gemma|alias <name>]"
        echo "Known aliases: $(known_aliases) gemma-optiq"
        exit 1
        ;;
esac

echo -e "\n${C_GREEN}Synchronization sequence ended.${C_RESET}"
echo "Current cache status:"
status_all
