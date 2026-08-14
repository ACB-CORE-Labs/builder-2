# Role capability gates

Role capability gates define what each builder-II persona is allowed to do today.

These gates do not add execution authority. They document and test the current boundary so later tool work can tighten or promote capabilities deliberately.

## Capabilities

| Capability | Default status | Meaning |
| --- | --- | --- |
| `direct_ask` | `ALLOWED` | The persona may be used with direct local chat prompts. |
| `goose_planning` | `ALLOWED` | The persona may be used in governed Goose planning/review sessions. |
| `goose_tool_execution` | `UNSUPPORTED` | Local Goose tool execution through MLX is not validated. |
| `file_editing` | `OPERATOR_ONLY` | File edits require explicit operator action and verification. |
| `runtime_switch` | `OPERATOR_ONLY` | Runtime/model switching must be explicit. |
| `heavy_model_routing` | `FORBIDDEN` | Heavy/candidate lanes are explicit opt-in and cannot be automatic. |

## Stricter persona overrides

- `failure_reviewer` may not edit files; it is diagnostic only.
- `invariant_auditor` may not edit files or switch runtimes.
- `diff_summarizer` may not mutate the change it reviews.
- `lane_router` may not switch runtimes and may not route heavy/candidate/sidecar lanes automatically.

## Promotion rule

A capability can move from `UNSUPPORTED` or `OPERATOR_ONLY` only after a dedicated PR adds a deterministic smoke test, explicit docs, and a validation command. No persona promotion should happen silently.
