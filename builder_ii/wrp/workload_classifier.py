"""W0 / F0 — WorkloadClassifier (STAR reference, deterministic rules).

Maps free-text or explicit coordinates into WorkloadPoint + model tier recommendation.
Low-confidence STAR-style fallback routes to the safer local tier.
"""

from __future__ import annotations

import os
import re
from typing import Any

from builder_ii.wrp.artifacts import (
    WORKLOAD_CLASSIFICATION_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.spaces import WorkloadPoint, workload_distance

ENV_WRP_EMBED = "BUILDER_II_WRP_EMBED"

# Anchor prototypes for nearest-centroid style classification (fixed, not trained).
_ANCHORS: dict[str, WorkloadPoint] = {
    "fast_local": WorkloadPoint(domain=0.2, difficulty=0.15, safety=0.3, context=0.2, interaction=0.2),
    "primary_local": WorkloadPoint(domain=0.5, difficulty=0.5, safety=0.4, context=0.45, interaction=0.4),
    "high_complexity": WorkloadPoint(domain=0.75, difficulty=0.85, safety=0.55, context=0.8, interaction=0.7),
    "safety_audit": WorkloadPoint(domain=0.4, difficulty=0.55, safety=0.95, context=0.5, interaction=0.35),
}

_TIER_FOR_ANCHOR: dict[str, str] = {
    "fast_local": "fast",
    "primary_local": "primary",
    "high_complexity": "primary_constrained",
    "safety_audit": "fast",  # safer small reasoning lane
}

_FALLBACK_TIER = "fast"
_LOW_CONFIDENCE_THRESHOLD = 0.35  # max margin between best and second; smaller → low conf

_FAST_RE = re.compile(
    r"\b(explain|what|where|find|search|list|describe|summarize|doc|read|show|inspect|status)\b",
    re.I,
)
_DEEP_RE = re.compile(
    r"\b(implement|fix|write|refactor|debug|build|generate|migrate|optimize|rewrite|test)\b",
    re.I,
)
_LOGIC_RE = re.compile(
    r"\b(audit|review|verify|validate|prove|invariant|governance|safety|refusal|adr)\b",
    re.I,
)
_HEAVY_RE = re.compile(
    r"\b(whole repo|entire repo|deep refactor|multi-file|cross-module|architecture-wide|global migration)\b",
    re.I,
)
_SAFETY_RE = re.compile(r"\b(security|secret|auth|permission|opa|msda|policy gate|cryptograph)\b", re.I)


def text_to_workload(text: str) -> WorkloadPoint:
    """Rule-based feature extraction from free text (no embeddings)."""
    domain = 0.35
    difficulty = 0.3
    safety = 0.35
    context = 0.3
    interaction = 0.3

    fast_hit = bool(_FAST_RE.search(text))
    deep_hit = bool(_DEEP_RE.search(text))
    logic_hit = bool(_LOGIC_RE.search(text))
    heavy_hit = bool(_HEAVY_RE.search(text))
    safety_hit = bool(_SAFETY_RE.search(text))

    # Status/show/list probes win over incidental deep tokens like "build" in "status of the build".
    probe_only = bool(re.search(r"\b(status|show|list|describe|explain|summarize|read|inspect)\b", text, re.I))
    generative = bool(
        re.search(
            r"\b(implement|fix|write|refactor|debug|add|create|patch|generate|migrate|optimize|rewrite)\b",
            text,
            re.I,
        )
    )

    if fast_hit:
        difficulty = min(difficulty, 0.25)
        domain = 0.25
    if deep_hit and not (probe_only and not generative):
        difficulty = max(difficulty, 0.55)
        domain = max(domain, 0.55)
        interaction = max(interaction, 0.5)
    if logic_hit and not generative:
        # Pure audit/review/validate → safer small lane; generative+validate stays primary.
        safety = max(safety, 0.7)
        difficulty = max(difficulty, 0.45)
        domain = min(domain, 0.4)
    elif logic_hit and generative:
        difficulty = max(difficulty, 0.55)
        domain = max(domain, 0.55)
    if heavy_hit:
        difficulty = max(difficulty, 0.85)
        context = max(context, 0.85)
        interaction = max(interaction, 0.75)
    if safety_hit:
        safety = max(safety, 0.9)
    # Length as coarse context proxy
    tokens = max(1, len(text.split()))
    context = max(context, min(1.0, tokens / 200.0))
    return WorkloadPoint(
        domain=domain,
        difficulty=difficulty,
        safety=safety,
        context=context,
        interaction=interaction,
    )


def _use_embedding_backend(explicit: bool | None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.getenv(ENV_WRP_EMBED, "").strip().lower() in {"1", "true", "yes", "on"}


def _classify_with_embedding(text: str) -> tuple[str, float, dict[str, float], str]:
    """HashingEmbedder + kNN over anchor label strings (M1-safe default backend)."""
    from builder_ii.wrp.embedding_backend import HashingEmbedder, knn_classify

    embedder = HashingEmbedder()
    labels = list(_ANCHORS.keys())
    # Embed short canonical phrases for each anchor (stable, deterministic).
    phrases = {
        "fast_local": "explain list show status summarize read inspect",
        "primary_local": "implement fix write refactor debug build test",
        "high_complexity": "whole repo multi-file architecture-wide global migration",
        "safety_audit": "audit security governance policy validate prove invariant",
    }
    vectors = embedder.embed([phrases[name] for name in labels])
    anchors = {name: vec for name, vec in zip(labels, vectors, strict=True)}
    query = embedder.embed([text])[0]
    label, margin = knn_classify(query, anchors, k=1, metric="cosine")
    # Cosine margin is small; map to distances for API compatibility.
    distances = {name: (0.0 if name == label else 1.0 - min(margin, 0.99)) for name in labels}
    distances[label] = max(0.0, 1.0 - margin)
    return label, float(margin), distances, embedder.name


def classify_workload(
    *,
    text: str | None = None,
    point: WorkloadPoint | None = None,
    use_embedding: bool | None = None,
    phi: dict[str, float] | None = None,
    phi_policy_digest: str | None = None,
) -> dict[str, Any]:
    """Classify a workload into tier + anchor with confidence and fallback path.

    Default: rule + WorkloadPoint Euclidean anchors (``DEFAULT_PHI``).
    Optional ``phi`` (from HITL-applied ``phi_policy``) overrides distance weights only
    when explicitly passed — never silent live default mutation.
    When ``use_embedding=True`` or ``BUILDER_II_WRP_EMBED=1``: HashingEmbedder + kNN
    (ModernBERT remains opt-in via embedding_backend, not default here).
    """
    embed_mode = _use_embedding_backend(use_embedding)
    embedder_name: str | None = None
    phi_map = phi  # explicit bind only

    if point is None:
        if not text:
            raise ValueError("text or point is required")
        if embed_mode:
            best_name, margin, distances, embedder_name = _classify_with_embedding(text)
            best_dist = distances[best_name]
            point = text_to_workload(text)  # still emit workload coords for R integrity
            second_dist = sorted(distances.values())[1] if len(distances) > 1 else best_dist + 1.0
        else:
            point = text_to_workload(text)
            distances = {
                name: workload_distance(point, anchor, phi=phi_map)
                for name, anchor in _ANCHORS.items()
            }
            ranked = sorted(distances.items(), key=lambda kv: kv[1])
            best_name, best_dist = ranked[0]
            second_dist = ranked[1][1] if len(ranked) > 1 else best_dist + 1.0
            margin = second_dist - best_dist
    else:
        if text is None:
            text = ""
        distances = {
            name: workload_distance(point, anchor, phi=phi_map)
            for name, anchor in _ANCHORS.items()
        }
        ranked = sorted(distances.items(), key=lambda kv: kv[1])
        best_name, best_dist = ranked[0]
        second_dist = ranked[1][1] if len(ranked) > 1 else best_dist + 1.0
        margin = second_dist - best_dist

    # Confidence: closer to anchor and larger margin → higher
    proximity = 1.0 / (1.0 + best_dist)
    confidence_score = proximity * (0.5 + 0.5 * min(1.0, margin / 0.5))
    if confidence_score >= 0.65:
        confidence = "high"
    elif confidence_score >= _LOW_CONFIDENCE_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    tier = _TIER_FOR_ANCHOR[best_name]
    fallback_applied = False
    if confidence == "low" or point.safety >= 0.85:
        # STAR-style low-confidence / high-safety fallback
        if confidence == "low" or best_name != "safety_audit":
            tier = _FALLBACK_TIER
            fallback_applied = confidence == "low"
            if point.safety >= 0.85:
                tier = "fast"
                best_name = "safety_audit"

    # High complexity never auto-escalates to cloud/heavy — only primary_constrained.
    if best_name == "high_complexity" and not fallback_applied:
        tier = "primary_constrained"

    rationale = (
        f"nearest_anchor={best_name} dist={best_dist:.4f} margin={margin:.4f} "
        f"confidence={confidence} tier={tier} fallback={fallback_applied}"
    )
    if embedder_name:
        rationale += f" embedder={embedder_name}"
    return base_envelope(
        kind=WORKLOAD_CLASSIFICATION_KIND,
        artifact_state="RECOMMENDATION_ONLY",
        capability_state="wrp_recommendation_only",
        extra={
            "input_text_snippet": " ".join((text or "").split())[:120],
            "workload": point.to_jsonable(),
            "classification": {
                "anchor": best_name,
                "tier": tier,
                "confidence": confidence,
                "confidence_score": round(confidence_score, 6),
                "distances": {k: round(v, 6) for k, v in distances.items()},
                "fallback_applied": fallback_applied,
                "fallback_tier": _FALLBACK_TIER,
                "rationale": rationale,
                "method": "embedding_knn" if embed_mode and embedder_name else "workload_metric",
                "embedder": embedder_name,
            },
            "recommended_model_alias": {
                "fast": "phi-reasoning",
                "primary": "qwen-coder",
                "primary_constrained": "qwen-coder",
            }.get(tier, "phi-reasoning"),
            "phi_bound": phi_map is not None,
            "phi_policy_digest": phi_policy_digest if phi_map is not None else None,
            "executes_model": False,
            "grants_authority": False,
        },
    )


def validate_workload_classification(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=WORKLOAD_CLASSIFICATION_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("artifact_state") != "RECOMMENDATION_ONLY":
        errors.append("artifact_state must be RECOMMENDATION_ONLY")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    clf = record.get("classification")
    if not isinstance(clf, dict):
        errors.append("classification must be an object")
    else:
        if clf.get("tier") not in {"fast", "primary", "primary_constrained"}:
            errors.append("classification.tier invalid")
        if clf.get("confidence") not in {"high", "medium", "low"}:
            errors.append("classification.confidence invalid")
    workload = record.get("workload")
    if not isinstance(workload, dict) or workload.get("space") != "W":
        errors.append("workload must be a WorkloadPoint jsonable with space=W")
    return errors


# ---------------------------------------------------------------------------
# Acceptance fixture set for ≥95% routing accuracy (W0 criterion)
# ---------------------------------------------------------------------------

CLASSIFIER_GOLDEN_FIXTURES: tuple[tuple[str, str], ...] = (
    ("explain what this module does", "fast"),
    ("list the files in the package", "fast"),
    ("summarize the README", "fast"),
    ("show current status of the build", "fast"),
    ("describe the config schema", "fast"),
    ("implement a new CLI command for sessions", "primary"),
    ("fix the failing unit test in routing", "primary"),
    ("refactor the orchestration plan validator", "primary"),
    ("write integration tests for the gateway", "primary"),
    ("debug the digest mismatch in validation", "primary"),
    ("build a passive artifact emitter", "primary"),
    ("add schema validation for the new kind", "primary"),
    ("audit the security boundaries of the tool gateway", "fast"),
    ("review governance invariants in the ADR", "fast"),
    ("verify the policy gate denies unauthorized tools", "fast"),
    ("validate artifact digests against the chain", "fast"),
    ("prove the invariant holds for fail-closed routing", "fast"),
    ("whole repo deep refactor across modules", "primary_constrained"),
    ("architecture-wide multi-file migration plan", "primary_constrained"),
    ("cross-module call graph global migration", "primary_constrained"),
)


def score_classifier_fixtures(
    fixtures: tuple[tuple[str, str], ...] = CLASSIFIER_GOLDEN_FIXTURES,
) -> dict[str, Any]:
    """Return accuracy over golden fixtures for W0 acceptance."""
    correct = 0
    rows: list[dict[str, Any]] = []
    for text, expected_tier in fixtures:
        result = classify_workload(text=text)
        got = result["classification"]["tier"]
        ok = got == expected_tier
        if ok:
            correct += 1
        rows.append({"text": text, "expected": expected_tier, "got": got, "ok": ok})
    total = len(fixtures)
    accuracy = correct / total if total else 0.0
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "meets_w0_threshold": accuracy >= 0.95,
        "rows": rows,
    }
