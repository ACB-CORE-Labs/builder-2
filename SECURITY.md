# Security Policy

## Supported Versions

`builder-II` is an open-source governed engineering control plane. Security fixes and vulnerability remediation are actively applied to the main development line:

| Version Line | Supported | Notes |
| :--- | :--- | :--- |
| `main` (unreleased development line) | **Yes** | Active development; no v1.0.0 tag has been made. |
| `< 0.2.0` | No | Legacy milestone tags. Operators should track `main`. |

The supported Python runtime contract is `Python >=3.12.13, <3.13`.

## Reporting a Vulnerability

We appreciate responsible disclosure of security vulnerabilities.

If you discover a security vulnerability in builder-II:

1. **Do not** open a public issue describing an exploitable vulnerability.
2. If GitHub private vulnerability reporting is enabled for this repository, use that channel. Otherwise, contact the maintainers privately through an established repository-owner channel before disclosure; this repository does not publish a dedicated security email address.
3. In your report, please include:
   - Affected component, command surface, or file path.
   - Exact steps or script to reproduce the issue.
   - Potential impact and risk evaluation.
   - Any suggested patch or remediation (if available).

No response-time SLA or disclosure deadline is promised here. The maintainers will coordinate remediation and disclosure with the reporter when a report is received.

## Threat Model & Governance Boundaries Specific to builder-II

builder-II is explicit about what its governance boundaries protect against, and what they do not:

- **The bounded verification runner is NOT a sandbox.** The `pytest_full` and `builder_full` verification profiles execute the target repository's own code (including transitive `conftest.py`, dependencies, and test plugins) directly on the host with the operator's user privileges. The runner constrains *invocation* (fixed in-code argv, strict environment allowlist, `shell=False`, range-checked timeout), **never what invoked code can do**. Running verification on untrusted target repositories is unsafe.
- **Artifacts are evidence, not authority.** A JSON artifact (such as a plan, receipt, or memory atom) is an auditable record of what was planned, approved, or executed — the file itself is not authority. Runtime authority is enforced fail-closed by the `command_authority` registry and the interactive human-in-the-loop (HITL) approval gates.
- **Approvals bind exact artifact digests.** HITL approval artifacts bind the SHA-256 digest of the proposed mutation or plan. Any subsequent change to the artifact invalidates the approval token.
- **Model outputs are unverified proposals.** Text or code emitted by a model or subagent is never treated as execution clearance or verification truth until validated and approved through a governed lane.

If you observe an operational lane that violates these guarantees (e.g. an unprompted file mutation, a subprocess execution that bypasses the command authority gate, or execution of arbitrary shell strings without explicit approval), that constitutes a high-priority defect.

## Secret Management

Never commit secrets, API keys, tokens, or credentials to any repository or artifact. builder-II local CI runs automated secret detection (`gitleaks` and regex pattern scans). If credentials are ever accidentally committed or exposed in an artifact, rotate them immediately.
