"""Assert that a `builder-*` console script boots STRATUM under a real TTY and exits cleanly.

`docs/CAPABILITY_PROMOTION.md` §7 recorded this as the gap left by retiring the pexpect driver:
`run_test()` constructs the app in-process and never spawns a terminal, so nothing asserted that
the shipped entry point survives contact with an actual tty -- raw mode, terminal size queries,
`tcsetattr`, the capability handshake. Those are exactly the mechanics an in-process harness
cannot exercise, and the ones a host-dependent defect hides in.

Why this is not the banned thing
--------------------------------
§7 forbids "driving a TUI by spawning a pty and reading rendered bytes" *as an evidence method*.
This lane spawns a pty and never uses a byte of what comes back: output is drained and discarded,
and the entire verdict is the process exit code. It asserts nothing about what was painted, so it
cannot rot when a glyph, colour or layout changes -- the failure mode that made the retired
scraper worthless. Draining is not observation here, it is plumbing: see `_boot_under_pty`.

Why the exit code is worth anything at all
------------------------------------------
Only because `run_tui` now propagates it. Measured before that fix: an app whose `on_mount` raises
`RuntimeError` exits `0` -- Textual catches the exception, prints the traceback, and returns
normally, recording the failure only in `App.return_code`, which every launch site discarded.
Asserting `exit == 0` against that would have been the retired driver's defect rebuilt: a green
that is green no matter what. The mutation lane below exists to keep that honest.
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The shipped console script, in the venv running these tests -- the artifact under test is the
#: entry point an operator types, not an in-process construction of the app.
CONSOLE_SCRIPT = Path(sys.executable).parent / "builder-platform"

#: ctrl+q -- STRATUM's quit binding (`app.py`: `Binding("ctrl+q", "quit_app", ...)`).
#: Also byte 0x11 == XON, which is why it must be delivered *after* Textual takes the terminal out
#: of canonical mode; before that the tty driver eats it as flow control. Hence the retry below.
CTRL_Q = b"\x11"

#: Measured boot-to-exit on the M1 target: ~1.4s. 60s is ~40x headroom, so expiry means genuinely
#: wedged rather than merely slow. A timeout fails loudly; it is never reported as a pass.
BOOT_DEADLINE_S = 60.0


def _boot_under_pty(argv: list[str], deadline_s: float = BOOT_DEADLINE_S) -> int:
    """Launch `argv` on a real pty, offer ctrl+q until it quits, and return its exit code.

    Two mechanics here were measured, not assumed, and both are load-bearing:

    **The master must be drained or the app deadlocks.** STRATUM emits ~120KB painting its first
    frame. Left unread, the pty buffer fills and the app blocks *in write* -- it never reaches its
    input reader, so it never sees the quit key and hangs until killed. Three separate attempts to
    write this lane failed exactly this way. The bytes are read solely to keep the pipe moving and
    are dropped on the floor; nothing is parsed and nothing is asserted on them.

    **A key sent before the app reads is gone.** Written at t=0 it is discarded outright and the
    app runs forever. So the key is re-offered on an interval instead of timed: the app takes it
    whenever it is ready, which converges in ~1.4s here and cannot race a slow host. That is the
    difference between this and a sleep-and-read scraper -- there is no budget to expire, and no
    verdict that depends on guessing when boot finished.
    """
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        argv,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        cwd=ROOT,
        env={**os.environ, "TERM": "xterm-256color", "COLUMNS": "120", "LINES": "40"},
    )
    os.close(slave)

    started = time.monotonic()
    next_offer = 0.0
    try:
        while True:
            elapsed = time.monotonic() - started
            returncode = proc.poll()
            if returncode is not None:
                return returncode
            if elapsed > deadline_s:
                proc.kill()
                proc.wait()
                raise AssertionError(
                    f"{argv[0]} never exited within {deadline_s}s of being offered ctrl+q. It "
                    f"booted but will not quit, or it wedged before reading input."
                )
            if elapsed >= next_offer:
                try:
                    os.write(master, CTRL_Q)
                except OSError:
                    pass  # pty already tearing down; the poll above decides the verdict
                next_offer = elapsed + 1.0
            readable, _, _ = select.select([master], [], [], 0.1)
            if readable:
                try:
                    os.read(master, 65536)  # drained and discarded -- never evidence
                except OSError:
                    pass  # slave closed: process is exiting; poll reports the code
    finally:
        try:
            os.close(master)
        except OSError:
            pass


def test_the_console_script_under_test_exists() -> None:
    """Vacuity guard: a missing binary must fail, never silently skip this file's only subject."""
    assert CONSOLE_SCRIPT.exists(), (
        f"{CONSOLE_SCRIPT} not found -- `uv sync` installs it from [project.scripts]. Skipping "
        f"would leave the pty gap open while reporting green."
    )


def test_stratum_boots_under_a_real_tty_and_exits_zero() -> None:
    """The gap §7 names: a shipped console script, a real terminal, a clean exit.

    No visual assertion. If STRATUM raises on mount under a tty -- the class of defect an
    in-process `run_test()` structurally cannot see -- `run_tui` reports Textual's return code and
    this fails.
    """
    returncode = _boot_under_pty([str(CONSOLE_SCRIPT), "tui", "--no-splash", "--no-guide"])

    assert returncode == 0, f"STRATUM exited {returncode} booting under a real pty"


def test_a_boot_crash_under_a_real_tty_is_not_reported_as_success() -> None:
    """The lane above is only worth its runtime if a crash can actually fail it.

    This is the measurement that forced `run_tui` to exist, kept as a permanent lane rather than a
    throwaway probe: Textual swallows an `on_mount` exception, prints the traceback, and returns
    normally, so the process exits `0` unless someone reads `App.return_code`. Any refactor that
    goes back to a bare `app.run()` at a launch site makes this red, which is the only thing
    keeping the sibling test above from being a green that means nothing.

    Deliberately a throwaway app rather than a monkeypatched StratumApp: the claim under test is
    about Textual's exit-code contract and how builder-II honours it, not about STRATUM.
    """
    crashing_app = (
        "import sys\n"
        "from textual.app import App\n"
        "sys.path.insert(0, %r)\n"
        "from builder_ii.tui.app import run_tui\n"
        "class Boom(App):\n"
        "    def on_mount(self):\n"
        "        raise RuntimeError('boom on boot')\n"
        "sys.exit(run_tui(Boom()))\n" % str(ROOT)
    )

    returncode = _boot_under_pty([sys.executable, "-c", crashing_app])

    assert returncode != 0, (
        "an app that raised RuntimeError in on_mount exited 0 -- run_tui is discarding "
        "App.return_code again, and the boot lane beside this one now proves nothing"
    )
