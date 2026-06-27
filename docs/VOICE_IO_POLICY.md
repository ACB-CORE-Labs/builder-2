# Voice I/O Policy

This document formally describes the policy surrounding Voice I/O (STT/TTS) in the builder-II platform.

## Scope

`builder-II` is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. Voice I/O is explicitly governed and currently disabled.

## Current State
*   **Status**: `DESIGN_ONLY`
*   **Runtime**: `DISABLED`

Voice I/O is governed, not invisible. STT/TTS runtime is **not** enabled.

## Denied Behaviors
The following behaviors are strictly prohibited under the current policy:
*   No microphone capture
*   No speaker playback
*   No subprocess invocation (e.g. `rec`, `afplay`, `say`)
*   No Swift compilation
*   No model execution
*   No shell execution
*   No network access
*   No target repo mutation
*   No hidden audio persistence
*   No `builder ask` integration

## Future Capabilities
*   STT and TTS are recognized as future candidate capabilities only.
*   Native macOS APIs, MLX Whisper, and Chatterbox are declared as future optional backends. No current dependencies on these exist.

## Promotion Requirements
For Voice I/O to be promoted from design to an active feature, the following requirements must be met:
*   Docs
*   Tests
*   Command surface
*   Failure mode definition
*   Human approval boundary
*   Output artifact definition
*   Rollback path
*   Verification path
