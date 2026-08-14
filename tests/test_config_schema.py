from builder_ii.core.config_schema import (
    CONFIG_SCHEMA_VERSION,
    create_config_schema_artifact,
    legacy_alias_map,
    validate_config_schema_artifact,
)


def test_config_schema_version_and_required_fields() -> None:
    artifact = create_config_schema_artifact()

    assert artifact["kind"] == "builder_ii.config_schema"
    assert artifact["schema_version"] == CONFIG_SCHEMA_VERSION
    assert not validate_config_schema_artifact(artifact)

    fields = artifact["fields"]
    for required in (
        "platform_artifact_root",
        "default_target_id",
        "target_repo",
        "active_target_profile",
        "active_agent_profile",
        "active_verification_profile",
        "model_backend",
        "model_alias",
        "goose_config_path",
        "goose_recipe_path",
        "goose_skills_source_path",
        "goose_skills_destination_policy",
        "deepagents_mode",
        "runtime_mode",
    ):
        assert required in fields


def test_schema_is_generic_first_with_legacy_alias_metadata() -> None:
    artifact = create_config_schema_artifact()

    assert artifact["fields"]["target_repo"]["primary_env"] == "BUILDER_TARGET_REPO"
    assert artifact["fields"]["model_backend"]["primary_env"] == "BUILDER_MODEL_BACKEND"
    assert artifact["fields"]["model_alias"]["primary_env"] == "BUILDER_MODEL_ALIAS"

    aliases = legacy_alias_map()
    assert aliases["CORE_REPO_PATH"]["alias_for"] == "BUILDER_TARGET_REPO"
    assert aliases["CORE_AGENT_BACKEND"]["alias_for"] == "BUILDER_MODEL_BACKEND"
    assert aliases["CORE_AGENT_MODEL_ALIAS"]["alias_for"] == "BUILDER_MODEL_ALIAS"
    assert aliases["CORE_REPO_PATH"]["compatibility_state"] == "backwards_compatible_alias_only"


def test_schema_disables_runtime_authority() -> None:
    artifact = create_config_schema_artifact()
    governance = artifact["governance"]

    assert governance["artifact_is_authority"] is False
    assert governance["runtime_execution"] == "disabled"
    assert governance["model_execution"] == "disabled"
    assert governance["shell_execution"] == "disabled"
    assert governance["source_writes"] == "disabled"
    assert governance["goose_runtime"] == "disabled"
    assert governance["deepagents_runtime"] == "disabled"
    assert governance["mcp_tool_invocation"] == "disabled"
    assert governance["patch_authority"] == "disabled"
