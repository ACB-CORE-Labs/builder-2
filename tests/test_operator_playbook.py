import re
import pathlib
import tomllib

def test_script_registration_drift():
    """Verify that all documented command families exist in pyproject.toml."""
    pyproject_path = pathlib.Path("pyproject.toml")
    assert pyproject_path.exists(), "pyproject.toml must exist"
    
    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)
        
    scripts = config.get("project", {}).get("scripts", {})
    
    required_families = [
        "builder",
        "builder-targets",
        "builder-agent",
        "builder-verification",
        "builder-context",
        "builder-bundle",
        "builder-research",
        "builder-quality",
        "builder-notes",
        "builder-goose",
        "builder-deepagents",
        "builder-bridge",
        "builder-chain",
    ]
    
    for command in required_families:
        assert command in scripts, f"Command '{command}' must be registered in pyproject.toml"

def test_docs_alignment_drift():
    """Verify docs/OPERATOR_PLAYBOOK.md and docs/ROADMAP.md mention the same operating-loop commands."""
    playbook_path = pathlib.Path("docs/OPERATOR_PLAYBOOK.md")
    roadmap_path = pathlib.Path("docs/ROADMAP.md")
    
    assert playbook_path.exists(), "docs/OPERATOR_PLAYBOOK.md must exist"
    assert roadmap_path.exists(), "docs/ROADMAP.md must exist"
    
    with open(playbook_path, "r", encoding="utf-8") as f:
        playbook_content = f.read()
        
    with open(roadmap_path, "r", encoding="utf-8") as f:
        roadmap_content = f.read()
        
    # Command families to look for
    commands = [
        "builder-setup plan",
        "builder-setup validate-plan",
        "builder doctor",
        "builder-targets validate",
        "builder-agent validate",
        "builder-verification validate",
        "builder-context pack",
        "builder-verification artifact",
        "builder-bundle create",
        "builder-bundle validate",
        "builder-research plan",
        "builder-research validate",
        "builder-quality plan",
        "builder-quality validate",
        "builder-notes handoff",
        "builder-notes validate",
        "builder-goose manifest",
        "builder-goose validate",
        "builder-goose readonly-audit",
        "builder-goose validate-audit",
        "builder-goose inspect-readonly",
        "builder-goose validate-inspection",
        "builder-deepagents policy",
        "builder-deepagents validate",
        "builder-deepagents readiness",
        "builder-deepagents validate-readiness",
        "builder-bridge render",
        "builder-bridge validate-artifact",
    ]
    
    for cmd in commands:
        assert cmd in playbook_content, f"Command '{cmd}' must be documented in docs/OPERATOR_PLAYBOOK.md"
        assert cmd in roadmap_content, f"Command '{cmd}' must be documented in docs/ROADMAP.md"

def test_no_runtime_language_guard():
    """Assert that the playbook explicitly denies runtime behaviors and keeps future commands disabled."""
    playbook_path = pathlib.Path("docs/OPERATOR_PLAYBOOK.md")
    assert playbook_path.exists(), "docs/OPERATOR_PLAYBOOK.md must exist"
    
    with open(playbook_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    denial_phrases = [
        "shell execution",
        "source writes",
        "model execution",
        "goose runtime activation",
        "deepagents construction",
        "memory mutation",
        "commit/push automation",
        "core workbench coupling",
    ]
    
    content_lower = content.lower()
    for phrase in denial_phrases:
        assert phrase in content_lower, f"Playbook must explicitly deny '{phrase}'"
        
    # Check that future runtime commands are only in the future/disabled section
    future_commands = [
        "builder-goose start-readonly",
        "builder-run approved",
        "builder-apply approved",
        "git push",
    ]
    
    # Locate the future capabilities section
    future_section_match = re.search(r"## Future Runtime Capabilities", content)
    assert future_section_match is not None, "Playbook must have a section '## Future Runtime Capabilities'"
    
    future_section_index = future_section_match.start()
    before_future = content[:future_section_index]
    after_future = content[future_section_index:]
    
    for cmd in future_commands:
        assert cmd not in before_future, f"Future runtime command '{cmd}' must not appear before the Future Runtime Capabilities section"
        assert cmd in after_future, f"Future runtime command '{cmd}' must be listed in the Future Runtime Capabilities section"
        
    assert "not enabled" in after_future.lower(), "Future capabilities section must explicitly note they are 'not enabled'"
