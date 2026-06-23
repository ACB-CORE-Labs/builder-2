#!/usr/bin/env bash
# Install Codename Goose CLI (AAIF / block-goose-cli).
# NOT the PyPI goose-ai stub package.
set -euo pipefail

if command -v goose >/dev/null 2>&1; then
  echo "goose already installed: $(goose --version)"
  exit 0
fi

if command -v brew >/dev/null 2>&1; then
  echo "Installing via Homebrew..."
  brew install block-goose-cli
  goose --version
  exit 0
fi

echo "Installing via official download script..."
curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh | CONFIGURE=false bash
export PATH="${HOME}/.local/bin:${PATH}"
goose --version