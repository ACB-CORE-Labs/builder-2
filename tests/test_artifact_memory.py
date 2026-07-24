import json as json_lib
from pathlib import Path

from builder_ii.core.artifact_chain_verification import (
    VALIDATORS as CHAIN_VALIDATORS,
)
from builder_ii.core.artifact_chain_verification import (
    extract_references,
    verify_artifact_chain,
)
from builder_ii.core.artifact_memory import (
    MEMORY_ATOM_KIND,
    MEMORY_INDEX_KIND,
    MEMORY_RECONSTRUCTION_KIND,
    MEMORY_SEARCH_RESULT_KIND,
    create_memory_atom,
    create_memory_index,
    create_memory_index_entry,
    create_memory_reconstruction,
    create_memory_ref,
    create_memory_search_result,
    validate_memory_atom,
    validate_memory_index,
    validate_memory_reconstruction,
    validate_memory_search_result,
    write_memory_atom,
    write_memory_index,
    write_memory_reconstruction,
    write_memory_search_result,
)
from builder_ii.core.handoff_notes import HANDOFF_NOTE_KIND, create_handoff_note
from builder_ii.core.research_plans import RESEARCH_PLAN_KIND, create_research_plan_artifact
from builder_ii.governance.ledger.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.governance.ledger.workflow_records import canonical_digest

TIMESTAMP = "2026-07-01T18:00:00Z"


def _research_plan() -> dict:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="map artifact memory surfaces",
        topic="artifact memory",
        source_hint=("docs",),
    )


def _plan_ref(path: str = "research-plan.json") -> dict:
    plan = _research_plan()
    return create_memory_ref(
        kind=RESEARCH_PLAN_KIND,
        path=path,
        sha256=canonical_digest(plan),
        role="source_artifact",
        name=Path(path).name,
    )


def _make_atom(
    *,
    atom_id: str,
    path: str,
    summary_text: str,
    tags: tuple[str, ...],
    claim_boundary: str = "proposal_only",
    atom_state: str = "ACTIVE",
    stale_reason: str = "",
    superseded_by_ref: dict | None = None,
) -> dict:
    return create_memory_atom(
        artifact_ref=_plan_ref(path),
        target_profile="builder",
        task="map artifact memory surfaces",
        created_at_utc=TIMESTAMP,
        claim_boundary=claim_boundary,
        review_state="validated"
        if atom_state == "ACTIVE"
        else "superseded"
        if atom_state == "SUPERSEDED"
        else "operator_reviewed",
        atom_state=atom_state,
        source_truth_state="SOURCE_BOUND",
        summary_text=summary_text,
        summary_origin="artifact_projection",
        tags=tags,
        stale_reason=stale_reason,
        atom_id=atom_id,
        superseded_by_ref=superseded_by_ref,
    )


def test_memory_atom_wraps_explicit_source_artifact() -> None:
    atom = create_memory_atom(
        artifact_ref=_plan_ref(),
        target_profile="builder",
        task="map artifact memory surfaces",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        summary_text="Research planning artifact for artifact memory work.",
        summary_origin="artifact_projection",
        tags=("memory", "research"),
        atom_id="atom-research-plan",
    )

    assert atom["kind"] == MEMORY_ATOM_KIND
    assert atom["artifact_is_authority"] is False
    assert atom["grants_authority"] is False
    assert atom["governance"]["hidden_memory"] is False
    assert atom["governance"]["opaque_vector_store"] == "DISABLED"
    assert atom["governance"]["model_summary_is_authority"] is False
    assert validate_memory_atom(atom) == []


def test_handoff_memory_atom_requires_explicit_source_refs() -> None:
    handoff = create_handoff_note(
        target_name="builder",
        summary="Prepared a governed handoff.",
        next_recommended_action="Review and continue.",
    )
    atom = create_memory_atom(
        artifact_ref=create_memory_ref(
            kind=HANDOFF_NOTE_KIND,
            path="handoff-note.json",
            sha256=canonical_digest(handoff),
            role="source_artifact",
            name="handoff-note.json",
        ),
        target_profile="builder",
        task="continue artifact memory work",
        created_at_utc=TIMESTAMP,
        claim_boundary="reviewed_handoff",
        summary_text="Handoff summary only.",
        summary_origin="artifact_projection",
        atom_id="atom-handoff",
    )

    errors = validate_memory_atom(atom)
    assert "handoff-derived memory atoms require source_refs to avoid source-truth inflation" in errors


