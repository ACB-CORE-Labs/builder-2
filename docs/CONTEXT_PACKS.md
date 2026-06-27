# Bounded Context Packs

The context pack capability extracts a bounded, high-signal subset of repository entries from a repository map. It delivers structured intelligence tailored for human review or agent session initialization without executing tasks or mutating files.

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench, not CORE UI/UX, and not a second CORE runtime. CORE is only a target profile.

## Artifact Specification

- **Kind**: `builder_ii.context_pack`
- **Schema Version**: `1`

The context pack artifact captures:
- **`target_name`**: Target profile (`generic`, `builder`, or `core`).
- **`task`**: Optional description of the target task or workflow.
- **`source`**: Metadata referencing the underlying repository map (`repo_path`, `file_count`, `summary_counts`).
- **`selected_files`**: Bounded list of file entries selected from the map.
- **`omitted_file_count`**: Count of remaining repository files not included in the pack.
- **`operator_guidance`**: Instructions advising manual review and out-of-band verification.
- **`verification_boundary`**: Explicit statements preventing the artifact from being treated as proof or evidence.
- **`governance`**: Explicit flags confirming all execution and write capabilities remain disabled.

## Selection Ordering & Bounding

To maintain stability and ensure foundational architectural context is presented first, files from the repository map are selected in a strict priority order:
1. **`docs`**: High-level READMEs and documentation.
2. **`config`**: Project specifications, build manifests, and tool settings.
3. **`test`**: Existing test suites and regression specifications.
4. **`source`**: Core implementation code.
5. **`artifact` & `unknown`**: Auxiliary files.

Selection is bounded by `max_entries` (default 100 entries) to prevent context flooding. Any additional files are counted in `omitted_file_count`.

## Operator Guidance & Verification Boundary

Every context pack embeds explicit boundaries to prevent premature trust or unverified claims:
- **Read-Only Context**: The context pack provides passive structural orientation.
- **No Proof of Correctness**: Including a file or test suite in a context pack does not imply that the code is bug-free or that tests pass.
- **No Evidence Conversion**: Planned verification steps must be run and evidenced out-of-band by the operator.

## CLI Command

You can generate a context pack independently from a repository map via the CLI:

```bash
builder-session context-pack generic \
  --repo-map .builder/artifacts/repo-map.json \
  --output .builder/artifacts/context-pack.json \
  --task "Implement new capability"
```

## Governance & Runtime Boundary

Like all governed preparation artifacts, the context pack operates strictly within platform boundaries:
- **No shell execution**: Selection operates entirely over in-memory Python dictionaries.
- **No subprocess calls**: No external command tools or bundling utilities are invoked.
- **No target-repo writes**: The target repository is never modified.
- **No model execution**: Selection heuristics are deterministic.
- **No Goose / deepagents activation**: No agents are executed or delegated to.
