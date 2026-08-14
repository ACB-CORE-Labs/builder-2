# Passive profile-pack example

Generate a profile-pack lifecycle in an isolated artifact directory:

```bash
mkdir -p .builder/profile-pack-example

builder-profile-pack scaffold \
  --pack-id builder-passive-profile-pack \
  --target builder \
  --task "compose passive capability-factory substrate" \
  --output .builder/profile-pack-example/manifest.json

builder-profile-pack render \
  .builder/profile-pack-example/manifest.json \
  --output .builder/profile-pack-example/render-plan.json

builder-profile-pack dry-run \
  .builder/profile-pack-example/manifest.json \
  --render-plan .builder/profile-pack-example/render-plan.json \
  --output .builder/profile-pack-example/dry-run.json

builder-profile-pack validate \
  .builder/profile-pack-example/manifest.json \
  --output .builder/profile-pack-example/validation-report.json
```

The generated files are passive artifacts. They do not start Goose, construct deepagents, call models, connect to MCP, call tools, execute shell commands, run verification commands, write target source, approve HITL gates, or promote capabilities.