def test_memory_atom_rejects_model_summary_as_authority() -> None:
    atom = create_memory_atom(
        artifact_ref=_plan_ref(),
        target_profile="builder",
        task="map artifact memory surfaces",
        created_at_utc=TIMESTAMP,
        claim_boundary="verification_result",
        source_truth_state="SOURCE_BOUND",
        summary_text="Model summary",
        summary_origin="model",
        atom_id="atom-model-summary",
    )

    errors = validate_memory_atom(atom)
    assert "summary_origin model requires claim_boundary derived_summary" in errors
    assert "summary_origin model requires source_truth_state DERIVED_SUMMARY" in errors
    assert "summary_origin model requires source_refs" in errors


def test_memory_index_search_and_reconstruction_are_deterministic() -> None:
    active = _make_atom(
        atom_id="atom-release-active",
        path="research-plan-active.json",
        summary_text="Release memory atom for current builder memory work.",
        tags=("release", "memory"),
    )
    stale = _make_atom(
        atom_id="atom-release-stale",
        path="research-plan-stale.json",
        summary_text="Release memory atom from a stale handoff review.",
        tags=("release", "handoff"),
        atom_state="STALE",
        stale_reason="Source artifact predates the latest memory chain.",
    )
    stale["review_state"] = "operator_reviewed"
    stale["atom_digest"] = canonical_digest({k: v for k, v in stale.items() if k != "atom_digest"})
    successor_ref = create_memory_ref(
        kind=MEMORY_ATOM_KIND,
        path="atom-release-active.json",
        sha256=canonical_digest(active),
        role="superseded_by",
        name="atom-release-active",
    )
    superseded = _make_atom(
        atom_id="atom-release-superseded",
        path="research-plan-superseded.json",
        summary_text="Old release atom that has been superseded.",
        tags=("release", "old"),
        atom_state="SUPERSEDED",
        stale_reason="Replaced by atom-release-active.",
        superseded_by_ref=successor_ref,
    )

    assert validate_memory_atom(active) == []
    assert validate_memory_atom(stale) == []
    assert validate_memory_atom(superseded) == []

    entries = [
        create_memory_index_entry(active, path="atom-release-active.json"),
        create_memory_index_entry(stale, path="atom-release-stale.json"),
        create_memory_index_entry(superseded, path="atom-release-superseded.json"),
    ]
    index = create_memory_index(
        entries=entries,
        target_profile="builder",
        created_at_utc=TIMESTAMP,
        index_name="builder-memory-release",
        task_scope="artifact memory release review",
    )
    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path="memory-index.json",
        sha256=canonical_digest(index),
        role="memory_index",
        name="memory-index.json",
    )

    assert validate_memory_index(index) == []

    result_a = create_memory_search_result(
        index,
        index_ref=index_ref,
        query="release memory",
        created_at_utc=TIMESTAMP,
        limit=10,
    )
    result_b = create_memory_search_result(
        index,
        index_ref=index_ref,
        query="release memory",
        created_at_utc=TIMESTAMP,
        limit=10,
    )

    assert validate_memory_search_result(result_a) == []
    assert result_a == result_b
    assert [item["atom_id"] for item in result_a["matches"]] == [
        "atom-release-active",
        "atom-release-stale",
    ]
    assert result_a["excluded_atom_refs"][0]["reason"] == "excluded atom_state=superseded"

    reconstruction = create_memory_reconstruction(
        index,
        index_ref=index_ref,
        query="release memory",
        created_at_utc=TIMESTAMP,
        max_atoms=2,
    )

    assert validate_memory_reconstruction(reconstruction) == []
    assert [ref["name"] for ref in reconstruction["selected_atom_refs"]] == [
        "atom-release-active",
        "atom-release-stale",
    ]
    assert "atom-release-stale is marked STALE" in reconstruction["warnings"]


