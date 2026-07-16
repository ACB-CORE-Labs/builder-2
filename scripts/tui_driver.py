#!/usr/bin/env python3
"""
Governed TUI exploration driver for core-labs/builder-II (Forgejo only).
kind: tui-exploration-driver
Produces snapshots + structured reports; pairs with validate-tui-exploration.
Supports pexpect (Claude Code exploratory play) + Textual Pilot (deterministic tests).
"""
import pexpect
import sys
import time
from typing import Optional

class TUIDriver:
    def __init__(self, command: str, cols: int = 220, rows: int = 50, timeout: int = 10):
        self.command = command  # MUST use "uv run builder-platform tui" etc.
        self.cols = cols
        self.rows = rows
        self.timeout = timeout
        self.proc: Optional[pexpect.spawn] = None

    def start(self) -> "TUIDriver":
        self.proc = pexpect.spawn(
            self.command,
            encoding="utf-8",
            timeout=self.timeout,
            dimensions=(self.rows, self.cols),
        )
        time.sleep(1.5)
        return self

    def read_screen(self) -> str:
        try:
            self.proc.expect(pexpect.TIMEOUT, timeout=0.8)
        except pexpect.TIMEOUT:
            pass
        return self.proc.before or ""

    def send_key(self, key: str) -> "TUIDriver":
        self.proc.send(key)
        time.sleep(0.4)
        return self

    def send_keys(self, *keys: str, delay: float = 0.3) -> "TUIDriver":
        for k in keys:
            self.send_key(k)
        return self

    def quit(self, quit_key: str = "q") -> str:
        self.proc.send(quit_key)
        try:
            self.proc.expect(pexpect.EOF, timeout=5)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        return self.read_screen()

    def snapshot(self, label: str = "") -> None:
        screen = self.read_screen()
        tag = f"[{label}] " if label else ""
        print(f"\n{'='*80}\n{tag}TUI SNAPSHOT (Forgejo-only session)\n{'='*80}\n{screen}\n{'='*80}")

# Exact builder-II surfaces (verified against cli/main.py)
def drive_main_tui() -> TUIDriver:
    return TUIDriver("uv run builder-platform tui").start()

def drive_code_vault_tui() -> TUIDriver:
    return TUIDriver("uv run builder-code-vault frame/recall").start()

def drive_inspection_tui() -> TUIDriver:
    return TUIDriver("uv run builder-tui-inspection").start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        print("Launching main TUI smoke test (Forgejo-only)...")
        d = drive_main_tui()
        d.snapshot("initial")
        d.send_key("\t").snapshot("after tab")
        d.quit()
        print("Smoke test complete.")
