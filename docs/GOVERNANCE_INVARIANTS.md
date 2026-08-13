# Cross-artifact governance invariants

builder-II emits multiple governance artifacts before any runtime harness is promoted. These artifacts are allowed to describe future execution plans, but they must not become authority themselves.

This document records the shared invariants that must remain aligned across the current artifact surfaces:

- Goose session manifests;
- Goose read-only candidate audit artifacts;
- bounded Goose read-only inspection artifacts;
- governed deepagents policy artifacts;
- deepagents dependency-readiness artifacts.

## Required shared invariants

Every artifact surface must keep the following common governance fields disabled:

```text
model_execution
agent_construction
shell_execution
command_execution
source_writes
memory_mutation
```

Every artifact must also preserve:

```text
artifact_is_authority = false
core_workbench_coupling = NONE
```

The platform may target CORE as a target profile, but these artifacts must not become CORE Workbench/UI authority and must not claim to drive CORE runtime behavior.

## Runtime execution labels

Most current artifacts keep `runtime_execution = DISABLED`.

The bounded inspection artifact is the only exception. It may label `runtime_execution = READ_ONLY_CANDIDATE_INSPECTION` because it reads explicit operator-requested file metadata. That label must still preserve:

```text
runtime_started = false
goose_process_started = false
```

This is not a Goose process-backed runtime and does not promote model, shell, command, write, memory, or deepagents authority.

## Denied authority families

Every artifact must deny the common authority families:

```text
execute_commands
execute_shell
write_source_files
apply_patches
mutate_memory
call_models
```

Every artifact must also deny runtime start and deepagents construction through the vocabulary appropriate to that artifact family.

Goose-family artifacts deny Goose runtime start and deepagents construction as external authority. Deepagents-family artifacts deny deepagents runtime start and construction through the governed factory path.

## Bounded inspection exception

The only current repository-read exception is bounded read-only inspection.

`builder-goose inspect-readonly` may read only explicit operator-requested relative file paths inside the manifest target repo. It records metadata only:

- relative path;
- byte count;
- SHA-256 digest;
- line count;
- `content_recorded: false`.

It must not record file contents and must not start Goose.

All other current artifact surfaces either deny repository reads as runtime behavior or record that no repository file metadata was read.

## Deepagents compatibility invariant

The governed deepagents policy artifact and dependency-readiness artifact must agree on the optional package and governed factory contract:

```text
package/module = deepagents
factory/export = create_deep_agent
```

Construction is allowed only in `NativeDeepAgentsRuntime` after the readiness gate, exact candidate approval, sealed WRP obligations, and two-key native acknowledgement validate. Policy and readiness artifacts themselves remain passive and cannot construct or authorize the runtime.

## Verification

The invariant suite is intentionally test-only and runtime-free:

```bash
uv run pytest tests/test_cross_artifact_governance.py -q
uv run pytest -q
```

These tests should fail if any artifact silently gains runtime start, model execution, shell/command execution, source writes, memory mutation, authority status, CORE Workbench/UI coupling, or unbounded repository-read authority.
