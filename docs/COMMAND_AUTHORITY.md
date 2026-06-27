# Command Authority Tier Registry

## Why the Registry Exists
The Command Authority Tier Registry exists to prevent authority fog across the `builder-II` developer platform. As a generic platform exposing multiple console scripts and major subcommands, it is essential that every command has a single canonical classification describing its authority boundaries, runtime boundaries, write boundaries, human approval requirements, output behaviors, and promotion states. 

Crucially, **the presence of a command in this repository does not imply it is promoted, safe, runtime-enabled, or permitted to mutate source code.**

## The Tier Model
The platform categorizes all console scripts and subcommands into one of five explicit tiers:

* **Tier 0 — read-only inspection**:
  - *Allows*: Reading files, querying git history/hashes, inspecting workspace metadata, printing benchmarks.
  - *Forbids*: Running subprocesses (except read-only queries), generating non-read-only artifacts, modifying memory, or writing to source.
* **Tier 1 — artifact-only planning/validation**:
  - *Allows*: Static code analysis, template validations, writing structured/signed plans, preflight validation.
  - *Forbids*: Runtime execution of agents, model interaction, or mutating workspace source files.
* **Tier 2 — operator-managed setup/runtime helper**:
  - *Allows*: Triggered background server setups, model-chat loops (`builder ask`), execution of test suites (`builder verify`), and legacy/external scans.
  - *Forbids*: Autonomous agent execution or hidden runtime write authorities.
* **Tier 3 — HITL-gated execution candidate**:
  - *Allows*: Preparing execution requests, gathering candidate patches, and validating execution receipts.
  - *Forbids*: Autonomous execution without explicit human approval.
* **Tier 4 — forbidden/unpromoted automation**:
  - *Allows*: Spec rendering and dry-run validation.
  - *Forbids*: Active execution. These commands are unpromoted and disabled by default.

## Rules and Invariants
1. **Metadata is NOT Runtime Permission**: The registry defines declarative metadata boundaries. It does not dynamically grant runtime execution authorization.
2. **Promotion Requirements**: Upgrading a command to a more permissive state or tier requires:
   - Complete documentation.
   - Comprehensive test coverage.
   - A stable command surface.
   - Explicit failure mode definition.
   - A human approval boundary.
   - Predictable output artifacts.
   - A verified rollback path.
   - Verification suites.
3. **CORE TARGET ONLY**: CORE is a lineage context and target profile only, not the identity of the platform. Conflating the platform with the CORE workbench is strictly forbidden.
4. **Deephaven untouched**: Deephaven-related capabilities remain completely untouched and out of scope.

## Command Authority Registry Table

