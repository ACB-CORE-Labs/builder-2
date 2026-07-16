#!/usr/bin/env python3
"""
Semantic DOM Extractor & Driver for builder-II TUIs.
Enforces Mechanical Sympathy, Semantic Rigor, and The Third Door.
Target: Apple Silicon M1 (Headless Pilot Execution)
"""
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from textual.app import App

# Load-bearing imports mapped directly to the builder-II architecture
try:
    from builder_ii.tui.app import StratumApp
    from builder_ii.tui_audit_ledger import append_event, build_event, read_chain_head
except ImportError as e:
    print(json.dumps({"error": "CRITICAL_FAILURE", "message": f"Failed to import core applications: {e}"}))
    sys.exit(1)

async def extract_semantic_state(app: App) -> Dict[str, Any]:
    """Extracts a semantic dictionary representation of the UI state."""
    state = {
        "focused_id": app.focused.id if app.focused and app.focused.id else None,
        "active_screen": app.screen.__class__.__name__,
        "widgets": [],
        "notifications": list(notifications_log) # Captured from hook
    }
    
    for widget in app.screen.walk_children():
        if not widget.display:
            continue
            
        w_state = {
            "type": widget.__class__.__name__,
            "id": widget.id,
            "classes": sorted(list(widget.classes)),
        }
        
        if hasattr(widget, "render"):
            try:
                renderable = widget.render()
                text = str(renderable)
                import re
                text = re.sub(r'0x[0-9a-fA-F]+', '0x[MEM_ADDR]', text)
                w_state["text"] = text
            except Exception:
                pass
                
        state["widgets"].append(w_state)
        
    return state

async def run_exploration(app_class, script_steps: List[Dict]):
    """Executes deterministic JSON payloads against the active DOM."""
    # Handle both direct App classes and factory functions
    app = app_class() if isinstance(app_class, type) else app_class
    
    run_id = str(uuid.uuid4())
    global notifications_log
    notifications_log = []
    
    # Hook notify to capture toasts deterministically
    original_notify = app.notify
    def recording_notify(message: str, title: str = "", severity: str = "information", timeout: float = 5.0, **kwargs):
        notifications_log.append({"message": str(message), "title": str(title), "severity": str(severity)})
        return original_notify(message, title=title, severity=severity, timeout=timeout, **kwargs)
    app.notify = recording_notify

    ledger_dir = Path(".builder/artifacts")
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "tui_audit_ledger.jsonl"

    # The chain spans the file, not the run: a new run continues from the last recorded link, so
    # deleting a whole run's block is as detectable as deleting a single line.
    seq, prev_digest = read_chain_head(ledger_path)

    results = {"initial_state": {}, "execution_log": [], "final_state": {}}

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
            target = step.get("target") # Can be an ID ("#btn") or key ("tab")
            step_log = {"step": step, "status": "success", "error": None}
            
            try:
                if action == "press":
                    await pilot.press(target)
                elif action == "click":
                    await pilot.click(target)
                else:
                    step_log["status"] = "ignored"
                    step_log["error"] = f"Unknown action: {action}"
                
                # Deterministic pause to allow the state machine to settle
                await pilot.pause()
            except Exception as e:
                step_log["status"] = "failed"
                step_log["error"] = str(e)
            
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "MISSING_PAYLOAD", "message": "Provide a JSON payload. Example: '{\"app\": \"StratumApp\", \"steps\": []}'"}))
        sys.exit(1)
        
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        print(json.dumps({"error": "INVALID_JSON", "message": "Payload must be valid JSON."}))
        sys.exit(1)

    app_map = {
        "StratumApp": StratumApp,
    }
    
    target_name = payload.get("app")
    target_app = app_map.get(target_name)
    
    if not target_app:
        print(json.dumps({"error": "UNKNOWN_APP", "message": f"App '{target_name}' not found or failed to import."}))
        sys.exit(1)
        
    asyncio.run(run_exploration(target_app, payload.get("steps", [])))
