"""CodeVault commercial upsell helpers for open-core fallback seams.

Fires only on genuine fallback (plugin missing, or scan truncation) — never every run.
Preserves the open-core fail-closed CLI voice; optional CODEVAULT_URL for upgrade link.
"""

from __future__ import annotations

import os

DEFAULT_CODEVAULT_URL = (
    "https://github.com/AssetOverflow/builder-II#codevault-paid-commercial-plugin-upgrade"
)


def codevault_url() -> str:
    return os.environ.get("CODEVAULT_URL", DEFAULT_CODEVAULT_URL).strip() or DEFAULT_CODEVAULT_URL


def format_context_scale_upsell() -> str:
    """Canonical hint when an operator reaches the optional commercial boundary."""
    return (
        "[builder-II] This request exceeds the open-core inspection boundary.\n"
        f"→ Upgrade to CodeVault: {codevault_url()}"
    )


# Keep the better live CLI voice; append optional URL line without replacing it.
CODEVAULT_CLI_UPGRADE_MESSAGE = (
    "CodeVault is not installed in this builder-II core distribution. "
    "Install the separately licensed builder-ii-code-vault plugin to enable its "
    "command surface. Core Goose/deepagents/STRATUM/HITL lanes remain fully available.\n"
    f"Inquire / upgrade: {codevault_url()}"
)
