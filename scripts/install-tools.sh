#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-required}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required installer: $1" >&2
    exit 1
  fi
}

have() {
  command -v "$1" >/dev/null 2>&1
}

brew_installed() {
  brew list "$1" >/dev/null 2>&1
}

brew_install_cmd() {
  local pkg="$1"
  local cmd="$2"
  need brew
  if have "$cmd"; then
    echo "ok: $cmd already available at $(command -v "$cmd")"
    return
  fi
  if brew_installed "$pkg"; then
    echo "ok: brew package $pkg already installed"
    return
  fi
  echo "install: brew install $pkg"
  brew install "$pkg"
}

brew_install_cmd_with_npm_fallback() {
  local pkg="$1"
  local cmd="$2"
  local npm_pkg="$3"
  if have "$cmd"; then
    echo "ok: $cmd already available at $(command -v "$cmd")"
    return
  fi
  need brew
  echo "install: brew install $pkg"
  if brew install "$pkg"; then
    return
  fi
  echo "warn: brew install $pkg failed; falling back to npm install -g $npm_pkg"
  need npm
  npm install -g "$npm_pkg"
}

brew_cask_install() {
  need brew
  for pkg in "$@"; do
    if brew list --cask "$pkg" >/dev/null 2>&1; then
      echo "ok: brew cask $pkg already installed"
    else
      echo "install: brew install --cask $pkg"
      brew install --cask "$pkg"
    fi
  done
}

uv_tool_install_cmd() {
  local package="$1"
  local cmd="$2"
  if have "$cmd"; then
    echo "ok: $cmd already available at $(command -v "$cmd")"
    return
  fi
  need uv
  echo "install/update: uv tool install $package"
  uv tool install "$package"
}

npm_global_install_cmd() {
  local package="$1"
  local cmd="$2"
  if have "$cmd"; then
    echo "ok: $cmd already available at $(command -v "$cmd")"
    return
  fi
  need npm
  echo "install/update: npm install -g $package"
  npm install -g "$package"
}

install_required() {
  brew_install_cmd_with_npm_fallback repomix repomix repomix
  brew_install_cmd semgrep semgrep
  brew_install_cmd ruff ruff
  brew_install_cmd ripgrep rg
  brew_install_cmd gh gh
}

install_tier1() {
  install_required
  brew_install_cmd fd fd
  brew_install_cmd pyright pyright
  uv_tool_install_cmd pre-commit pre-commit
  echo "info: serena is run with uvx when needed; no persistent install is required here"
}

install_tier2() {
  brew_install_cmd ast-grep ast-grep
  uv_tool_install_cmd aider-chat aider
  npm_global_install_cmd promptfoo promptfoo
}

install_notes() {
  echo "info: markdown-vault requires no install"
  brew_cask_install logseq zettlr
  echo "info: Foam is a VS Code extension; install manually if desired"
  echo "info: Obsidian is proprietary and optional; install manually only if desired"
}

show_status() {
  for cmd in repomix semgrep ruff rg gh fd pyright pre-commit aider ast-grep promptfoo; do
    if have "$cmd"; then
      echo "PASS $cmd -> $(command -v "$cmd")"
    else
      echo "MISS $cmd"
    fi
  done
  echo "PASS markdown-vault -> no install required"
}

case "$MODE" in
  required)
    install_required
    ;;
  tier1)
    install_tier1
    ;;
  tier2)
    install_tier2
    ;;
  notes)
    install_notes
    ;;
  all)
    install_tier1
    install_tier2
    install_notes
    ;;
  status)
    show_status
    ;;
  *)
    cat <<'USAGE'
Usage: bash scripts/install-tools.sh [required|tier1|tier2|notes|all|status]

Modes:
  required  Install required external tools only: repomix, semgrep, ruff, ripgrep, gh.
  tier1     Install required tools plus fd, pyright, pre-commit. Serena remains uvx-on-demand.
  tier2     Install optional agent/dev tools: ast-grep, aider-chat, promptfoo.
  notes     Install optional open-source Markdown UIs: Logseq and Zettlr.
  all       Install tier1, tier2, and notes tools.
  status    Print PATH status without installing anything.
USAGE
    exit 2
    ;;
esac
