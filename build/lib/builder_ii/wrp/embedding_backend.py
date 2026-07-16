"""WRP embedding backends — hashing default (M1-safe); ModernBERT-class opt-in only.

Design:
- Default path is pure-stdlib: no torch, transformers, or heavy ML deps.
- Same text → same vector across processes (stable hashlib, not salted ``hash()``).
- OptionalModernBertBackend is fail-closed unless env
  ``BUILDER_II_WRP_EMBEDDER=modernbert`` **and** an injectable/importable provider
  is available. Default unit tests never require ModernBERT installed.

Opt-in ModernBERT (research / source-fidelity profiles only)::

    export BUILDER_II_WRP_EMBEDDER=modernbert
    # then inject provider= callable or ship builder_ii.wrp._optional_modernbert
"""

from __future__ import annotations

import hashlib
import importlib
import math
import os
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, runtime_checkable

DEFAULT_EMBED_DIM: int = 64
MODERNBERT_ENV: str = "BUILDER_II_WRP_EMBEDDER"
MODERNBERT_ENV_VALUE: str = "modernbert"

# Optional module path for a real ModernBERT provider (never shipped by default).
_OPTIONAL_MODERNBERT_MODULE = "builder_ii.wrp._optional_modernbert"

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

EmbedProvider = Callable[[list[str]], list[list[float]]]


class BackendUnavailableError(RuntimeError):
    """Raised when an opt-in embedding backend cannot be used (fail closed)."""


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Minimal embedder contract for WRP workload text → vector."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one float vector per input text. Must not mutate ``texts``."""
        ...


