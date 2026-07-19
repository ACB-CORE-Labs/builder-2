"""W5.1 replay harness."""

from __future__ import annotations

from builder_ii.replay_harness import replay_from_manifest, validate_run_replay_report
from builder_ii.run_manifest import create_run_manifest


def test_replay_ok_on_matching_manifest() -> None:
    prompt_digest = "a" * 64
    m = create_run_manifest(
        model_id="gpt-4o-stub",
        prompt_digest=prompt_digest,
        tokenizer_id="builder_ii.whitespace_v1",
        tokenizer_version="1",
        envelope_digest="b" * 64,
        receipt_digest="c" * 64,
    )
    envelope = {"prompt_digest": prompt_digest, "digest": "b" * 64}
    receipt = {"digest": "c" * 64, "response_text": "non-det"}
    report = replay_from_manifest(m, envelope=envelope, receipt=receipt)
    assert report["deterministic_ok"] is True
    assert report["executes_model"] is False
    assert report["reinvokes_provider"] is False
    assert validate_run_replay_report(report) == []


def test_replay_flags_prompt_mismatch() -> None:
    m = create_run_manifest(
        model_id="m",
        prompt_digest="a" * 64,
        tokenizer_id="t",
        tokenizer_version="1",
    )
    report = replay_from_manifest(m, envelope={"prompt_digest": "b" * 64})
    assert report["deterministic_ok"] is False