def test_memory_kinds_are_registered_and_chain_visible() -> None:
    for kind in (
        MEMORY_ATOM_KIND,
        MEMORY_INDEX_KIND,
        MEMORY_SEARCH_RESULT_KIND,
        MEMORY_RECONSTRUCTION_KIND,
    ):
        assert kind in INDEX_VALIDATORS
        assert kind in CHAIN_VALIDATORS

    atom = create_memory_atom(
        artifact_ref=_plan_ref(),
        target_profile="builder",
        task="map artifact memory surfaces",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        summary_text="Research planning artifact for artifact memory work.",
        summary_origin="artifact_projection",
        tags=("memory",),
        atom_id="atom-chain-visible",
    )
    index = create_memory_index(
        entries=[create_memory_index_entry(atom, path="atom-chain-visible.json")],
        target_profile="builder",
        created_at_utc=TIMESTAMP,
        index_name="builder-memory-chain",
    )
    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path="memory-index.json",
        sha256=index["index_digest"],
        role="memory_index",
        name="memory-index.json",
    )
    search = create_memory_search_result(
        index,
        index_ref=index_ref,
        query="memory",
        created_at_utc=TIMESTAMP,
        limit=5,
    )
    reconstruction = create_memory_reconstruction(
        index,
        index_ref=index_ref,
        query="memory",
        created_at_utc=TIMESTAMP,
        max_atoms=5,
    )

    atom_refs = extract_references(atom)
    assert atom_refs[0]["field"] == "artifact_ref"
    assert atom_refs[0]["expected_kind"] == RESEARCH_PLAN_KIND

    index_refs = extract_references(index)
    assert index_refs == [
        {
            "field": "entries[0].atom_ref",
            "sha256": canonical_digest(atom),
            "path": "atom-chain-visible.json",
            "expected_kind": MEMORY_ATOM_KIND,
        }
    ]

    search_refs = extract_references(search)
    assert search_refs[0]["field"] == "index_ref"
    assert search_refs[1]["field"] == "matches[0].atom_ref"

    reconstruction_refs = extract_references(reconstruction)
    assert reconstruction_refs[0]["field"] == "index_ref"
    assert reconstruction_refs[1]["field"] == "selected_atom_refs[0]"


def test_memory_artifact_chain_verification_resolves_explicit_sources(tmp_path: Path) -> None:
    plan = _research_plan()
    plan_path = tmp_path / "research-plan.json"
    plan_path.write_text(json_lib.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    atom = create_memory_atom(
        artifact_ref=create_memory_ref(
            kind=RESEARCH_PLAN_KIND,
            path=plan_path,
            sha256=canonical_digest(plan),
            role="source_artifact",
            name=plan_path.name,
        ),
        target_profile="builder",
        task="map artifact memory surfaces",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        summary_text="Research planning artifact for artifact memory work.",
        summary_origin="artifact_projection",
        tags=("memory", "research"),
        atom_id="atom-chain",
    )
    atom_path = tmp_path / "memory-atom.json"
    write_memory_atom(atom, atom_path)

    index = create_memory_index(
        entries=[create_memory_index_entry(atom, path=atom_path)],
        target_profile="builder",
        created_at_utc=TIMESTAMP,
        index_name="builder-memory-chain",
    )
    index_path = tmp_path / "memory-index.json"
    write_memory_index(index, index_path)

    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path=index_path,
        sha256=canonical_digest(index),
        role="memory_index",
        name=index_path.name,
    )
    search = create_memory_search_result(
        index,
        index_ref=index_ref,
        query="memory research",
        created_at_utc=TIMESTAMP,
        limit=5,
    )
    search_path = tmp_path / "memory-search.json"
    write_memory_search_result(search, search_path)

    reconstruction = create_memory_reconstruction(
        index,
        index_ref=index_ref,
        query="memory research",
        created_at_utc=TIMESTAMP,
        max_atoms=5,
    )
    reconstruction_path = tmp_path / "memory-reconstruction.json"
    write_memory_reconstruction(reconstruction, reconstruction_path)

    report = verify_artifact_chain([plan_path, atom_path, index_path, search_path, reconstruction_path])

    assert report["valid"] is True, report["errors"]
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0


def test_b8_atom_state_rejected_and_invalidated() -> None:
    # 1. REJECTED is valid
    atom_rejected = _make_atom(
        atom_id="atom-rejected",
        path="research-plan-rejected.json",
        summary_text="Rejected memory atom.",
        tags=("memory", "rejected"),
        atom_state="REJECTED",
        stale_reason="This proposal was rejected during operator review.",
    )
    atom_rejected["review_state"] = "rejected"
    # Recalculate digest
    from builder_ii.governance.ledger.workflow_records import canonical_digest

    atom_rejected.pop("atom_digest", None)
    atom_rejected["atom_digest"] = canonical_digest(atom_rejected)
    assert validate_memory_atom(atom_rejected) == []

    # 2. INVALIDATED is rejected
    atom_invalidated = dict(atom_rejected)
    atom_invalidated["atom_state"] = "INVALIDATED"
    atom_invalidated.pop("atom_digest", None)
    atom_invalidated["atom_digest"] = canonical_digest(atom_invalidated)
    errors = validate_memory_atom(atom_invalidated)
    assert any("atom_state must be one of" in error for error in errors)


