#!/usr/bin/env python3
"""
Semantic DOM Extractor & Driver for builder-II TUIs.
Enforces Mechanical Sympathy, Semantic Rigor, and The Third Door.
Target: Apple Silicon M1 (Headless Pilot Execution)

This is a measuring instrument, so its failure modes matter more than its features:

* A widget whose `render()` raises is recorded (`render_error`), never swallowed.
* Extracted text is bounded at `MAX_TEXT_CHARS`, and a truncated field carries a digest of the
  *whole* text so bounding the output does not blind the change detector.
* Apps are constructed through `APP_FACTORIES` with their automation-hostile surfaces off -- most
  importantly the splash, which otherwise owns `app.screen` and is all this driver would observe.
* A step only reports `success` when something was actually there to receive it.
"""
import asyncio
import hashlib
import json
import re
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from textual.app import App

# Private, deliberately: `App._press_keys` normalises a one-character key through this exact
# function before dispatching it, and a reception check that normalised differently would disagree
# with the press it is validating. If Textual moves it, this import fails loudly at startup, which
# is the correct outcome -- far better than silently reporting every `?` as a phantom.
from textual.keys import _character_to_key
from textual.widgets import Input, TextArea

# Load-bearing imports mapped directly to the builder-II architecture
try:
    from builder_ii.tui.app import StratumApp
    from builder_ii.tui_audit_ledger import append_event, build_event, read_chain_head
except ImportError as e:
    print(json.dumps({"error": "CRITICAL_FAILURE", "message": f"Failed to import core applications: {e}"}))
    sys.exit(1)

# One extracted text field is capped here. `EpistemicMatrix` renders 345 characters on STRATUM's
# default screen today, so this is a live branch rather than a guard against a hypothetical.
# (`ThirdDoorGate` renders 426 but carries `display = False`, and the walk below skips hidden
# widgets -- a separate, pre-existing blind spot in this driver, not one this cap introduces.)
MAX_TEXT_CHARS = 250

_MEM_ADDR = re.compile(r"0x[0-9a-fA-F]+")

# Module level so `extract_semantic_state` has something to read regardless of call order.
notifications_log: List[Dict[str, Any]] = []


def _scrub(text: str) -> str:
    """Remove run-to-run noise, so two identical UIs produce one identical `state_digest`."""
    return _MEM_ADDR.sub("0x[MEM_ADDR]", text)


