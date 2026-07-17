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
from textual.dom import DOMNode

# Private, deliberately: `App._press_keys` normalises a one-character key through this exact
# function before dispatching it, and a reception check that normalised differently would disagree
# with the press it is validating. If Textual moves it, this import fails loudly at startup, which
# is the correct outcome -- far better than silently reporting every `?` as a phantom.
from textual.keys import _character_to_key
from textual.widgets import Input, TextArea

# Load-bearing imports mapped directly to the builder-II architecture
try:
    from builder_ii.tui.app import StratumApp
    from builder_ii.tui_audit_ledger import (
        MASTER_INDEX_FILENAME,
        append_event,
        append_run_to_index,
        build_event,
        read_chain_head,
    )
except ImportError as e:
    print(json.dumps({"error": "CRITICAL_FAILURE", "message": f"Failed to import core applications: {e}"}))
    sys.exit(1)

# One extracted text field is capped here. `EpistemicMatrix` (340 characters) and `ThirdDoorGate`
# (421-525, depending on its state) both exceed it on STRATUM's default screen, so this is a live
# branch rather than a guard against a hypothetical -- which is why `_bounded_text` digests the
# whole string: a `ThirdDoorGate` verdict lives past character 250 and would otherwise be invisible
# to the change detector.
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


def _is_visible(widget: DOMNode) -> bool:
    """Would an operator actually see this widget right now?

    Deliberately neither of Textual's two look-alike properties, because each answers a different
    question and neither answers this one:

    * `widget.display` is the node's **own** `display` rule. A shown widget inside a hidden
      container reports `True` from it while being unseeable, so it cannot be reported as
      "visible" without lying.
    * `widget.visible` is the `visibility` rule -- a *different* CSS concept, under which Textual
      still reserves layout space. It already inherits from ancestors; `display` does not.

    So `display` is walked up the ancestor chain by hand and `visible` is consulted for the rule it
    actually owns. Both must hold. The distinction is worth the words: this driver has already been
    burned once by a name that meant something else in the layer underneath it.
    """
    node: DOMNode | None = widget
    while node is not None:
        if not node.display:
            return False
        node = node.parent
    return bool(getattr(widget, "visible", True))


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

    # Every mounted widget, hidden ones included. Skipping `display = False` made the instrument
    # blind to exactly the widgets worth asserting on: `ThirdDoorGate` -- the HITL gate -- is
    # mounted with `display = False` and revealed by mode, so "is the gate mounted and waiting?"
    # was unanswerable, and a gate that vanished from the DOM entirely looked identical to one
    # merely hidden. Measured on STRATUM's default screen: 37 widgets reported, 39 mounted.
    for widget in app.screen.walk_children():
        w_state: Dict[str, Any] = {
            "type": widget.__class__.__name__,
            "id": widget.id,
            "classes": sorted(list(widget.classes)),
            "visible": _is_visible(widget),
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

    # Hook notify to capture toasts deterministically -- while changing nothing about them.
    #
    # The previous hook restated Textual's signature and got it wrong twice, in opposite
    # directions. It defaulted `timeout` to a hardcoded `5.0`, but `App.notify` defaults it to
    # `None` and resolves that to `self.NOTIFICATION_TIMEOUT`; an app that tunes that class
    # attribute had its setting silently overridden the moment it was observed. And it accepted
    # `title`/`severity`/`timeout` positionally where Textual makes them keyword-only, so
    # `notify("x", "title")` -- a `TypeError` in production -- succeeded under the driver. Both are
    # the same defect: an instrument that reports on mechanics it is itself changing.
    #
    # Forwarding `**kwargs` untouched fixes both at once. Textual's own signature stays the only
    # authority on defaults and on what is even callable, because this hook no longer has an
    # opinion. The resolved timeout is *recorded* rather than imposed, so what the notification
    # actually got is observable without the observation deciding it.
    original_notify = app.notify

    def recording_notify(message: Any, **kwargs: Any) -> Any:
        timeout = kwargs.get("timeout")
        notifications_log.append({
            "message": str(message),
            "title": str(kwargs.get("title", "")),
            "severity": str(kwargs.get("severity", "information")),
            "timeout": app.NOTIFICATION_TIMEOUT if timeout is None else timeout,
        })
        return original_notify(message, **kwargs)

    app.notify = recording_notify

    # One ledger per run, because one shared ledger was not merely untidy -- it was incorrect.
    # Two runs appending to a single file both read the same chain head and both wrote from it,
    # forking the chain. Measured: two concurrent runs produced four events in which every link
    # after the first was broken, so the validator reported a file that no tampering had touched
    # as "an event was deleted, reordered, or rewritten". Concurrency corrupted the evidence and
    # then made the corruption indistinguishable from an attack. The run id already scopes the
    # events; scoping the file to match costs nothing and bounds the file to one run's growth
    # instead of every run this checkout ever made.
    #
    # An explicit override is still honoured verbatim -- tests point the chain at `tmp_path`, and
    # continuing an existing file is exactly how the legacy-ledger refusal below stays reachable.
    ledger_path = Path(ledger_path_override or f".builder/artifacts/tui_audit_ledger_{run_id}.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    # The chain spans the file: a run continues from the last recorded link in whatever file it was
    # pointed at. Across files, `append_run_to_index` is what makes a deleted run detectable -- this
    # comment used to claim the per-file chain did that, which stopped being true the moment the
    # ledger was split per run and stayed on the page anyway.
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

    # The master index lives beside the ledgers it anchors, so an explicit `ledger_path` (tests,
    # tmp_path) carries its own index with it rather than reaching into the real artifacts dir.
    index_path = ledger_path.parent / MASTER_INDEX_FILENAME

    # `ledger_path` is reported because it is no longer predictable. A fixed filename could be
    # named in a doc and found later; a per-run one cannot, and an audit record nobody can locate
    # is not a record. `run_id` ties the file's contents to this output.
    results: Dict[str, Any] = {
        "run_id": run_id,
        "ledger_path": str(ledger_path),
        "index_path": str(index_path),
        "initial_state": {},
        "execution_log": [],
        "final_state": {},
    }

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

    # Anchor the completed run. Deliberately after the app closes and outside the `async with`: a
    # run that crashed mid-exploration has not finished, and indexing a partial chain as if it were
    # a whole one would make the index's event_count a lie on exactly the runs worth inspecting.
    # The cost is that a crashed run leaves an unindexed ledger, which is why `validate_master_index`
    # does not treat one as tampering.
    index_entry = append_run_to_index(
        index_path,
        run_id=run_id,
        ledger_path=ledger_path,
        timestamp=time.time(),
    )
    results["index_entry_digest"] = index_entry["entry_digest"]

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
