import hashlib
import json as json_lib

from builder_ii.research_adapters import create_research_adapter_artifact, validate_research_adapter_artifact
from builder_ii.research_plans import create_research_plan_artifact, dumps_research_plan_artifact


def _digest(value: dict) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _plan() -> dict:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="plan source review",
        topic="adapter test",
    )


def test_create_research_adapter_artifact_shape() -> None:
    plan = _plan()
    artifact = create_research_adapter_artifact(
        target="builder",
        topic="adapter test",
        research_question="What sources would need review?",
        plan_path="missing-plan.json",
        plan_sha256=_digest(plan),
    )

    assert artifact["kind"] == "builder_ii.research_adapter"
    assert artifact["schema_version"] == 1
    assert artifact["target"] == "builder"
    assert artifact["adapter_name"] == "governed_research_projection"
    assert artifact["research_plan"]["path"] == "missing-plan.json"
    assert artifact["adapter_relation"] == "PROJECTION_ONLY"
    assert artifact["handoff_state"] == "NOT_INVOKED"
    assert artifact["performed_actions"] == []
    assert artifact["governance"]["runtime_execution"] == "DISABLED"
    assert artifact["governance"]["search_execution"] == "DISABLED"
    assert artifact["governance"]["source_collection"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_research_adapter_artifact(artifact) == []


def test_validate_research_adapter_rejects_authority_changes() -> None:
    plan = _plan()
    artifact = create_research_adapter_artifact(
        target="builder",
        topic="adapter test",
        research_question="What sources would need review?",
        plan_path="missing-plan.json",
        plan_sha256=_digest(plan),
    )
    artifact["adapter_relation"] = "OTHER"
    artifact["handoff_state"] = "INVOKED"
    artifact["performed_actions"] = ["invoke"]
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["model_execution"] = "ENABLED"
    artifact["governance"]["search_execution"] = "ENABLED"
    artifact["governance"]["source_collection"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True
    artifact["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_research_adapter_artifact(artifact)

    assert "adapter_relation must be PROJECTION_ONLY" in errors
    assert "handoff_state must be NOT_INVOKED" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.model_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.search_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_collection must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_research_plan_digest_fixture_is_stable_shape() -> None:
    plan_json = json_lib.loads(dumps_research_plan_artifact(_plan()))
    assert plan_json["kind"] == "builder_ii.research_plan"
    assert _digest(plan_json)
