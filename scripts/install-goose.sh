#!/usr/bin/env bash
# Install Codename Goose CLI (AAIF / block-goose-cli).
# NOT the PyPI goose-ai stub package.
set -euo pipefail

GOOSE_DOWNLOAD_CLI_URL="https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh"
# SHA-256 of the script at GOOSE_DOWNLOAD_CLI_URL, pinned 2026-07-07. The upstream "stable" tag is
# mutable, so a mismatch here does not necessarily mean tampering -- it can also mean aaif-goose/goose
# shipped a new stable release. Either way this script refuses to pipe unverified remote content into
# bash; if a mismatch is a legitimate new release, re-verify the new script by hand and update this
# constant.
GOOSE_DOWNLOAD_CLI_SHA256="54d64de9b10befba030d3fdc4f6c316de55557c203abeaa9525c04f450c34280"

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
tmp_installer="$(mktemp)"
curl -fsSL "$GOOSE_DOWNLOAD_CLI_URL" -o "$tmp_installer"
actual_sha256="$(shasum -a 256 "$tmp_installer" | awk '{print $1}')"

if [ "$actual_sha256" != "$GOOSE_DOWNLOAD_CLI_SHA256" ]; then
  echo "error: checksum mismatch for $GOOSE_DOWNLOAD_CLI_URL" >&2
  echo "  expected: $GOOSE_DOWNLOAD_CLI_SHA256" >&2
  echo "  actual:   $actual_sha256" >&2
  echo "This may mean upstream shipped a new 'stable' release, or the download was tampered with." >&2
  echo "Inspect the downloaded script before trusting it: $tmp_installer" >&2
  echo "If it is legitimate, update GOOSE_DOWNLOAD_CLI_SHA256 in scripts/install-goose.sh." >&2
  exit 1
fi

CONFIGURE=false bash "$tmp_installer"
rm -f "$tmp_installer"
export PATH="${HOME}/.local/bin:${PATH}"
goose --version