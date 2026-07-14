"""Unit tests for WRP EmbeddingBackend (hash default + ModernBERT opt-in stub)."""

from __future__ import annotations

import math
from typing import get_type_hints

import pytest

from builder_ii.wrp.embedding_backend import (
    DEFAULT_EMBED_DIM,
    MODERNBERT_ENV,
    MODERNBERT_ENV_VALUE,
    BackendUnavailableError,
    EmbeddingBackend,
    HashingEmbedder,
    OptionalModernBertBackend,
    knn_classify,
    modernbert_opt_in_enabled,
    resolve_embedder,
)

# ---------------------------------------------------------------------------
# Protocol surface
# ---------------------------------------------------------------------------


def test_embedding_backend_protocol_has_embed_and_name() -> None:
    assert callable(getattr(EmbeddingBackend, "embed", None))
    annotations = getattr(EmbeddingBackend, "__annotations__", {})
    assert "name" in annotations
    hints = get_type_hints(EmbeddingBackend.embed)
    assert "texts" in hints
    ret = hints["return"]
    assert getattr(ret, "__origin__", None) is list or str(ret).startswith("list")


def test_hashing_embedder_satisfies_protocol() -> None:
    backend: EmbeddingBackend = HashingEmbedder()
    assert isinstance(backend, EmbeddingBackend)
    assert isinstance(backend.name, str) and backend.name
    vectors = backend.embed(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == DEFAULT_EMBED_DIM


# ---------------------------------------------------------------------------
# HashingEmbedder — deterministic, M1-safe, no ML deps
# ---------------------------------------------------------------------------


def test_hashing_embedder_fixed_dim() -> None:
    emb = HashingEmbedder(dim=32)
    out = emb.embed(["a", "b", "c"])
    assert len(out) == 3
    assert all(len(v) == 32 for v in out)
    assert all(all(isinstance(x, float) for x in v) for v in out)


def test_hashing_embedder_default_dim_is_64() -> None:
    emb = HashingEmbedder()
    assert len(emb.embed(["x"])[0]) == 64
    assert DEFAULT_EMBED_DIM == 64


def test_hashing_embedder_deterministic_same_text() -> None:
    emb = HashingEmbedder()
    a = emb.embed(["classify this workload"])
    b = emb.embed(["classify this workload"])
    assert a == b
    # Two separate instances must agree (no process-salted hash).
    emb2 = HashingEmbedder()
    assert emb2.embed(["classify this workload"]) == a


def test_hashing_embedder_different_texts_not_identical() -> None:
    emb = HashingEmbedder()
    v1 = emb.embed(["implement a new validation helper"])[0]
    v2 = emb.embed(["audit the security policy gate"])[0]
    assert v1 != v2


def test_hashing_embedder_does_not_mutate_input() -> None:
    emb = HashingEmbedder()
    texts = ["alpha", "beta"]
    snapshot = list(texts)
    emb.embed(texts)
    assert texts == snapshot


def test_hashing_embedder_batch_order_preserved() -> None:
    emb = HashingEmbedder()
    texts = ["one", "two", "three"]
    batch = emb.embed(texts)
    singles = [emb.embed([t])[0] for t in texts]
    assert batch == singles


def test_hashing_embedder_empty_batch() -> None:
    emb = HashingEmbedder()
    assert emb.embed([]) == []


def test_hashing_embedder_vectors_are_finite() -> None:
    emb = HashingEmbedder()
    for v in emb.embed(["", "tokens here", "!!!", "a " * 50]):
        assert all(math.isfinite(x) for x in v)


def test_hashing_embedder_rejects_non_positive_dim() -> None:
    with pytest.raises(ValueError, match="dim"):
        HashingEmbedder(dim=0)
    with pytest.raises(ValueError, match="dim"):
        HashingEmbedder(dim=-3)


def test_hashing_embedder_rejects_non_list_texts() -> None:
    emb = HashingEmbedder()
    with pytest.raises((TypeError, ValueError)):
        emb.embed("not-a-list")  # type: ignore[arg-type]


def test_hashing_embedder_rejects_non_str_items() -> None:
    emb = HashingEmbedder()
    with pytest.raises((TypeError, ValueError)):
        emb.embed([123])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# knn_classify
# ---------------------------------------------------------------------------


def test_knn_classify_nearest_centroid_cosine() -> None:
    anchors = {
        "fast": [1.0, 0.0, 0.0],
        "primary": [0.0, 1.0, 0.0],
        "deep": [0.0, 0.0, 1.0],
    }
    label, margin = knn_classify([0.9, 0.1, 0.0], anchors, k=1, metric="cosine")
    assert label == "fast"
    assert isinstance(margin, float)
    assert margin > 0.0


def test_knn_classify_nearest_centroid_l2() -> None:
    anchors = {
        "a": [0.0, 0.0],
        "b": [10.0, 10.0],
    }
    label, margin = knn_classify([0.1, 0.1], anchors, k=1, metric="l2")
    assert label == "a"
    assert margin > 0.0


def test_knn_classify_margin_is_best_minus_second() -> None:
    anchors = {
        "near": [1.0, 0.0],
        "far": [0.0, 1.0],
    }
    # Query almost on "near" unit axis.
    label, margin = knn_classify([1.0, 0.0], anchors, k=1, metric="cosine")
    assert label == "near"
    # Cosine(near)=1.0, cosine(far)=0.0 → margin 1.0
    assert margin == pytest.approx(1.0)


def test_knn_classify_single_anchor_margin() -> None:
    label, margin = knn_classify([1.0, 0.0], {"only": [1.0, 0.0]}, k=1, metric="cosine")
    assert label == "only"
    assert margin >= 0.0


def test_knn_classify_does_not_mutate_inputs() -> None:
    query = [1.0, 0.0]
    anchors = {"x": [1.0, 0.0], "y": [0.0, 1.0]}
    q_snap = list(query)
    a_snap = {k: list(v) for k, v in anchors.items()}
    knn_classify(query, anchors, k=1)
    assert query == q_snap
    assert anchors == a_snap


def test_knn_classify_fail_closed_empty_anchors() -> None:
    with pytest.raises(ValueError, match="anchor"):
        knn_classify([1.0], {}, k=1)


def test_knn_classify_fail_closed_dim_mismatch() -> None:
    with pytest.raises(ValueError, match="dimension|dim|length"):
        knn_classify([1.0, 0.0], {"a": [1.0]}, k=1)


def test_knn_classify_fail_closed_bad_k() -> None:
    with pytest.raises(ValueError, match="k"):
        knn_classify([1.0], {"a": [1.0]}, k=0)


def test_knn_classify_fail_closed_unknown_metric() -> None:
    with pytest.raises(ValueError, match="metric"):
        knn_classify([1.0], {"a": [1.0]}, k=1, metric="manhattan")


def test_knn_classify_with_hashing_vectors() -> None:
    emb = HashingEmbedder(dim=64)
    impl_centroid = emb.embed(["implement refactor debug"])[0]
    audit_centroid = emb.embed(["audit security policy secret"])[0]
    assert impl_centroid != audit_centroid
    # Exact centroid match must win.
    label, margin = knn_classify(
        impl_centroid,
        {"impl": impl_centroid, "audit": audit_centroid},
        k=1,
        metric="cosine",
    )
    assert label == "impl"
    assert margin > 0.0
    # Slightly perturbed query still nearer to its source family under L2.
    near_impl = list(impl_centroid)
    near_impl[0] = near_impl[0] + 1e-3
    label_l2, margin_l2 = knn_classify(
        near_impl,
        {"impl": impl_centroid, "audit": audit_centroid},
        k=1,
        metric="l2",
    )
    assert label_l2 == "impl"
    assert margin_l2 > 0.0


# ---------------------------------------------------------------------------
# OptionalModernBertBackend — opt-in only, default unavailable
# ---------------------------------------------------------------------------


def test_optional_modernbert_unavailable_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MODERNBERT_ENV, raising=False)
    backend = OptionalModernBertBackend()
    assert backend.name == "modernbert"
    with pytest.raises(BackendUnavailableError):
        backend.embed(["hello"])


