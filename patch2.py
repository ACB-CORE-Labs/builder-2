with open("builder_ii/governance/authority/authority_registry.py", "r") as f:
    content = f.read()

# Fix delegating groups
content = content.replace('"builder-inspect",', '"builder inspect",')

# Fix command record
content = content.replace('name="builder-inspect"', 'name="builder inspect"')

# Fix extra commands
content = content.replace('"builder-inspect hitl', '"builder inspect hitl')
content = content.replace('"builder-inspect profile', '"builder inspect profile')
content = content.replace('"builder-inspect model', '"builder inspect model')
content = content.replace('"builder-inspect promote', '"builder inspect promote')
content = content.replace('"builder-inspect postflight', '"builder inspect postflight')
content = content.replace('"builder-inspect goose', '"builder inspect goose')
content = content.replace('"builder-inspect code-vault', '"builder inspect code-vault')

with open("builder_ii/governance/authority/authority_registry.py", "w") as f:
    f.write(content)

with open("tests/test_command_authority.py", "r") as f:
    tcontent = f.read()

tcontent = tcontent.replace('"builder-inspect",  # Group wrapper, delegates to subcommands', '"builder inspect",  # Group wrapper, delegates to subcommands')

with open("tests/test_command_authority.py", "w") as f:
    f.write(tcontent)

