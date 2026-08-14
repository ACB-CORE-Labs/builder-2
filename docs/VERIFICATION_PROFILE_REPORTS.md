# Verification Profile Reports

`builder_ii.verification_profile_report` is a governed planning artifact for verification work.

It renders the selected verification profile into a deterministic report containing planned checks, required evidence, and human operator boundaries. The report is not completed evidence and does not execute any command.

## Scope

The report records:

- selected target profile
- selected agent profile
- selected prompt profile
- selected verification profile
- planned verification checks
- required evidence strings
- optional Goose read-only session plan embedding
- governance fields proving planned-only behavior

## Governance boundary

Verification profile reports are planning artifacts only.

They do not:

- execute commands
- invoke a shell
- import or use `subprocess`
- activate Goose
- activate deepagents
- mutate source files
- mutate memory
- grant runtime authority
- prove that verification passed

Every planned check is emitted with:

```json
{
  "execution_state": "NOT_RUN",
  "human_operator_required": true,
  "completed_evidence_ref": null
}
```

## Report states

The only supported report state is:

```text
PLANNED_ONLY
```

`completed_verification` must remain `false`.

## Validation

A valid report must include:

- `kind: builder_ii.verification_profile_report`
- `schema_version: 1`
- valid target, agent, prompt, and verification profile projections
- at least one planned check
- non-empty required evidence strings
- disabled runtime/model/shell/source-write/memory mutation governance fields
- `artifact_is_authority: false`
- `report_is_completed_evidence: false`
- `core_workbench_coupling: NONE`

## Intended use

This artifact sits after the session workflow and Goose read-only session rendering layers:

```text
target/profile resolution -> session workflow plan -> Goose read-only plan -> verification profile report
```

It prepares the human operator to run verification out of band and capture evidence separately.