def test_optional_modernbert_unavailable_without_provider_even_with_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, MODERNBERT_ENV_VALUE)
    backend = OptionalModernBertBackend()
    with pytest.raises(BackendUnavailableError):
        backend.embed(["hello"])


def test_optional_modernbert_works_with_env_and_injected_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, MODERNBERT_ENV_VALUE)

    def fake_provider(texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0, 1.0] for t in texts]

    backend = OptionalModernBertBackend(provider=fake_provider)
    out = backend.embed(["ab", "abcd"])
    assert out == [[2.0, 0.0, 1.0], [4.0, 0.0, 1.0]]


def test_optional_modernbert_provider_alone_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MODERNBERT_ENV, raising=False)

    def fake_provider(texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    backend = OptionalModernBertBackend(provider=fake_provider)
    with pytest.raises(BackendUnavailableError, match="opt-in|BUILDER_II_WRP_EMBEDDER|modernbert"):
        backend.embed(["x"])


def test_optional_modernbert_wrong_env_value_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, "hashing")

    def fake_provider(texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    backend = OptionalModernBertBackend(provider=fake_provider)
    with pytest.raises(BackendUnavailableError):
        backend.embed(["x"])


def test_optional_modernbert_does_not_mutate_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, MODERNBERT_ENV_VALUE)
    seen: list[list[str]] = []

    def fake_provider(texts: list[str]) -> list[list[float]]:
        seen.append(texts)
        texts.append("mutated")  # provider may misbehave; backend must pass a copy
        return [[0.0] for _ in texts]

    original = ["keep"]
    backend = OptionalModernBertBackend(provider=fake_provider)
    backend.embed(original)
    assert original == ["keep"]
    assert seen and seen[0] is not original