def _bounded_text(text: str) -> Dict[str, Any]:
    """Bound one text field, and stay honest about what bounding cost.

    Truncation is where a change detector goes blind: two renders sharing a 250-character prefix but
    differing after it would record as one state and diff as "unchanged". `text_sha256` is taken
    over the *whole* string, so a change past the cut still moves the digest. Bounded output,
    unbounded detection.
    """
    if len(text) <= MAX_TEXT_CHARS:
        return {"text": text}
    return {
        "text": text[:MAX_TEXT_CHARS],
        "text_truncated": True,
        "text_full_chars": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _render_failure(exc: BaseException) -> Dict[str, Any]:
    """Describe a `render()` that raised, deterministically and within budget.

    The full traceback goes to stderr for the human. It deliberately does not go into the state:
    the state is hashed into `state_digest`, whose entire purpose is that one UI digests to one
    value, and a traceback embeds the absolute path of the checkout it ran in. Two worktrees would
    then digest the same broken widget differently -- losing run-over-run diffing at exactly the
    moment someone is using it to ask "did my fix land?".

    What survives is deterministic and still names the crash: the exception type, its message, and
    the basename:lineno of the innermost frame -- a traceback's actual payload, minus its cost.
    """
    traceback.print_exc(file=sys.stderr)
    frames = traceback.extract_tb(exc.__traceback__)
    where = f"{Path(frames[-1].filename).name}:{frames[-1].lineno}" if frames else "unknown"
    return {
        "render_error": _scrub(f"{type(exc).__name__}: {exc}")[:MAX_TEXT_CHARS],
        "render_error_at": where,
    }


def _key_reception(app: App, key: str) -> Tuple[bool, str]:
    """Would anything actually receive `key` in the app's current state?

    `pilot.press` of an unbound key raises nothing and returns None, so every phantom keypress used
    to record as `status: "success"` -- the driver reporting that it drove something when it drove
    nothing.

    Text inputs are the carve-out: `Input`/`TextArea` consume printable characters through `on_key`
    without declaring a binding, so a letter typed into the palette's search box is genuinely
    handled and must not be called a phantom.
    """
    normalized = _character_to_key(key) if len(key) == 1 and not key.isalnum() else key
    if normalized in app.screen.active_bindings:
        return True, "binding"
    focused = app.focused
    if focused is not None and isinstance(focused, (Input, TextArea)) and len(key) == 1:
        return True, "text_input"
    return False, "nothing"


def _click_reception(app: App, selector: Any) -> Tuple[bool, str]:
    """Is there a displayed widget behind `selector`?

    The predicate is "exists and is displayed", not "exists and is focusable". `PaletteEntry`,
    `SpineItem` and `CapabilityItem` are all `Static` subclasses with `can_focus = False`, yet
    clicking a `PaletteEntry` is the palette's primary interaction -- `CommandPaletteScreen.on_click`
    dismisses with the chosen command. Gating success on focusability would report the single most
    important click in the app as a failure.
    """
    if not isinstance(selector, str):
        return False, "TARGET_NOT_A_SELECTOR"
    try:
        nodes = list(app.screen.query(selector))
    except Exception as exc:
        return False, f"BAD_SELECTOR: {type(exc).__name__}: {exc}"
    if not nodes:
        return False, "NO_SUCH_TARGET"
    if not any(node.display for node in nodes):
        return False, "TARGET_NOT_DISPLAYED"
    return True, "displayed"


async def extract_semantic_state(app: App) -> Dict[str, Any]:
    """Extracts a semantic dictionary representation of the UI state."""
    state: Dict[str, Any] = {
        "focused_id": app.focused.id if app.focused and app.focused.id else None,
        "active_screen": app.screen.__class__.__name__,
        "widgets": [],
        "notifications": list(notifications_log),  # Captured from hook
    }

    for widget in app.screen.walk_children():
        if not widget.display:
            continue

        w_state: Dict[str, Any] = {
            "type": widget.__class__.__name__,
            "id": widget.id,
            "classes": sorted(list(widget.classes)),
        }

        if hasattr(widget, "render"):
            try:
                rendered = _scrub(str(widget.render()))
            except Exception as exc:
                # A widget whose render() raises is the most interesting thing this instrument can
                # find, and `except Exception: pass` deleted precisely that: the crashed widget
                # recorded as one with no text, indistinguishable from an empty one, and the run
                # still exited 0. A driver that hides crashes is worse than no driver, because it
                # is believed.
                w_state.update(_render_failure(exc))
            else:
                w_state.update(_bounded_text(rendered))

        state["widgets"].append(w_state)

    return state


async def run_exploration(
    app_factory: Callable[[], App],
    script_steps: List[Dict],
    ledger_path_override: str | None = None,
) -> None:
    """Executes deterministic JSON payloads against the active DOM."""
    app = app_factory()

    run_id = str(uuid.uuid4())
    global notifications_log
    notifications_log = []

    # Hook notify to capture toasts deterministically
    original_notify = app.notify
    def recording_notify(message: str, title: str = "", severity: str = "information", timeout: float = 5.0, **kwargs):
        notifications_log.append({"message": str(message), "title": str(title), "severity": str(severity)})
        return original_notify(message, title=title, severity=severity, timeout=timeout, **kwargs)
    app.notify = recording_notify

    # Overridable so a caller -- notably a test -- can point the chain at its own file. The chain
    # made this necessary: appending links to one fixed path meant a run's outcome depended on
    # whatever a gitignored file had accumulated, so a stale ledger on any developer's disk could
    # fail a test that has nothing to do with it.
    ledger_path = Path(ledger_path_override or ".builder/artifacts/tui_audit_ledger.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    # The chain spans the file, not the run: a new run continues from the last recorded link, so
    # deleting a whole run's block is as detectable as deleting a single line.
    #
    # A ledger written before the chain existed has no `entry_digest` to continue from, and every
    # ledger already on disk is one of those. Reported as this driver's other failures are -- one
    # line of JSON naming the remedy -- rather than as the raw traceback an uncaught ValueError
    # produces, which would break the driver's "always emits JSON" contract on first run after
    # upgrade for anyone holding an existing file.
    try:
        seq, prev_digest = read_chain_head(ledger_path)
    except ValueError as exc:
        print(json.dumps({
            "error": "LEDGER_CHAIN_UNREADABLE",
            "message": str(exc),
            "remedy": (
                f"Move or delete {ledger_path}, then re-run. A ledger whose tail predates the "
                f"hash chain (or is corrupt) cannot be extended without leaving a gap that no "
                f"later verification could detect, so this refuses rather than appending."
            ),
        }))
        sys.exit(1)

    results: Dict[str, Any] = {"initial_state": {}, "execution_log": [], "final_state": {}}

    async with app.run_test(headless=True) as pilot:
        initial_state = await extract_semantic_state(app)
        results["initial_state"] = initial_state

        entry = build_event(
            seq=seq,
            run_id=run_id,
            timestamp=time.time(),
            event="MOUNT",
            state=initial_state,
            prev_digest=prev_digest,
        )
        append_event(ledger_path, entry)
        seq, prev_digest = seq + 1, entry["entry_digest"]

        for step in script_steps:
            action = step.get("action")
            target = step.get("target")  # Can be an ID ("#btn") for click, or a key ("tab") for press
            step_log: Dict[str, Any] = {"step": step, "status": "success", "error": None}

            try:
                if action == "press":
                    received, how = _key_reception(app, str(target))
                    step_log["reception"] = how
                    # Sent either way. The reception check governs what this driver *claims*, not
                    # what it does: a false negative here would otherwise silently drop a keypress
                    # from a script, turning a reporting bug into a behavioural one.
                    await pilot.press(str(target))
                    if not received:
                        step_log["status"] = "unhandled"
                        step_log["error"] = (
                            f"PHANTOM_KEYPRESS: {target!r} is not bound on "
                            f"{app.screen.__class__.__name__} and no text input holds focus. "
                            f"The key was delivered and nothing was listening."
                        )
                elif action == "click":
                    ok, why = _click_reception(app, target)
                    step_log["reception"] = why
                    if not ok:
                        # Clicking would either raise `NoMatches` or land on nothing; either way
                        # this is not a success, and saying why beats re-deriving it from a stack.
                        step_log["status"] = "failed"
                        step_log["error"] = f"PHANTOM_CLICK: {why} for target {target!r}"
                    else:
                        await pilot.click(target)
                else:
                    step_log["status"] = "ignored"
                    step_log["error"] = f"Unknown action: {action}"

                # Deterministic pause to allow the state machine to settle
                await pilot.pause()
            except Exception as e:
                step_log["status"] = "failed"
                step_log["error"] = f"{type(e).__name__}: {e}"

            results["execution_log"].append(step_log)

            # Extract state immediately after the action settles
            current_state = await extract_semantic_state(app)

            # The payload key is `state` for every event type, MOUNT and ACTION alike -- a
            # consumer should not have to know the event type to find the state it recorded.
            entry = build_event(
                seq=seq,
                run_id=run_id,
                timestamp=time.time(),
                event="ACTION",
                state=current_state,
                prev_digest=prev_digest,
                action=action,
                target=target,
                status=step_log["status"],
                error=step_log["error"],
            )
            append_event(ledger_path, entry)
            seq, prev_digest = seq + 1, entry["entry_digest"]

        results["final_state"] = await extract_semantic_state(app)

    print(json.dumps(results, indent=2))


# A factory per app, not a class: an app's automation-safe construction is part of what this driver
# needs to know about it, and `StratumApp()` bare is not that app.
#
# `show_splash=False` is not a nicety. With the splash on, `push_screen(SplashScreen(...))` in
# `on_mount` makes `app.screen` the splash, and this driver -- which reads `app.screen` -- recorded
# the splash's five widgets on every run it has ever made, never once observing STRATUM. It also
# spawns a Swift/Cocoa subprocess and blocks ~4.6s of wall clock inside a headless test.
# `skip_guide=True` matches the construction every StratumApp test already uses.
APP_FACTORIES: Dict[str, Callable[[], App]] = {
    "StratumApp": lambda: StratumApp(show_splash=False, skip_guide=True),
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "MISSING_PAYLOAD", "message": "Provide a JSON payload. Example: '{\"app\": \"StratumApp\", \"steps\": []}'"}))
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(json.dumps({"error": "INVALID_JSON", "message": "Payload must be valid JSON."}))
        sys.exit(1)

    target_name = payload.get("app")
    target_factory = APP_FACTORIES.get(target_name)

    if not target_factory:
        print(json.dumps({"error": "UNKNOWN_APP", "message": f"App '{target_name}' not found or failed to import."}))
        sys.exit(1)

    asyncio.run(run_exploration(target_factory, payload.get("steps", []), payload.get("ledger_path")))
