# Research planning artifacts

Research planning artifacts are governed JSON plans for bounded research work. They are not research runtimes.

They can use `AssetOverflow/open_deep_research` as a reference target or design inspiration, but this surface does not import LangGraph, run MCP tools, collect sources, run web search, call models, or execute shell commands.

## Commands

```bash
builder-research profiles
builder-research show research_planner
builder-research validate-profiles

builder-research plan --target generic --profile research_planner --task "map open_deep_research architecture"
builder-research plan --target generic --profile research_planner --task "map open_deep_research architecture" --source-hint "repository docs" --output .builder/artifacts/research-plan.json
builder-research validate .builder/artifacts/research-plan.json
```

Profiles:

```text
research_planner
source_mapper
evidence_synthesizer
report_reviewer
```

## Artifact contents

A research plan artifact includes:

- `kind: builder_ii.research_plan`
- `schema_version: 1`
- selected target
- selected research profile
- task
- optional topic
- source hints
- source strategy
- evidence requirements
- report contract
- known unknowns
- failure mode
- governance boundary

## Governance boundary

Research planning artifacts do not:

- collect sources
- run web search
- run MCP tools
- import or execute LangGraph graphs
- call models
- construct agents
- execute shell commands
- edit source files
- commit or push
- authorize future runtime actions
- couple builder-II to CORE Workbench/UI

The only write performed by `builder-research plan --output PATH` is the explicit output path.

## Validation

`builder-research validate PATH` validates the research plan schema and disabled-action invariants.

Validation checks:

- plan kind and schema version
- valid target
- known profile name
- required task
- non-empty source strategy, evidence requirements, report contract, and known unknowns
- `open_deep_research_relation: REFERENCE_ONLY`
- disabled runtime, model, search, MCP, source collection, and shell execution fields

A valid research plan is evidence for review. It is not permission to collect sources or execute tools.

## Relationship to the operating loop

```bash
builder-research plan --target generic --profile source_mapper --task "map open_deep_research architecture" --output .builder/artifacts/research-plan.json
builder-research validate .builder/artifacts/research-plan.json
builder-quality plan --target builder --profile builder_full --task "review research plan follow-up" --output .builder/artifacts/quality-gate.json
builder-notes handoff --target builder --agent handoff_scribe --task "research plan follow-up" --summary "Research planning artifact created." --output .builder/artifacts/handoff.json
```

Future runtime modes may consume research plans, but the plan itself never grants execution authority.
