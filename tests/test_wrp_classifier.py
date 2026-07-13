from __future__ import annotations

from builder_ii.wrp.workload_classifier import (
    CLASSIFIER_GOLDEN_FIXTURES,
    classify_workload,
    score_classifier_fixtures,
    validate_workload_classification,
)


def test_classify_produces_valid_artifact() -> None:
    art = classify_workload(text="implement a new validation helper")
    assert validate_workload_classification(art) == []
    assert art["executes_model"] is False
    assert art["grants_authority"] is False
    assert art["classification"]["tier"] in {"fast", "primary", "primary_constrained"}


def test_low_confidence_or_safety_fallback_paths() -> None:
    art = classify_workload(text="audit the security policy gate and secret handling")
    assert art["classification"]["tier"] == "fast"
    assert art["recommended_model_alias"] == "phi-reasoning"


def test_w0_fixture_accuracy_at_least_95_percent() -> None:
    report = score_classifier_fixtures(CLASSIFIER_GOLDEN_FIXTURES)
    assert report["meets_w0_threshold"], (
        f"accuracy={report['accuracy']:.3f} rows={[(r['text'], r['expected'], r['got']) for r in report['rows'] if not r['ok']]}"
    )
