"""W0.1 — price book artifact and token accounting honesty."""

from __future__ import annotations

from pathlib import Path

from builder_ii.routing.price_book import (
    PRICE_BOOK_KIND,
    create_default_price_book,
    lookup_price_entry,
    validate_price_book,
    write_price_book,
)
from builder_ii.routing.token_accounting import (
    TOKENIZER_WHITESPACE_V1,
    build_cost_report,
    count_tokens,
    count_tokens_whitespace_v1,
    estimate_usd,
)


def test_whitespace_tokenizer_is_measured_and_deterministic() -> None:
    a = count_tokens_whitespace_v1("hello world")
    b = count_tokens_whitespace_v1("hello world")
    assert a.token_count == 2
    assert a.token_accounting == "measured"
    assert a.tokenizer_id == TOKENIZER_WHITESPACE_V1
    assert a.token_count == b.token_count
    assert a.tokenizer_version == b.tokenizer_version


def test_punctuation_isolates_tokens() -> None:
    r = count_tokens_whitespace_v1("hello, world!")
    # hello , world !
    assert r.token_count == 4
    assert r.token_accounting == "measured"


def test_empty_prompt_zero_tokens() -> None:
    r = count_tokens("   ")
    assert r.token_count == 0
    assert r.token_accounting == "measured"


def test_estimate_usd_math() -> None:
    usd = estimate_usd(
        input_tokens=1000,
        output_tokens=500,
        input_usd_per_1k=1.0,
        output_usd_per_1k=2.0,
    )
    assert usd["estimated_usd_input"] == 1.0
    assert usd["estimated_usd_output"] == 1.0
    assert usd["estimated_usd_total"] == 2.0


def test_build_cost_report_measured_fields() -> None:
    report = build_cost_report(
        prompt="one two three",
        response_text="four five",
        model_id="gpt-4o-stub",
        input_usd_per_1k=0.001,
        output_usd_per_1k=0.002,
        price_book_ref={"kind": PRICE_BOOK_KIND, "sha256": "a" * 64},
    )
    assert report["token_accounting"] == "measured"
    assert report["input_tokens"] == 3
    assert report["output_tokens"] == 2
    assert report["total_tokens"] == 5
    assert report["tokenizer_id"]
    assert report["tokenizer_version"]
    assert "estimated_usd_total" in report
    assert report["price_book_ref"]["sha256"] == "a" * 64


def test_default_price_book_valid_and_digested() -> None:
    book = create_default_price_book()
    assert book["kind"] == PRICE_BOOK_KIND
    assert book["price_book_state"] == "RECORDED_ONLY"
    assert book["grants_authority"] is False
    assert validate_price_book(book) == []
    assert len(book["digest"]) == 64
    entry = lookup_price_entry(book, "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit")
    assert entry is not None
    assert entry["input_usd_per_1k"] == 0.0
    assert entry["cost_class"] == "free_local"


def test_price_book_rejects_negative_rates() -> None:
    book = create_default_price_book()
    book["entries"][0]["input_usd_per_1k"] = -1.0
    book.pop("digest", None)
    errors = validate_price_book(book)
    assert any("input_usd_per_1k" in e for e in errors)


def test_price_book_write_roundtrip(tmp_path: Path) -> None:
    book = create_default_price_book()
    path = tmp_path / "price_book.json"
    write_price_book(book, path)
    assert path.is_file()
    from builder_ii.routing.price_book import validate_price_book_file

    assert validate_price_book_file(path) == []
