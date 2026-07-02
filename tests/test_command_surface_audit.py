import tomllib
from pathlib import Path


def test_command_surface_audit_covers_all_scripts():
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    doc_path = project_root / "docs" / "COMMAND_SURFACE_AUDIT.md"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    builder_scripts = [name for name in scripts.keys() if name.startswith("builder")]

    doc_content = doc_path.read_text("utf-8")

    for script in builder_scripts:
        assert script in doc_content, f"Script '{script}' registered in pyproject.toml is missing from COMMAND_SURFACE_AUDIT.md"

def test_command_surface_audit_invariants():
    project_root = Path(__file__).parent.parent
    doc_path = project_root / "docs" / "COMMAND_SURFACE_AUDIT.md"
    doc_content = doc_path.read_text("utf-8")

    invariants = [
        "no shell execution is enabled",
        "no model execution is enabled",
        "no patch application is enabled",
        "no autonomous writes are enabled",
        "no Goose runtime activation is enabled",
        "no deepagents runtime is enabled",
        "builder-II is not CORE Workbench/UI",
        "CORE is only a target profile",
    ]

    for invariant in invariants:
        assert invariant in doc_content, f"Invariant '{invariant}' missing from COMMAND_SURFACE_AUDIT.md"
