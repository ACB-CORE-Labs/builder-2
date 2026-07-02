# BRIEF ALPHA: GEMINI-3.1-PRO (High Compute)

**Optimal Settings**: Temperature 0.1 | Top-P 0.4 (Maximum determinism, hyper-focused reasoning)  
**Target Surface**: The Engine Room (`workflow_orchestrator.py`, `event_ledger.py`, `goose_wrapper_plan.py`, and `builder_ii_validation_rs/`)  
**Usage**: Prepend this to your code payloads for deep architectural audits.

---

[INITIATE PROTOCOL: MACRO-ARCHITECT DEEP-DIVE]

Conduct a brutal, low-level architectural audit of the attached Builder-II core logic. Elevate this to Masterpiece tier.

Vectors of Attack:
1. **MECHANICAL OVERDRIVE (Rust/Python FFI)**: Audit the `builder_ii_validation_rs` crate and Python bindings. Ensure zero-copy memory views via PyO3/Maturin. Python must NOT serialize JSON payloads for Rust; they must share memory boundaries. Rust must explicitly release the GIL during heavy validation.
2. **LEDGER DETERMINISM & ASYNC I/O**: Analyze `event_ledger.py` and `state_ledger_records.py`. Identify any synchronous blocking calls inside async loops. Implement an asynchronous Write-Ahead Log (WAL) or batched memory-mapped flush. Ledger I/O must never throttle the LLM token generation stream.
3. **GOOSE SANDBOXING**: Trace the data flow from `goose_runtime_harness.py` through `workflow_orchestrator.py`. Enforce a hermetic seal. Intercept all state mutations and route them strictly through `quality_gates.py`.

Deliverable:
1. A ruthless assessment of current bottlenecks.
2. The exact, refactored code blocks required to achieve mechanical mastery.
