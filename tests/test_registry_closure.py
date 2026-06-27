import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.performance_measurements import PERFORMANCE_MEASUREMENT_KIND, create_performance_measurement_record
from builder_ii.readonly_inspection_promotion import READONLY_INSPECTION_PROMOTION_SPEC_KIND, create_readonly_inspection_promotion_spec
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, create_research_adapter_artifact
from builder_ii.research_plans import RESEARCH_PLAN_KIND, create_research_plan_artifact
from builder_ii.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND


CLOSURE_KINDS = {
    "builder_ii.target_profile",
    "builder_ii.verification_profile",
    "builder_ii.context_pack_record",
    "builder_ii.agent_profile_record",
    "builder_ii.git_state_record",
    RESEARCH_PLAN_KIND,
    RESEARCH_ADAPTER_KIND,
    PERFORMANCE_MEASUREMENT_KIND,
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    READONLY_INSPECTION_REPORT_KIND,
}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan() -> dict[str, Any]:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="plan registry closure",
        topic="registry closure",
    )


def _adapter(plan: dict[str, Any]) -> dict[str, Any]:
    return create_research_adapter_artifact(
        target="builder",
        topic="registry closure",
        research_question="Which registries must stay aligned?",
        plan_path="research-plan.json",
        plan_sha256=_digest(plan),
    )


def _measurement() -> dict[str, Any]:
    return create_performance_measurement_record(
        target="builder",
        candidate_name="registry_closure",
        metric_name="closure_artifact_count",
        metric_value=4,
        unit="artifacts",
        method="operator supplied test fixture",
        source_ref="tests/test_registry_closure.py",
    )


def test_recent_artifact_kinds_are_registered_in_both_registries() -> None:
    for kind in CLOSURE_KINDS:
        assert kind in INDEX_VALIDATORS
        assert kind in CHAIN_VALIDATORS


def test_recent_artifact_fixtures_validate_through_both_registries() -> None:
    plan = _plan()
    records = [plan, _adapter(plan), _measurement(), create_readonly_inspection_promotion_spec(target="builder")]

    for record in records:
        kind = record["kind"]
        assert INDEX_VALIDATORS[kind](record) == []
        assert CHAIN_VALIDATORS[kind](record) == []


def test_artifact_index_recognizes_recent_artifacts(tmp_path: Path) -> None:
    plan = _plan()
    for filename, artifact in {
        "research-plan.json": plan,
        "research-adapter.json": _adapter(plan),
        "performance.json": _measurement(),
        "readonly-spec.json": create_readonly_inspection_promotion_spec(target="builder"),
    }.items():
        _write(tmp_path / filename, artifact)

    index = create_artifact_index_record(tmp_path)

    assert index["counts"] == {"total": 4, "known": 4, "unknown": 0, "valid": 4, "invalid": 0}
    assert validate_artifact_index_record(index) == []


def test_research_adapter_link_resolves_to_plan(tmp_path: Path) -> None:
    plan = _plan()
    adapter = _adapter(plan)
    plan_path = tmp_path / "research-plan.json"
    adapter_path = tmp_path / "research-adapter.json"
    _write(plan_path, plan)
    _write(adapter_path, adapter)

    report = verify_artifact_chain([adapter_path])

    assert report["valid"] is True
    assert report["counts"]["links"] == 1
    assert report["counts"]["resolved_links"] == 1
    assert report["links"][0]["field"] == "research_plan"
    assert report["links"][0]["target_kind_expected"] == RESEARCH_PLAN_KIND
