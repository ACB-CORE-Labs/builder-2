# **STRATUM TUI/UX Overhaul: Mastery Resonance Console**

# **Part 1: Deep-Dive Audit & Comparative Analysis**

An audit of the active codebase in [builder-II Repository](https://core-gitquarters.acbcontent.org/core-labs/builder-II) highlights several structural, security, and design opportunities when contrasted against the proposed overhaul.

## **1\. CodeVault Traceability vs. The Digest Invariant**

* **Overhaul Proposal:** A vertical live chain view in the Spine with density glyphs, combined with a timeline summary showing chain validity.  
* **Codebase Reality:** In `builder_ii/tui/app.py`, the constant `CHAIN_DIGEST_ABSENT = "—"` enforces a strict truth boundary: the TUI does not verify or synthesize digests on its own because `verify_artifact_chain` exposes no ambient digest. This prevents the display of a fabricated digest where none has been evaluated.  
* **Alignment Plan:** Any vertical "Traceability Field" or "Chain Resonance Timeline" must bind to actual CodeVault ledger files or receipts (such as `gate_battery_receipt.py` or `verification_execution_ledger.py`). It must visually denote "unverified/unevaluated" states as a clean absence (using your semantic void palette) rather than rendering placeholder or simulated hashes.

## **2\. Deepagents Forge vs. Execution Boundaries**

* **Overhaul Proposal:** A draggable teaming matrix node canvas with customization sliders and preview simulations.  
* **Codebase Reality:** In `builder_ii/tui/app.py` under `action_toggle_agents`, STRATUM explicitly refuses to write `orchestration_assignment.json` or dispatch agents directly:self.notify("STRATUM cannot dispatch subagents or write assignment artifacts; run \`builder-deepagents assign-subagent\` in your terminal.")  
    
  Deepagent profiles are read-only-loaded in `builder_ii/routing/agent_profiles.py` and displayed using flat text in `builder_ii/tui/widgets/stratum.py`.  
    
* **Alignment Plan:** A "Deepagents Forge Canvas" is structurally sound as a visual design wizard, but it must remain a pure configurator that outputs the exact CLI command to run (e.g., in the Command Composer / CLI Passthrough) or previews YAML files located in `profiles/deepagents/`. It must never write configuration files directly, preserving the rule that the TUI does not originate authority.

## **3\. Model Routing Canvas vs. Registry States**

* **Overhaul Proposal:** Interactive node graphs with cost/context heatmaps and routed test previews.  
* **Codebase Reality:** `StratumMode.MODEL_MATRIX` reads directly from `builder_ii/routing/model_client_registry.py` to display active models, cost categories, context limits, and provider statuses.  
* **Alignment Plan:** High-density, horizontal matrix layouts utilizing ASCII borders, box-drawing characters, and semantic colors (`stratum-active` for routed paths, `stratum-fail` for disabled models) can achieve a routing canvas. Test queries must be routed strictly through the real `model_client_registry` using display-only channels.

## **4\. Dynamic Orchestrator vs. Governed Goose Sessions**

* **Overhaul Proposal:** Horizontal lane diagrams with active recipes, modular skill blocks, and session projections.  
* **Codebase Reality:** Goose sessions are heavily restricted. `app.py` suspends the TUI and hands the terminal to the governed command `builder-goose start-readonly` using a subprocess call. This ensures that arbitrary file editing and tool execution are never initiated or laundered by the TUI itself.  
* **Alignment Plan:** The workflow lane diagram should visualize the stages of active recipes (.yaml configurations in `recipes/` and `recipes/subrecipes/`) and obligations directly from `workflow_records.py`. It should display a projection of the session, but the final activation step must suspend the TUI and execute the governed CLI launcher to ensure clean boundaries.

## **5\. HITL Gates & Ceremonial Commands**

* **Overhaul Proposal:** Full-screen overlays with visual effects, digest glyphs, and a "Run Governed Command" button.  
* **Codebase Reality:** The center panel handles `HITL_GATE` mode by rendering the command, tier, authority requirements, and artifact previews. The `approve` and `reject` actions warn the operator that the TUI cannot harvest confirmation and instruct them to run the CLI helper.  
* **Alignment Plan:** A ceremonial gate interface can show constraints from the `ThirdDoorGate` widget (e.g., verifying tests, documentation, rollback paths). The "Run Governed Command" action should use the `CLIPassthroughScreen` to pre-fill the exact command (such as `builder-hitl approve-patch`), forcing the operator to execute it in the terminal context where authority evaluation actually resides.

# **Part 2: Pillars of the Masterpiece Plan**

## **Pillar 1: High-Density Traceability Field (Spine Overhaul)**

* **Visual Metaphor:** Replace the flat text list in `builder_ii/tui/widgets/spine.py` with a live structural chain of block glyphs (`█` for verified, `░` for pending, `▒` for gate-open).  
* **Behavior:** Up/down movement triggers a detailed side-pane expansion in the Center Panel showing CodeVault metadata (cryptographic hashes, receipt paths, reconstruction evidence) fetched from `builder_ii/code_vault_provenance.py` without fabricating missing data.

## **Pillar 2: Deepagents Matrix & Forge Workspace**

* **Visual Metaphor:** Transform the flat agent profile listing into a horizontal node map using unicode line-drawing characters (`├─`, `─┬─`, `─┤`).  
* **Behavior:** Clicking an agent profile highlights its allowed tools and displays its target configuration (e.g., `profiles/deepagents/governed_repo_cartographer.yaml`). It evaluates the team structure against `builder_ii/adapters/deepagents/deepagents_bridge_readiness.py` to show a "Bridge Readiness Score."

## **Pillar 3: Live Model Routing Grid**

* **Visual Metaphor:** A grid matrix showing backends (Ollama, MLX, Frontier) as column headers and model classes as rows.  
* **Behavior:** Displays real-time status of local runtimes. Hovering over a route highlights the current fallback path defined by `builder_ii/routing/model_routing_policy.py`.

## **Pillar 4: Orchestrator Lane & Skill Projection**

* **Visual Metaphor:** A split view showing lanes for active recipes (e.g., `core-coding.yaml`) and skill invocations from `.agents/skills/`.  
* **Behavior:** Displays historical execution paths and postflight checklist states. Integrates the `ThirdDoorGate` widget directly to display which of the 8 canonical constraints (documentation, rollback path, verification path, etc.) are satisfied.

## **Pillar 5: Governed CLI Passthrough & Gate Ceremonies**

* **Visual Metaphor:** A full-screen terminal shroud overlay with high-contrast borders (`$stratum-warn` for HITL, `$stratum-fail` for blockers).  
* **Behavior:** Highlights the cryptographic digest to be signed. Pressing `A` (Approve) opens the CLI wrapper pre-populated with the command, keeping the operator in control of the actual transaction.

# **Part 3: stratum.tcss & tui\_theme.py Specification**

These palette variables map directly to the existing Textual variable system used in `StratumApp._apply_theme()` within `builder_ii/tui/app.py`.

## **Refined `builder_ii/core/tui_theme.py` (Extended Stratum Void Scheme)**

| Key | Hex Value | Semantic Role |
| :---- | :---- | :---- |
| pass | \#3fb950 | Emerald (verified determinism) |
| warn | \#ffa657 | Amber (gate/needs attention) |
| fail | \#f85149 | Crimson (broken chain / block) |
| hint | \#6e7681 | Slate Gray (de-emphasized context) |
| active | \#79c0ff | Ice Blue (resonance highlight) |
| dim | \#21262d | Muted Gray (grid lines, rules) |
| bold | \#c9d1d9 | Frost White (primary readable text) |
| accent | \#d2a8ff | Amethyst (deepagents / forge) |
| \_bg | \#0a0e14 | Void background |
| \_panel | \#0d1117 | Dark surface container |

## **Refined `builder_ii/tui/stratum.tcss` Excerpt**

s  
Screen {  
background: $stratum-bg;  
color: $stratum-bold;  
}

\#stratum-header {  
background: $stratum-panel;  
border-bottom: solid $stratum-border;  
color: $stratum-hint;  
}

