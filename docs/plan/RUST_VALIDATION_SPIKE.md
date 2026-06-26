# Rust validation spike plan

Status: design-only spike plan.

This document defines how builder-II should evaluate Rust-backed artifact validation and processing without turning Rust into hidden runtime authority or a premature hard dependency.

## Purpose

Rust may eventually improve validation throughput, artifact processing, and deterministic parsing for stable schemas. It should not be introduced because it feels sophisticated. It should be introduced only where measurement proves value and deterministic parity can be maintained.

The starting position is:

```text
Python validators are the reference implementation.
Rust validators are candidate accelerators.
Parity and failure-mode tests decide promotion.
```

## Non-goals

This spike does not authorize:

- rewriting all validators in Rust;
- making Rust a required dependency before evidence exists;
- runtime execution;
- Goose start;
- shell execution;
- command execution;
- model calls;
- deepagents construction;
- source mutation;
- memory mutation;
- commits, pushes, or PR creation;
- source collection, web search, or MCP execution.

## Candidate validation surfaces

The best first candidates are stable artifact schemas with clear invariants:

- Goose session manifests;
- read-only runtime audit artifacts;
- bounded inspection audit artifacts;
- target bundle artifacts;
- verification profile artifacts;
- quality gate artifacts;
- research plan artifacts;
- handoff artifacts;
- future linked artifact audit records;
- future compatibility reports;
- future memory atom envelopes.

Avoid first:

- command execution artifacts;
- patch application artifacts;
- model routing execution;
- runtime memory mutation;
- anything that may still change schema rapidly.

## Measurement-first sequence

### Step 1: Benchmark Python validators

Add a benchmark command or script that measures current Python validation cost.

Inputs:

- artifact kind;
- artifact size;
- number of artifacts;
- valid/invalid mix;
- repeated runs.

Outputs:

```json
{
  "kind": "builder_ii.validation_benchmark",
  "schema_version": 1,
  "validator_backend": "python",
  "artifact_kind": "builder_ii.goose_session_manifest",
  "artifact_count": 1000,
  "bytes_total": 123456,
  "valid_count": 900,
  "invalid_count": 100,
  "duration_ms": 0,
  "p50_ms": 0,
  "p95_ms": 0,
  "p99_ms": 0,
  "artifact_is_authority": false
}
```

### Step 2: Identify actual hot paths

Rust should only be considered if one of these is true:

- Python validation cost becomes material in normal operator workflows;
- artifact count grows enough that batch validation is slow;
- validation needs strict parsing guarantees that Rust can improve;
- canonicalization/hashing becomes a measurable bottleneck;
- deterministic schema parity can be proven cheaply.

### Step 3: Define Rust crate boundary

If justified, create a narrow crate boundary such as:

```text
builder_ii_validation_rs
```

Allowed responsibilities:

- parse known JSON artifact shapes;
- validate stable required fields;
- validate denied-action invariants;
- compute canonical JSON hash helpers if needed;
- return structured errors.

Denied responsibilities:

- reading arbitrary files;
- executing commands;
- starting Goose;
- calling models;
- constructing agents;
- mutating source;
- deciding runtime authority.

### Step 4: Keep Python as reference

Rust output must match Python output for:

- valid artifacts;
- missing required fields;
- wrong `kind`;
- wrong `schema_version`;
- authority flags set to true;
- denied-action omissions;
- malformed JSON;
- unexpected types;
- future schema versions.

### Step 5: Add parity artifacts

Parity reports should look like:

```json
{
  "kind": "builder_ii.validation_parity_report",
  "schema_version": 1,
  "artifact_kind": "builder_ii.goose_session_manifest",
  "python_validator_version": "...",
  "rust_validator_version": "...",
  "cases_total": 0,
  "matches": 0,
  "mismatches": [],
  "rust_promoted": false,
  "artifact_is_authority": false
}
```

No Rust validator may replace Python reference until parity is stable.

## Failure modes

Rust validation must fail closed when:

- JSON is malformed;
- schema version is unsupported;
- artifact kind is unknown;
- a required invariant is missing;
- a field type is unexpected;
- Rust/Python parity differs;
- the Rust extension is unavailable.

Fallback rule:

```text
If Rust is unavailable or mismatched, use Python reference validation.
If Python validation is unavailable, fail closed.
```

## Promotion ladder

### Phase 0: RFC/spike plan

- This document.
- No implementation.

### Phase 1: Python benchmark artifact

- Add benchmark command for existing Python validators.
- No Rust dependency.

### Phase 2: Rust feasibility spike

- Add optional Rust crate behind explicit dev feature or separate package boundary.
- No production default.

### Phase 3: parity tests

- Test Python and Rust validators on the same fixtures.
- Report mismatches.

### Phase 4: optional acceleration

- Allow explicit opt-in Rust validation when installed.
- Python remains reference.

### Phase 5: promotion consideration

Only consider wider use if:

- benchmark gain is meaningful;
- parity is stable;
- failure mode is clear;
- rollback is documented;
- package installation remains manageable;
- no runtime authority is introduced.

## Benchmark fixture set

Create fixtures for each artifact kind:

- minimal valid artifact;
- maximal valid artifact;
- missing kind;
- wrong schema version;
- missing target profile;
- missing denied action;
- `artifact_is_authority: true`;
- enabled runtime flag;
- malformed JSON;
- unknown future schema version.

## Rollback path

Rollback is simple if Rust remains optional:

- disable Rust backend;
- remove optional package feature;
- use Python reference validator;
- keep benchmark/parity artifacts for diagnosis.

## Acceptance criteria for first implementation

A future implementation PR must include:

- Python benchmark command or script;
- benchmark artifact schema;
- benchmark docs;
- fixture set;
- no Rust hard dependency;
- no runtime behavior;
- no shell/command/model/deepagents/source mutation authority;
- explicit statement that Python remains reference.

## Governing sentence

Rust may accelerate stable artifact validation only after measurement and parity evidence. It must never become a hidden runtime authority, dependency trap, or bypass around builder-II governance.