class HashingEmbedder:
    """Deterministic signed feature-hash embedder (no ML dependencies).

    Tokens are lowercased alphanumerics; each token maps to a dimension index and
    a sign via SHA-256. Vectors are L2-normalized when non-zero.
    """

    name: str = "hashing"

    def __init__(self, dim: int = DEFAULT_EMBED_DIM) -> None:
        if not isinstance(dim, int) or dim <= 0:
            raise ValueError(f"dim must be a positive integer, got {dim!r}")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise TypeError("texts must be a list of str")
        # Copy surface so callers retain original list identity/content.
        snapshot = list(texts)
        return [self._embed_one(t) for t in snapshot]

    def _embed_one(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise TypeError("each text must be a str")
        vec = [0.0] * self._dim
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            # First 8 bytes → index; next 8 bytes → sign (stable across platforms).
            index = int.from_bytes(digest[0:8], "big") % self._dim
            sign = 1.0 if (int.from_bytes(digest[8:16], "big") & 1) == 0 else -1.0
            vec[index] += sign
        return _l2_normalize(vec)


def knn_classify(
    query_vec: Sequence[float],
    anchors: Mapping[str, Sequence[float]],
    k: int = 1,
    *,
    metric: str = "cosine",
) -> tuple[str, float]:
    """Nearest-centroid label for ``query_vec`` among named anchor vectors.

    Returns ``(label, confidence_margin)`` where margin is best−second score under
    cosine similarity (higher better) or second−best L2 distance (higher better).
    ``k`` is accepted for API symmetry; classification uses the single nearest
    centroid (k=1). Non-1 values currently raise if k < 1.

    Does not mutate ``query_vec`` or ``anchors``.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if metric not in {"cosine", "l2"}:
        raise ValueError(f"metric must be 'cosine' or 'l2', got {metric!r}")
    if not anchors:
        raise ValueError("anchors must be a non-empty mapping of label → vector")

    query = _as_float_list(query_vec, field="query_vec")
    # Snapshot anchors without mutating caller mapping/lists.
    scored: list[tuple[str, float]] = []
    for label, raw in anchors.items():
        if not isinstance(label, str) or not label:
            raise ValueError("anchor labels must be non-empty strings")
        anchor = _as_float_list(raw, field=f"anchors[{label!r}]")
        if len(anchor) != len(query):
            raise ValueError(
                f"dimension mismatch: query length {len(query)} vs "
                f"anchor {label!r} length {len(anchor)}"
            )
        if metric == "cosine":
            scored.append((label, _cosine_similarity(query, anchor)))
        else:
            scored.append((label, -_l2_distance(query, anchor)))  # higher is better

    # Higher score is better for both metrics (L2 negated above).
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)
    best_label, best_score = ranked[0]
    if len(ranked) == 1:
        # Single anchor: margin is non-negative magnitude of best score for cosine,
        # or absolute L2 distance flipped back for interpretability.
        if metric == "cosine":
            margin = max(0.0, float(best_score))
        else:
            margin = max(0.0, -float(best_score))
        return best_label, float(margin)

    second_score = ranked[1][1]
    # Cosine: best_sim - second_sim. L2 scores are negated distances, so
    # best_score - second_score == second_dist - best_dist (margin ≥ 0 when unique nearest).
    margin = float(best_score - second_score)
    return best_label, margin


class OptionalModernBertBackend:
    """Fail-closed ModernBERT-class embedder stub (opt-in only).

    Activation requires **both**:

    1. Environment: ``BUILDER_II_WRP_EMBEDDER=modernbert``
    2. A provider: constructor ``provider=`` callable, or optional import of
       ``builder_ii.wrp._optional_modernbert.embed``

    Default test runs never install ModernBERT and never set the env var, so
    construction succeeds but ``embed`` always raises ``BackendUnavailableError``.
    """

    name: str = "modernbert"

    def __init__(self, provider: EmbedProvider | None = None) -> None:
        self._provider = provider

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise TypeError("texts must be a list of str")
        if os.environ.get(MODERNBERT_ENV) != MODERNBERT_ENV_VALUE:
            raise BackendUnavailableError(
                "OptionalModernBertBackend is opt-in only; set "
                f"{MODERNBERT_ENV}={MODERNBERT_ENV_VALUE} and provide a provider "
                "(injected or optional module). Default WRP path uses HashingEmbedder."
            )
        provider = self._provider if self._provider is not None else _try_load_modernbert_provider()
        if provider is None:
            raise BackendUnavailableError(
                "ModernBERT provider unavailable: inject provider= callable or install "
                f"optional module {_OPTIONAL_MODERNBERT_MODULE} (not required for M1 defaults)."
            )
        # Pass a shallow copy so a misbehaving provider cannot mutate caller input.
        return provider(list(texts))


def _try_load_modernbert_provider() -> EmbedProvider | None:
    """Attempt optional provider import; never raises — fail closed via None."""
    try:
        mod = importlib.import_module(_OPTIONAL_MODERNBERT_MODULE)
    except ImportError:
        return None
    embed_fn = getattr(mod, "embed", None)
    if not callable(embed_fn):
        return None
    return embed_fn  # type: ignore[return-value]


def modernbert_opt_in_enabled() -> bool:
    """True when env requests ModernBERT (does not imply provider available)."""
    return os.environ.get(MODERNBERT_ENV) == MODERNBERT_ENV_VALUE


def resolve_embedder(
    *,
    dim: int = DEFAULT_EMBED_DIM,
    provider: EmbedProvider | None = None,
) -> EmbeddingBackend:
    """Resolve default embedder: HashingEmbedder unless ModernBERT opt-in is set.

    When ``BUILDER_II_WRP_EMBEDDER=modernbert``:
    - Returns ``OptionalModernBertBackend`` (may still fail on ``embed`` if provider missing).
    Otherwise returns ``HashingEmbedder`` (M1-safe default, never requires torch).
    """
    if modernbert_opt_in_enabled():
        return OptionalModernBertBackend(provider=provider)
    return HashingEmbedder(dim=dim)



def _as_float_list(values: Sequence[float], *, field: str) -> list[float]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field} must be a sequence of floats")
    out: list[float] = []
    for item in values:
        try:
            out.append(float(item))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must contain only numeric values") from exc
    if not out:
        raise ValueError(f"{field} must be a non-empty vector")
    return out


def _l2_normalize(vec: list[float]) -> list[float]:
    norm_sq = sum(x * x for x in vec)
    if norm_sq <= 0.0:
        return list(vec)
    norm = math.sqrt(norm_sq)
    return [x / norm for x in vec]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _l2_distance(a: Sequence[float], b: Sequence[float]) -> float:
    acc = 0.0
    for x, y in zip(a, b, strict=True):
        d = x - y
        acc += d * d
    return math.sqrt(acc)


__all__ = [
    "DEFAULT_EMBED_DIM",
    "MODERNBERT_ENV",
    "MODERNBERT_ENV_VALUE",
    "BackendUnavailableError",
    "EmbeddingBackend",
    "HashingEmbedder",
    "OptionalModernBertBackend",
    "knn_classify",
    "modernbert_opt_in_enabled",
    "resolve_embedder",
]