.stratum-pass { color: $stratum-pass; }  
.stratum-warn { color: $stratum-warn; }  
.stratum-fail { color: $stratum-fail; }  
.stratum-active { color: $stratum-active; }  
.stratum-accent { color: $stratum-accent; }

\#spine-container {  
background: $stratum-panel;  
border-right: solid $stratum-border;  
}

.spine-item.-selected {  
background: $stratum-selected;  
color: $stratum-selected-text;  
text-style: bold;  
}

\#stratum-chain-bar {  
background: $stratum-panel;  
border-top: solid $stratum-border;  
color: $stratum-session;  
}

\#\# Part 4: Implementation Sequence & Dependency Ordering

To execute this architectural overhaul autonomously and reliably, development is segmented by structural dependencies rather than temporal constraints.

\#\#\# Milestone 1: Theme and Base Foundation

\*   Refine the registry palette in \`builder\_ii/tui\_theme.py\`.

\*   Adapt the Textual configuration variables inside \`builder\_ii/tui/stratum.tcss\` to use variables for borders, panels, and text hierarchies.

\*   Clean up global elements like header/footer panels to utilize the Cosmic Void scheme.

\#\#\# Milestone 2: Traceability and Routing Panels

\*   Overhaul \`builder\_ii/tui/widgets/spine.py\` to use vertical block glyphs.

\*   Wire Spine selection directly to \`builder\_ii/code\_vault\_provenance.py\` for rich metadata retrieval.

\*   Build active-route indicators for \`StratumMode.MODEL\_MATRIX\`.

\#\#\# Milestone 3: Deepagent Workspaces & Workflow Lane Diagrams

\*   Refine the layout of \`StratumMode.AGENT\_PROFILES\` to render agent rosters as dependency nodes.

\*   Structure active-lane visualizations in \`StratumMode.WORKFLOW\` to mirror the progress of active recipes and obligations dynamically.

\#\#\# Milestone 4: Gate Ceremony Integration and Verification

\*   Integrate the \`ThirdDoorGate\` visual constraint checks in the \`HITL\_GATE\` panel of \`builder\_ii/tui/widgets/stratum.py\`.

\*   Ensure that TUI approve/reject controls pre-populate the governed CLI environment to respect the authority boundary.

\*   Validate the complete visual state with the existing test suite in \`tests/test\_stratum\_tui.py\`.  
