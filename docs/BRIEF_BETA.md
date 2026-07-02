# BRIEF BETA: GEMINI-3.5-FLASH (High Context)

**Optimal Settings**: Temperature 0.25 | Top-P 0.8 (Fast execution, wide-context pattern matching)  
**Target Surface**: The Sprawl (60+ `*_cli.py` files, `tui/app.py`, `stratum.tcss`, schemas)  
**Usage**: Prepend this to your massive directory dumps for sweeping refactors.

---

[INITIATE PROTOCOL: TACTICAL REFACTOR & UI POLISH]

Execute a high-velocity structural cleanup, UI optimization, and semantic lockdown on the attached Builder-II modules. 

Vectors of Attack:
1. **CLI CONSOLIDATION (Third Door)**: The root directory is polluted with 60+ `*_cli.py` files. Architect a highly efficient, lazy-loaded routing module (using `typer` or `click` with lazy imports). Drop startup time to near-zero and clean up IDE indexing.
2. **THE MASTERPIECE TUI**: Audit `tui/app.py` and `hitl_tui.py`. Ensure the `asyncio` event loop driving the TUI is NEVER blocked by backend processes (ledger writes, heavy regex, LLM polling). Implement pub/sub signaling or background workers to ensure 60 FPS fluidity.
3. **SEMANTIC SWEEP**: Enforce Strict Pydantic V2 schemas (`model_config = ConfigDict(strict=True, frozen=True)`) and complete Python type hinting across all models. Eradicate `Any` types.

Deliverable:
1. The structural plan for consolidation.
2. The exact, copy-paste-ready refactored code for the UI/CLI layers.
