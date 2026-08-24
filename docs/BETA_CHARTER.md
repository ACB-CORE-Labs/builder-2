# Beta Charter

This document outlines the scope and goals for builder-II's beta evaluation: who it is for, what feedback is actively solicited, what is out of scope, and how to submit findings.

---

## 1. Operating Posture & Ground Truth

builder-II relies on a machine-checked truth matrix (`builder_ii/core/platform_completion_audit.py`) rather than narrative claims. Before evaluating capabilities, check the ground truth state:

```bash
# Check current verified capability counts
uv run builder-platform status

# Inspect full completion matrix
uv run builder-platform matrix

# Audit documentation against false-completion claims
uv run builder-platform audit-docs
```

For a comprehensive list of unpromoted capabilities generated directly from the matrix, consult [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

---

## 2. Who This Is For

Engineers and builders comfortable working from the terminal, inspecting typed JSON artifacts, and evaluating human-in-the-loop governance boundaries. We seek feedback from operators exercising the governed loop on real target repositories.

---

## 3. Scope: What the Verification Lane Covers (D7)

The bounded verification runner targets **trusted local repositories with a Python/pytest test suite**, invoked with a fixed argv, `shell=False`, environment allowlist, and a range-checked timeout.

- The bounded runner constrains **invocation**, not what invoked code does on your machine.
- It is **NOT a sandbox**. Target-executing profiles (`pytest_full`, `builder_full`) execute with the operator's host privileges.
- Testing on untrusted repositories is out of scope.

---

## 4. The Governed Demo Loop (Fastest Validation Path)

To experience the entire governed loop in under 5 minutes:

```bash
uv run builder-platform demo-loop --target-repo . --target-name self-test
uv run builder-platform validate-demo-loop
```

This runs the complete **propose $\rightarrow$ approve $\rightarrow$ apply $\rightarrow$ verify $\rightarrow$ rollback** sequence against a temporary detached worktree. The source checkout is never mutated.

---

## 5. What Feedback Is Wanted

1. **Governance Model Legibility:** Does the propose $\rightarrow$ approve $\rightarrow$ apply $\rightarrow$ verify $\rightarrow$ rollback lifecycle feel natural and clear?
2. **Onboarding & Mechanics:** Friction in `uv sync`, environment setup, or running `bash scripts/clean-clone-smoke.sh`.
3. **HITL Ergonomics:** The interactive confirmation prompt (typing the first 4 characters of the SHA-256 digest prefix) — does it provide clear, tamper-evident control without unnecessary friction?
4. **Docs-Truth Accuracy:** Any discrepancy between documented behavior and command execution.
5. **Validator Robustness:** Any malformed artifact that fails to trigger a fail-closed validator refusal.

---

## 6. What Is Out of Scope for this Release

- Container/VM sandbox isolation for arbitrary untrusted code execution.
- Autonomous background agents with unprompted write/push permissions.
- CodeVault geometric extraction (which is part of the separate commercial plugin `core-labs/builder-ii-code-vault`).

---

## 7. How to Send Feedback

Submit feedback and issue reports via the project's issue tracker or security reporting channels (see [`SECURITY.md`](../SECURITY.md)). Include the exact command line executed, the expected behavior, and the generated JSON receipt or error trace.