| Command Name | Tier | State | Runtime Boundary | Write Boundary | Approval Mode | Approval Boundary | Allows Shell | Allows Writes | Artifact Writes | State Writes |
|---|---|---|---|---|---|---|---|---|---|---|
| `builder` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Delegates to helper subcommands; root CLI does not execute direct agent/model loops. | No direct write authority at root CLI level. | `explicit_operator_invocation` | Operator must explicitly run command options from active terminal. | No | No | No | No |
| `builder-runtime` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Interacts with local server endpoints, background agents, and runtime indicators. | Writes session runtime lockfiles and state indicators locally. | `explicit_operator_invocation` | Operator must trigger control signals manually. | No | No | No | Yes |
| `builder-lanes` | Tier 1 — artifact-only planning/validation | `validation_only` | Evaluates passive rules and checklists; no subprocess execution. | No changes to workspace. | `none` | Passive check, no approval required. | No | No | No | No |
| `builder-tools` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Lists or verifies tool specs; can query tool registry metadata. | No changes to workspace. | `explicit_operator_invocation` | Operator runs spec auditing. | No | No | No | No |
| `builder-context` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Legacy context builder; delegates execution details to subcommands. | No direct write authority at root CLI level. | `explicit_operator_invocation` | Legacy context generator; operator must run command explicitly. | No | No | No | No |
| `builder-git-state` | Tier 1 — artifact-only planning/validation | `artifact_only` | Executes local git queries via read-only subprocess. | Writes declarative state file artifacts in workspace. | `none` | Passive git branch check. | No | No | Yes | No |
| `builder-targets` | Tier 0 — read-only inspection | `spec_only` | Retrieves target profile metadata; no execution. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-session` | Tier 1 — artifact-only planning/validation | `validation_only` | Delegates packaging and checks to subcommands. | No direct write authority at root CLI level. | `none` | Read-only checks or artifact-only packaging; no approval needed. | No | No | No | No |
| `builder-agent` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Resolves active agent profiles and manifests. | No changes to workspace. | `explicit_operator_invocation` | Operator triggers agent inventory check. | No | No | No | No |
| `builder-bridge` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Tests readiness of external deepagents integrations. | No changes to workspace. | `explicit_operator_invocation` | Operator checks network bridge connectivity. | No | No | No | No |
| `builder-bundle` | Tier 1 — artifact-only planning/validation | `artifact_only` | Validates bundle definitions or packages build artifacts. | Creates ZIP or tar bundles in designated build folder. | `none` | Artifact build task. | No | No | Yes | No |
| `builder-goose` | Tier 1 — artifact-only planning/validation | `validation_only` | Delegates validation and read-only audits to subcommands. | No direct write authority at root CLI level. | `none` | Validation and audit only. | No | No | No | No |
| `builder-records` | Tier 1 — artifact-only planning/validation | `artifact_only` | Decodes and validates cryptographically signed or structured approval logs. | Writes verified signature files. | `none` | None; read-only verification. | No | No | Yes | No |
| `builder-preflight` | Tier 1 — artifact-only planning/validation | `validation_only` | Runs local environment checks (Python version, CLI presence). | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-receipt` | Tier 1 — artifact-only planning/validation | `artifact_only` | Generates or reads execution receipts. | Writes receipt JSON files to output folders. | `none` | None. | No | No | Yes | No |
| `builder-chain` | Tier 1 — artifact-only planning/validation | `validation_only` | Traces artifact lineage chains. | Writes chain validation artifacts. | `none` | None. | No | No | Yes | No |
| `builder-handoff` | Tier 1 — artifact-only planning/validation | `artifact_only` | Aggregates verified evidence and creates handoff bundle metadata. | Writes handoff markdown files. | `none` | None. | No | No | Yes | No |
| `builder-intake` | Tier 1 — artifact-only planning/validation | `artifact_only` | Ingests inputs from outside workspace. | Writes configuration files in specific workspace location. | `none` | None. | No | No | Yes | No |
| `builder-index` | Tier 1 — artifact-only planning/validation | `artifact_only` | Tracks and indexes generated artifact files. | Updates local artifact index JSON ledger. | `none` | None. | No | No | Yes | No |
| `builder-promotion` | Tier 1 — artifact-only planning/validation | `validation_only` | Analyzes readiness for target promotion. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-promotion-decision` | Tier 1 — artifact-only planning/validation | `artifact_only` | Creates a signed promotion decision artifact. | Writes promotion decision JSON artifact. | `none` | None. | No | No | Yes | No |
| `builder-state-index` | Tier 1 — artifact-only planning/validation | `artifact_only` | Constructs system state summaries. | Writes state index JSON files. | `none` | None. | No | No | Yes | No |
| `builder-snapshot` | Tier 1 — artifact-only planning/validation | `artifact_only` | Records current directory snapshot hashes. | Writes workspace snapshot hash index. | `none` | None. | No | No | Yes | No |
| `builder-deepagents` | Tier 4 — forbidden/unpromoted automation | `forbidden_unpromoted` | Delegates deepagent specs rendering and validation to subcommands; active run is forbidden. | No direct write authority at root CLI level. | `forbidden_unpromoted` | Forbidden; no supported approval path. | No | No | No | No |
| `builder-notes` | Tier 1 — artifact-only planning/validation | `artifact_only` | Verifies or creates handoff notes artifacts. | Writes handoff notes markdown files. | `none` | None. | No | No | Yes | No |
| `builder-quality` | Tier 1 — artifact-only planning/validation | `validation_only` | Checks code linting or test coverage thresholds. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-research` | Tier 1 — artifact-only planning/validation | `artifact_only` | Builds read-only research plans. | Writes plan metadata files. | `none` | None. | No | No | Yes | No |
| `builder-performance` | Tier 0 — read-only inspection | `validation_only` | Measures CLI loading time and file sizes. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-readonly` | Tier 0 — read-only inspection | `read_only_runtime_candidate` | Inspects system files and configurations without execution. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-verification` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates verification profile schemas. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-hitl` | Tier 3 — HITL-gated execution candidate | `hitl_runtime_candidate` | Delegates execution request and receipt operations to subcommands. | No direct write authority at root CLI level. | `hitl_artifact_required` | Operator must sign hitl request and verify receipts. | No | No | No | No |
| `builder-orchestration` | Tier 1 — artifact-only planning/validation | `artifact_only` | Delegates plan setup and validation to subcommands. | No direct write authority at root CLI level. | `none` | None. | No | No | No | No |
| `builder-session prepare-package` | Tier 1 — artifact-only planning/validation | `artifact_only` | Prepares context packaging and checks files. | Writes prepared package files locally. | `none` | None. | No | No | Yes | No |
| `builder-session validate-prepare-package` | Tier 1 — artifact-only planning/validation | `validation_only` | Performs validations on the prepared package directory structure. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-session summarize-prepare-package` | Tier 1 — artifact-only planning/validation | `validation_only` | Analyzes prepared package and generates a passive summary. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-context pack` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Invokes legacy external scanner or git commands. | Writes context bundle files. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | Yes | No |
| `builder-context changed` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Queries git status or git diff via subprocess. | No changes to workspace. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | No | No |
| `builder-context artifact` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Processes codebase scanning, potentially using external tools like repomix. | Creates context artifact files. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | Yes | No |
| `builder start` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Starts background runtime processes and servers. | Creates process locks and configuration settings. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | No | Yes |
| `builder ask` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Queries model provider or MLX local runtime using user input. | Writes conversation history files locally. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | Yes | No |
| `builder verify` | Tier 2 — operator-managed setup/runtime helper | `operator_managed` | Invokes local pytest/runner test suites via subprocess. | No source code changes; generates test result files. | `explicit_operator_invocation` | Explicit operator invocation only; no artifact approval chain. | No | No | No | No |
| `builder-goose manifest` | Tier 1 — artifact-only planning/validation | `validation_only` | Inspects Goose configuration manifest templates. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose validate` | Tier 1 — artifact-only planning/validation | `validation_only` | Performs validations on active Goose session configs. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose readonly-audit` | Tier 1 — artifact-only planning/validation | `validation_only` | Ensures a target Goose session uses read-only tools only. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose validate-audit` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates the output of a Goose audit run. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose inspect-readonly` | Tier 1 — artifact-only planning/validation | `validation_only` | Performs read-only inspection validation on explicitly requested paths. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose validate-inspection` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates inspection config details. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-goose start-readonly` | Tier 4 — forbidden/unpromoted automation | `forbidden_unpromoted` | Attempts to start a Goose session. Disabled and unpromoted by default. | No changes to workspace. | `forbidden_unpromoted` | Forbidden; no supported approval path. | No | No | No | No |
| `builder-deepagents render` | Tier 1 — artifact-only planning/validation | `artifact_only` | Renders deepagent specs statically. | Writes spec manifest files. | `none` | None. | No | No | Yes | No |
| `builder-deepagents validate` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates deepagents spec metadata. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-deepagents delegate` | Tier 4 — forbidden/unpromoted automation | `forbidden_unpromoted` | Attempts to execute autonomous models. Forbidden. | No changes to workspace. | `forbidden_unpromoted` | Forbidden; no supported approval path. | No | No | No | No |
| `builder-hitl request` | Tier 3 — HITL-gated execution candidate | `hitl_runtime_candidate` | Collects and validates HITL request details. | Writes HITL request JSON artifact. | `hitl_artifact_required` | Requires explicit operator approval signature. | No | No | Yes | No |
| `builder-hitl receipt` | Tier 3 — HITL-gated execution candidate | `hitl_runtime_candidate` | Records execution completion or failure receipt metadata. | Writes HITL receipt JSON artifact. | `hitl_artifact_required` | Operator must sign hitl request and verify receipts. | No | No | Yes | No |
| `builder-hitl validate` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates request and receipt artifact files against schema. | No changes to workspace. | `none` | None. | No | No | No | No |
| `builder-orchestration plan` | Tier 1 — artifact-only planning/validation | `artifact_only` | Creates plan structure statically without launching active agents. | Writes plan JSON file. | `none` | None. | No | No | Yes | No |
| `builder-orchestration validate` | Tier 1 — artifact-only planning/validation | `validation_only` | Validates the schema and steps of a plan artifact. | No changes to workspace. | `none` | None. | No | No | No | No |
