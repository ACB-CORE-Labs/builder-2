# Voice I/O Policy

This document defines the governed policy boundary for future Voice I/O capabilities in the builder-II platform.

## Scope

`builder-II` is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE remains a target profile only.

Voice I/O is governed, not invisible. STT/TTS runtime is not enabled.

## Current State

- `kind`: `builder_ii.voice_io_policy`
- `record_state`: `RECORDED_ONLY`
- `current_state`: `DESIGN_ONLY`
- `runtime_status`: `DISABLED`

## Future Candidate Capabilities

- STT is a future candidate capability only.
- TTS is a future candidate capability only.
- Native macOS, MLX Whisper, and Chatterbox are future backend declarations only.

This PR does not add optional dependencies and does not import any runtime backend.

## Denied Current Behaviors

The following behaviors are denied by policy:

- no microphone capture
- no speaker playback
- no subprocess invocation
- no Swift compilation
- no model execution
- no shell execution
- no network access
- no target repo mutation
- no hidden audio persistence
- no `builder ask` integration

## Governance Boundary

The policy artifact does not grant authority. Its governance fields remain disabled:

- `runtime_execution`: `DISABLED`
- `model_execution`: `DISABLED`
- `shell_execution`: `DISABLED`
- `network_access`: `DISABLED`
- `source_writes`: `DISABLED`
- `memory_mutation`: `DISABLED`
- `artifact_is_authority`: `false`
- `core_workbench_coupling`: `NONE`

## Promotion Requirements

For Voice I/O to move beyond design-only policy, a future PR must provide:

- docs
- tests
- command surface
- failure mode definition
- human approval boundary
- output artifact definition
- rollback path
- verification path

Runtime STT/TTS must not be added until those promotion requirements are satisfied.