def test_optional_modernbert_is_embedding_backend_with_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, MODERNBERT_ENV_VALUE)
    backend: EmbeddingBackend = OptionalModernBertBackend(provider=lambda ts: [[0.0] * 3 for _ in ts])
    assert isinstance(backend, EmbeddingBackend)
    assert backend.embed(["z"]) == [[0.0, 0.0, 0.0]]


def test_backend_unavailable_error_is_runtime_error() -> None:
    assert issubclass(BackendUnavailableError, RuntimeError)


def test_exports_all_public_names() -> None:
    from builder_ii.wrp import embedding_backend as mod

    for name in (
        "EmbeddingBackend",
        "HashingEmbedder",
        "OptionalModernBertBackend",
        "BackendUnavailableError",
        "knn_classify",
        "DEFAULT_EMBED_DIM",
        "MODERNBERT_ENV",
        "MODERNBERT_ENV_VALUE",
        "resolve_embedder",
        "modernbert_opt_in_enabled",
    ):
        assert name in mod.__all__
        assert hasattr(mod, name)


def test_resolve_embedder_defaults_to_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MODERNBERT_ENV, raising=False)
    backend = resolve_embedder()
    assert isinstance(backend, HashingEmbedder)
    assert backend.name == "hashing"
    assert modernbert_opt_in_enabled() is False
    vectors = backend.embed(["default path"])
    assert len(vectors) == 1 and len(vectors[0]) == DEFAULT_EMBED_DIM


def test_resolve_embedder_modernbert_opt_in_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODERNBERT_ENV, MODERNBERT_ENV_VALUE)
    backend = resolve_embedder()
    assert isinstance(backend, OptionalModernBertBackend)
    assert modernbert_opt_in_enabled() is True
    with pytest.raises(BackendUnavailableError):
        backend.embed(["no provider"])
