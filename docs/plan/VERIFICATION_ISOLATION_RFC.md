# Verification Isolation RFC (Ladder 9)

## The Crux: Evidence of Isolation
**Finding:** There is *nothing* an isolated run can evidence that an unisolated run could not forge. 

Because builder-II executes locally under the operator's privileges, the trusted component (the verification runner) and an untrusted, unisolated target code share the exact same security domain. If a malicious target code is executed unisolated (the default), it gains full host access. It can trivially synthesize a receipt claiming to have run isolated, including faking container IDs, image digests, and network policies, and write this forged receipt directly to `.builder/ledger/`. Container isolation is a *containment* boundary when active, but locally, it cannot serve as an *attestation* boundary. Without a cryptographic hardware root (TPM/enclave) or an external trusted party holding a signing key inaccessible to the host, local isolation evidence is inherently forgeable by any code that escapes or bypasses it.

## Isolation Backend
**Choice:** `docker` (with fallback to `podman` if aliased or via explicitly configured binary, though we'll assume a `docker` CLI interface).
**Reasoning:** The primary canonical host is an Apple Silicon M1 (macOS). Native Linux namespaces (`bubblewrap`, `nsjail`) do not exist on macOS. While macOS has native sandboxing (`sandbox-exec`), it is deprecated, undocumented, and difficult to reconcile with Linux CI. Docker Desktop / OrbStack provide a ubiquitous CLI interface (`docker run`) that works across both macOS and Linux CI seamlessly. 

## Default Execution Path
**Decision:** The default must remain `none` (unisolated).
**Reasoning:** Dictated by the brief (the default execution path must not change; isolation is opt-in). This preserves behavior parity for existing fixtures and plans.

## Host Resource Remapping
When executing inside the container, the host's `HOME`, `TMPDIR`, `TEMP`, `TMP`, and `sys.executable` must be remapped to prevent the guest from writing to host-derived caches or executing the host's Python interpreter (which won't exist at the same path in the guest).
- `sys.executable`: Mapped to `python3` (or the container's default Python).
- `HOME`: Mapped to `/tmp/home` or a dedicated container-local empty dir.
- `TMPDIR`/`TEMP`/`TMP`: Mapped to `/tmp` in the container.
- `PYTHONPATH`: The `target_repo` must be mounted into the container (e.g., at `/workspace`), and `PYTHONPATH` set to `/workspace`.

## Git Availability
The runner relies on `git` for preflight and postflight state capture.
**Resolution:** The preflight and postflight captures occur on the *host* (in the verification runner), not inside the container. The target code inside the container does not inherently need `git` for the runner to function. If the target code itself requires `git`, the isolation image must have `git` installed. The runner will capture `git status` from the host outside the container boundary. 

## Promotion Gates
To move this capability across a promotion boundary (future PR), the following eight gates would be required:
1. Documentation of the capability.
2. A command surface (plan generation for isolated runs).
3. A failure mode (fail-closed if backend missing/timeout).
4. Human approval boundary (the plan must be approved).
5. Output artifact (the isolation policy and receipt).
6. Rollback path (reverting to unisolated).
7. Verification path (the verification runner itself validating the container execution).
8. Evidence-backed matrix flip (the truth matrix reflecting the new verification state).

## Conclusion
This is a `RECORDED_ONLY` change. It introduces the isolation mechanism and artifact shape but **promotes nothing**. The `none` path proves that existing non-isolated execution remains byte-identical.
