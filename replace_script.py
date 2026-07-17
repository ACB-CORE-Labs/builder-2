import re

with open("tests/test_convention_kernel_platform_spine.py", "r") as f:
    content = f.read()

content = re.sub(
    r"def test_prepare_platform_spine_rejects_unmarked_tier2_command\(tmp_path, monkeypatch\):.*?kernel\.prepare_platform_spine\([\s\S]*?repo_path=str\(repo\),\n        \)",
    r'''@patch("builder_ii.convention_kernel.create_session_workflow_plan")
def test_prepare_platform_spine_rejects_unmarked_tier2_command(mock_create, tmp_path):
    repo = _make_repo(tmp_path)
    settings = load_settings(project_root=ROOT)
    kernel = ConventionKernel()

    # Mock create_session_workflow_plan to inject a Tier 2 command
    from builder_ii.session_workflow import create_session_workflow_plan as orig_create_session

    def unmarked_tier2_session(*args, **kwargs):
        res = orig_create_session(*args, **kwargs)
        res["planned_commands"].append("builder-unknown-tier2 --target builder")
        return res

    mock_create.side_effect = unmarked_tier2_session

    with pytest.raises(ValueError, match="unregistered"):
        kernel.prepare_platform_spine(
            settings,
            "builder",
            repo_path=str(repo),
        )''',
    content,
    flags=re.DOTALL
)

with open("tests/test_convention_kernel_platform_spine.py", "w") as f:
    f.write(content)
