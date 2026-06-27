# Governed Handoff Notes

`builder_ii.handoff_note` is a durable governed note artifact for ending or transferring a builder-II session.

It captures what changed, what was verified, what remains risky, and what should happen next without granting authority or pretending that planned checks have passed.

## Scope

A handoff note records:

- target name: `generic`, `builder`, or `core`
- session summary
- changed-files summary
- verification summary
- optional verification evidence references
- optional session workflow plan reference
- optional Goose read-only session plan reference
- optional verification profile report reference
- open risks
- next recommended action
- human review requirement

## Governance boundary

A handoff note does not:

- run commands
- invoke a shell
- use subprocess
- activate Goose
- activate deepagents
- mutate memory
- grant runtime authority
- grant action authority
- claim verification passed without evidence refs
- couple builder-II to CORE Workbench/UI/UX

The only write allowance is explicit artifact output when a human or governed CLI writes the handoff note file.

## Verification claims

Without evidence refs:

```json
{
  "verification_claim": "NOT_CLAIMED",
  "verification_evidence_refs": [],
  "governance": {
    "claims_verification_passed": false
  }
}
```

With evidence refs:

```json
{
  "verification_claim": "EVIDENCE_REFERENCED",
  "governance": {
    "claims_verification_passed": true
  }
}
```

This does not make the note itself proof. It only means the note points to operator-supplied evidence artifacts.

## Valid lifecycle states

```text
DRAFT
READY_FOR_REVIEW
BLOCKED
```

## Expected placement

The handoff note fits after the current read-only workflow stack:

```text
target/profile resolution
-> session workflow plan
-> Goose read-only session plan
-> verification profile report
-> handoff note
```

## Local verification

Recommended focused checks:

```bash
CORE_REPO_PATH=. uv run pytest tests/test_handoff_notes.py tests/test_verification_profile_reports.py tests/test_goose_readonly_session.py tests/test_session_workflow.py tests/test_profile_resolution.py -q
CORE_REPO_PATH=. uv run pytest -q
git diff --check
```
