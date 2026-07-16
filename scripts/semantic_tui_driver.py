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
import os
from pathlib import Path
from typing import Any, Dict, List
from textual.app import App

# Load-bearing imports mapped directly to the builder-II architecture
try:
    from builder_ii.tui.app import StratumApp
    try:
        from builder_ii.cli.tui_inspection_cli import get_inspection_app 
        # Using a factory or mock if code_vault_tui isn't a direct App class
    except ImportError:
        get_inspection_app = None
except ImportError as e:
    print(json.dumps({"error": "CRITICAL_FAILURE", "message": f"Failed to import core applications: {e}"}))
    sys.exit(1)

async def extract_semantic_state(app: App) -> dict:
    """
    Extracts a token-efficient, logically rigorous representation of the UI.
    Explicitly tracks the active screen to detect Governance Modals.
    """
    state: Dict[str, Any] = {
        "active_screen": app.screen.__class__.__name__,
        "focused_id": None, 
        "widgets": []
    }
    
    if app.focused:
        state["focused_id"] = app.focused.id or f"anonymous_{app.focused.__class__.__name__}"

    # Walk only the active screen (this naturally captures modals if they are pushed)
    for widget in app.screen.walk_children():
        w_data = {
            "type": widget.__class__.__name__,
            "id": widget.id,
            "classes": list(widget.classes),
            "display": widget.display,
        }
        
        # Safely extract values without conflating visual render with runtime data
        if hasattr(widget, "value"):
            w_data["value"] = str(widget.value)
        elif hasattr(widget, "render"):
            try:
                rendered = str(widget.render())
                # Truncate strings to protect LLM context windows (Mechanical Sympathy)
                if len(rendered) < 250: 
                    w_data["text"] = rendered
            except Exception:
                pass
                
        state["widgets"].append(w_data)
        
    return state

async def run_exploration(app_class, script_steps: List[Dict]):
    """Executes deterministic JSON payloads against the active DOM."""
    # Handle both direct App classes and factory functions
    app = app_class() if isinstance(app_class, type) else app_class
    
    ledger_dir = Path(".builder/artifacts")
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "tui_audit_ledger.jsonl"
    
    results = {"initial_state": {}, "execution_log": [], "final_state": {}}
    
    async with app.run_test(headless=True) as pilot:
        initial_state = await extract_semantic_state(app)
        results["initial_state"] = initial_state
        
        # Append initial state to ledger
        with open(ledger_path, "a") as f:
            f.write(json.dumps({"timestamp": time.time(), "event": "MOUNT", "state": initial_state}) + "\n")
        
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
            
            # Stream the discrete event and resulting state to the ledger
            with open(ledger_path, "a") as f:
                f.write(json.dumps({
                    "timestamp": time.time(),
                    "event": "ACTION",
                    "action": action,
                    "target": target,
                    "status": step_log["status"],
                    "error": step_log["error"],
                    "resulting_state": current_state
                }) + "\n")
            
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
        "InspectionApp": get_inspection_app
    }
    
    target_name = payload.get("app")
    target_app = app_map.get(target_name)
    
    if not target_app:
        print(json.dumps({"error": "UNKNOWN_APP", "message": f"App '{target_name}' not found or failed to import."}))
        sys.exit(1)
        
    asyncio.run(run_exploration(target_app, payload.get("steps", [])))
