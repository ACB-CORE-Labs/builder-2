# Security Policy

## Supported versions

builder-II is pre-1.0 (currently versioned `0.1.0`, unreleased/untagged). There is a single
supported line: the tip of `main`. There is no long-term-support branch and no version support
matrix yet; that will be established around the first tagged release (see
[`CHANGELOG.md`](CHANGELOG.md)).

## Reporting a vulnerability

`[host-specific — TBD]` This repository is currently private and not yet open for public
contribution or disclosure. A dedicated security-contact channel (private advisory, security email
alias, or equivalent) will be established when the project is made public — see
[`docs/ROADMAP.md`](docs/ROADMAP.md) for open-sourcing status.

Until that channel exists:

- **Do not** open a public issue describing an exploitable vulnerability.
- If you have access to this repository directly, report the issue to the maintainer through a
  private channel you already have (this repo is not yet publicly accessible, so if you can read
  this file you likely already have one).

When the public channel is live, please include: affected component/file, reproduction steps,
impact, and (if you have one) a suggested fix. We aim to acknowledge reports promptly and to credit
reporters in the fix's changelog entry unless you request otherwise.

## Threat model notes specific to builder-II

builder-II's design is explicit about what its governance boundaries do and don't protect against.
Two things worth knowing before reporting or relying on a given surface:

- **The bounded verification runner is not a sandbox.** `pytest_full` / `builder_full` verification
  profiles execute the target repository's own code (including transitive `conftest.py`/plugin code)
  on the host, with the operator's own privileges. The runner bounds *invocation* (fixed argv,
  env-allowlist, `shell=False`, a required timeout) — it never bounds *what invoked code can do*.
  This is intentional and documented, not a gap to report; see
  [`docs/RUNTIME_PROMOTION.md`](docs/RUNTIME_PROMOTION.md) and the "D7" decision in the project's
  internal completion plan. Container/VM isolation for this lane is explicit future work, not a
  current guarantee.
- **Artifacts are evidence, not authority.** A JSON artifact (plan, approval, receipt) is a record of
  what happened or was approved — it is not itself a security boundary. Authority is enforced by the
  command-authority tier registry and the human-in-the-loop approval gates that consult it, not by
  the mere existence of an artifact file. See
  [`docs/COMMAND_AUTHORITY.md`](docs/COMMAND_AUTHORITY.md).

If you find a case where either of those boundaries is *violated* relative to what the docs claim
(e.g. a mutation lane that bypasses the command-authority gate, or a verification runner that
executes something outside its documented fixed argv), that is a real security bug — please report
it through the channel above once it exists, or directly to the maintainer in the meantime.

## Secret management

Never commit secrets (API keys, tokens, credentials) to this repository. CI runs a high-confidence
secret-pattern scan and Gitleaks on every push; if you accidentally commit a secret, rotate it
immediately regardless of whether CI catches it, since it is present in git history the moment it's
pushed.
