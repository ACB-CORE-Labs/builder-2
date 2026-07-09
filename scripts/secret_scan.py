#!/usr/bin/env python3
"""High-confidence secret scan (blocking CI gate).

Extracted verbatim from the inline heredoc that previously lived in
`.github/workflows/ci.yml`, so that the gate has exactly one definition and can
be run locally by `scripts/ci.sh` rather than reproduced by hand.

Scope note: this is a *high-confidence* scan -- four vendor-prefixed key shapes
with low false-positive rates. It is deliberately not a general entropy scanner;
broad coverage is gitleaks' job (advisory, workflow-only). A pass here means
"no obviously-live vendor key is committed", never "no secrets are committed".

The four patterns do not match their own source text, so this file needs no
self-exclusion and none is granted -- a real key pasted here would still fail
the scan.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_]{32,}"),
    re.compile(r"gsk_[A-Za-z0-9_]{32,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
)

# tests/ and docs/ carry illustrative fake keys by design.
EXCLUDED_PREFIXES: tuple[str, ...] = ("tests/", "docs/")

SKIPPED_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".gif", ".pdf", ".lock"})


def tracked_files() -> list[str]:
    return subprocess.check_output(["git", "ls-files"], text=True).splitlines()


def scan() -> list[str]:
    hits: list[str] = []
    for name in tracked_files():
        if name.startswith(EXCLUDED_PREFIXES):
            continue
        path = pathlib.Path(name)
        if path.suffix in SKIPPED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                hits.append(f"{name}: {pattern.pattern}")
    return hits


def main() -> int:
    hits = scan()
    if hits:
        print("Potential secrets detected:")
        print("\n".join(hits))
        return 1
    print("secret scan: no high-confidence vendor keys found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
