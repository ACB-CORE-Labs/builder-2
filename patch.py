import re

lines = [
    '"builder-inspect hitl status",',
    '"builder-inspect hitl chain",',
    '"builder-inspect hitl pending",',
    '"builder-inspect hitl approval",',
    '"builder-inspect hitl evidence",',
    '"builder-inspect hitl execution",',
    '"builder-inspect hitl promote",',
    '"builder-inspect hitl replay",',
    '"builder-inspect profile status",',
    '"builder-inspect profile lifecycle",',
    '"builder-inspect profile validate",',
    '"builder-inspect profile render-plan",',
    '"builder-inspect profile dry-run",',
    '"builder-inspect profile resolve",',
    '"builder-inspect profile history",',
    '"builder-inspect model routing show",',
    '"builder-inspect model routing simulate",',
    '"builder-inspect model routing candidates",',
    '"builder-inspect model routing policy",',
    '"builder-inspect model routing execution-policy",',
    '"builder-inspect model routing validate",',
    '"builder-inspect model registry show",',
    '"builder-inspect model registry diff",',
    '"builder-inspect promote status",',
    '"builder-inspect promote readiness",',
    '"builder-inspect promote artifact",',
    '"builder-inspect promote decision",',
    '"builder-inspect promote compatibility",',
    '"builder-inspect promote history",',
    '"builder-inspect promote gates",',
    '"builder-inspect postflight status",',
    '"builder-inspect postflight record",',
    '"builder-inspect postflight verify",',
    '"builder-inspect postflight governance",',
    '"builder-inspect postflight actions",',
    '"builder-inspect postflight refs",',
    '"builder-inspect postflight validate",',
    '"builder-inspect goose status",',
    '"builder-inspect goose manifest",',
    '"builder-inspect goose links",',
    '"builder-inspect goose actions",',
    '"builder-inspect goose governance",',
    '"builder-inspect goose validate",',
    '"builder-inspect goose approval",',
    '"builder-inspect code-vault status",',
    '"builder-inspect code-vault frame",',
    '"builder-inspect code-vault determinism",',
    '"builder-inspect code-vault recall",',
    '"builder-inspect code-vault lint",',
    '"builder-inspect code-vault context",',
    '"builder-inspect code-vault governance",',
    '"builder-inspect code-vault validate",',
]

with open("builder_ii/governance/authority/authority_registry.py", "r") as f:
    content = f.read()

target = '    "builder-code-vault frame/recall",\n'
new_content = content.replace(target, target + '    ' + '\n    '.join(lines) + '\n')

with open("builder_ii/governance/authority/authority_registry.py", "w") as f:
    f.write(new_content)
