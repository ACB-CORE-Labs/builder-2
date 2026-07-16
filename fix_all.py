import re
from pathlib import Path

# 1. builder_ii/tui/widgets/palette.py
p = Path("builder_ii/tui/widgets/palette.py")
content = p.read_text()
# imports
content = content.replace(
    "from textual.widgets import Input, Static",
    "from textual.widgets import Input, Static\nfrom textual import events"
)
# _tier_labels
tier_replacement = '''
    def _tier_labels() -> dict[str, tuple[str, str, str]]:
        from builder_ii.tui_theme import theme_palette
        from builder_ii.command_authority import TIER_0, TIER_1, TIER_2, TIER_3, TIER_4

        p = theme_palette()
        return {
            TIER_0: ("T0", p["pass"], "READ-ONLY"),
            TIER_1: ("T1", p["active"], "ARTIFACT-ONLY"),
            TIER_2: ("T2", p["accent"], "OPERATOR"),
            TIER_3: ("T3", p["warn"], "HITL-GATED"),
            TIER_4: ("T4", p["fail"], "FORBIDDEN"),
        }'''
content = re.sub(r'\s*def _tier_labels\(\) -> dict\[str, tuple\[str, str, str\]\]:.*?(?=    def _build_entries)', tier_replacement + '\n\n', content, flags=re.DOTALL)

# _build_entries
build_repl = '''    def _build_entries(self) -> None:
        """Build palette entries from command records."""
        from builder_ii.command_authority import TIER_4
        # Sort by tier, then by name
        sorted_cmds = sorted(
            self._commands,
            key=lambda c: (c.get("tier", TIER_4), c.get("name", "")),
        )
        for cmd in sorted_cmds:
            entry = PaletteEntry(
                cmd_name=cmd.get("name", "unknown"),
                tier=cmd.get("tier", TIER_4),'''
content = re.sub(r'    def _build_entries\(self\) -> None:\n.*?tier=cmd\.get\("tier", "TIER_0"\),', build_repl, content, flags=re.DOTALL)

# on_static_click -> on_click
content = content.replace("def on_static_click(self, event: Static.Click) -> None:", "def on_click(self, event: events.Click) -> None:")

p.write_text(content)

# 2. builder_ii/tui/app.py
p = Path("builder_ii/tui/app.py")
c = p.read_text()
c = c.replace('self.tier = "TIER_0"', 'from builder_ii.command_authority import TIER_0\n        self.tier = TIER_0')
p.write_text(c)

# 3. tests/test_stratum_tui.py
p = Path("tests/test_stratum_tui.py")
c = p.read_text()
c = c.replace('from builder_ii.tui.app import StratumApp', 'from builder_ii.tui.app import StratumApp\nfrom builder_ii.command_authority import TIER_0')
c = c.replace('mock_settings.return_value.model_tier = "TIER_0"', 'mock_settings.return_value.model_tier = TIER_0')
p.write_text(c)

# 4. tests/test_stratum_guide.py
p = Path("tests/test_stratum_guide.py")
c = p.read_text()
c = c.replace('from builder_ii.tui.app import StratumApp', 'from builder_ii.tui.app import StratumApp\nfrom builder_ii.command_authority import TIER_0')
c = c.replace('mock_settings.return_value.model_tier = "TIER_0"', 'mock_settings.return_value.model_tier = TIER_0')
p.write_text(c)

# 5. scripts/semantic_tui_driver.py
p = Path("scripts/semantic_tui_driver.py")
c = p.read_text()
c = c.replace("import time\nimport os", "import time\nimport os\nimport uuid\nimport hashlib")

run_exp_replacement = """    # Generate Third Door run ID
    run_id = str(uuid.uuid4())
    notifications_log = []
    
    # Hook notify to capture toasts deterministically
    original_notify = app.notify
    def recording_notify(message: str, title: str = "", severity: str = "information", timeout: float = 5.0, **kwargs):
        notifications_log.append({"message": str(message), "title": str(title), "severity": str(severity)})
        return original_notify(message, title=title, severity=severity, timeout=timeout, **kwargs)
    app.notify = recording_notify

    ledger_dir = Path(".builder/artifacts")"""
c = c.replace('    ledger_dir = Path(".builder/artifacts")', run_exp_replacement)

# extract_semantic_state replace
extract_repl = '''async def extract_semantic_state(app: App) -> Dict[str, Any]:
    """Extracts a semantic dictionary representation of the UI state."""
    state = {
        "focused": app.focused.id if app.focused and app.focused.id else None,
        "screen": app.screen.__class__.__name__,
        "widgets": [],
        "notifications": list(notifications_log) # Captured from hook
    }
    
    for widget in app.screen.walk_children():
        if not widget.is_visible:
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
                # Sanitize memory addresses
                text = re.sub(r'0x[0-9a-fA-F]+', '0x[MEM_ADDR]', text)
                w_state["text"] = text
            except Exception:
                pass
                
        state["widgets"].append(w_state)
        
    return state'''
c = re.sub(r'async def extract_semantic_state.*?return state', extract_repl, c, flags=re.DOTALL)

# ledger append 1
append1_repl = """        entry = {
            "kind": "builder_ii.tui_audit_ledger_event",
            "run_id": run_id,
            "timestamp": time.time(),
            "event": "MOUNT",
            "state": initial_state
        }
        entry["digest"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\\n")"""
c = re.sub(r'        with open\(ledger_path, "a"\) as f:\n.*?f\.write\(json\.dumps\(\{"timestamp".*?\n', append1_repl + '\n', c, flags=re.DOTALL)

# ledger append 2
append2_repl = """            # Extract state immediately after the action settles
            current_state = await extract_semantic_state(app)
            
            entry = {
                "kind": "builder_ii.tui_audit_ledger_event",
                "run_id": run_id,
                "timestamp": time.time(),
                "event": "ACTION",
                "action": action,
                "target": target,
                "status": step_log["status"],
                "error": step_log["error"],
                "resulting_state": current_state
            }
            entry["digest"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
            with open(ledger_path, "a") as f:
                f.write(json.dumps(entry) + "\\n")"""
c = re.sub(r'            # Extract state immediately after the action settles.*?            with open\(ledger_path, "a"\) as f:\n.*?f\.write\(json\.dumps\(\{.*?\}\) \+ "\\n"\)\n', append2_repl + '\n', c, flags=re.DOTALL)

p.write_text(c)