def test_b8_ref_validation() -> None:
    ref = _plan_ref()
    assert (
        validate_memory_atom(
            create_memory_atom(
                artifact_ref=ref,
                target_profile="builder",
                task="ref check",
                created_at_utc=TIMESTAMP,
                claim_boundary="proposal_only",
                atom_id="atom-ref-ok",
            )
        )
        == []
    )

    # Missing name in ref
    bad_ref_name = dict(ref)
    bad_ref_name.pop("name")
    atom_bad_name = create_memory_atom(
        artifact_ref=bad_ref_name,
        target_profile="builder",
        task="ref check",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        atom_id="atom-ref-bad-name",
    )
    assert any("artifact_ref.name is required" in err for err in validate_memory_atom(atom_bad_name))

    # Missing required in ref
    bad_ref_req = dict(ref)
    bad_ref_req.pop("required")
    atom_bad_req = create_memory_atom(
        artifact_ref=bad_ref_req,
        target_profile="builder",
        task="ref check",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        atom_id="atom-ref-bad-req",
    )
    assert any("artifact_ref.required is required" in err for err in validate_memory_atom(atom_bad_req))


def test_b8_atom_authority_rejection() -> None:
    atom_ok = create_memory_atom(
        artifact_ref=_plan_ref(),
        target_profile="builder",
        task="ref check",
        created_at_utc=TIMESTAMP,
        claim_boundary="proposal_only",
        atom_id="atom-auth-ok",
    )
    assert validate_memory_atom(atom_ok) == []

    # model_summary_is_authority=true is rejected
    bad_atom_summary = dict(atom_ok)
    bad_atom_summary["model_summary_is_authority"] = True
    bad_atom_summary.pop("atom_digest", None)
    from builder_ii.governance.ledger.workflow_records import canonical_digest

    bad_atom_summary["atom_digest"] = canonical_digest(bad_atom_summary)
    assert any(
        "model_summary_is_authority must be false or NOT_AUTHORIZED" in err
        for err in validate_memory_atom(bad_atom_summary)
    )

    # target_repo_mutation=true is rejected
    bad_atom_mutation = dict(atom_ok)
    bad_atom_mutation["target_repo_mutation"] = True
    bad_atom_mutation.pop("atom_digest", None)
    bad_atom_mutation["atom_digest"] = canonical_digest(bad_atom_mutation)
    assert any(
        "target_repo_mutation must be false or NOT_AUTHORIZED" in err for err in validate_memory_atom(bad_atom_mutation)
    )


def test_b8_index_schema_fields() -> None:
    active = _make_atom(atom_id="atom-active", path="active.json", summary_text="active atom", tags=("active",))
    entries = [create_memory_index_entry(active, path="active.json")]
    index = create_memory_index(
        entries=entries,
        target_profile="builder",
        created_at_utc=TIMESTAMP,
        index_name="builder-index",
    )
    assert validate_memory_index(index) == []
    assert "atom_refs" in index
    assert "source_artifact_refs" in index
    assert index["deterministic_sort_key"] == "atom_ref.sha256_atom_id"
    assert "stale_atom_ids" in index
    assert "superseded_atom_ids" in index
    assert index["search_keys"] == ["tags", "task", "summary_text", "artifact_kind"]


def test_b8_reconstruction_schema_fields() -> None:
    active = _make_atom(atom_id="atom-active", path="active.json", summary_text="active atom", tags=("active",))
    entries = [create_memory_index_entry(active, path="active.json")]
    index = create_memory_index(
        entries=entries,
        target_profile="builder",
        created_at_utc=TIMESTAMP,
        index_name="builder-index",
    )
    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path="memory-index.json",
        sha256=canonical_digest(index),
        role="memory_index",
        name="memory-index.json",
    )
    reconstruction = create_memory_reconstruction(
        index,
        index_ref=index_ref,
        query="active",
        created_at_utc=TIMESTAMP,
        max_atoms=5,
    )
    assert validate_memory_reconstruction(reconstruction) == []
    assert reconstruction["no_source_truth_inflation"] is True
    assert "source_refs" in reconstruction
    assert "stale_warnings" in reconstruction
    assert "supersession_warnings" in reconstruction
    assert (
        reconstruction["deterministic_ordering_declaration"]
        == "matches are sorted by score descending, then atom_id ascending"
    )
