"""Plan Set 1 exit-gate evidence for the governed-run lifecycle."""

from pathlib import Path

import pytest

from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity
from builder_ii.lifecycle.candidate.governed_run import (
    GovernedRun,
    SyntheticRuntimeAdapter,
    WrpSubagentRuntimeAdapter,
)


def _run(tmp_path: Path, adapter: SyntheticRuntimeAdapter) -> GovernedRun:
    run = GovernedRun(
        run_id="run-plan-set-1",
        target="builder",
        task="synthetic governed lifecycle",
        steps=["one", "two", "three"],
        output_dir=tmp_path,
        adapter=adapter,
    )
    run.prepare()
    return run


def test_complete_interrupt_resume_fail_cancel_and_close(tmp_path: Path) -> None:
    run = _run(tmp_path / "complete", SyntheticRuntimeAdapter())
    assert run.start() == "completed"
    receipt = run.close()
    assert receipt["terminal_state"] == "completed"
    assert receipt["unexecuted_steps"] == []

    interrupted = _run(tmp_path / "resume", SyntheticRuntimeAdapter(interrupt_at=1))
    assert interrupted.start() == "interrupted"
    checkpoint = interrupted.checkpoint_path.read_text(encoding="utf-8")
    assert "INTERRUPT_RECORDED" in checkpoint
    interrupted.adapter = SyntheticRuntimeAdapter()
    assert interrupted.resume() == "completed"
    assert interrupted.close()["completed_steps"] == [0, 1, 2]

    failed = _run(tmp_path / "failed", SyntheticRuntimeAdapter(fail_at=1))
    assert failed.start() == "failed"
    failed_receipt = failed.close()
    assert failed_receipt["completed_steps"] == [0]
    assert failed_receipt["unexecuted_steps"] == [1, 2]

    cancelled = _run(tmp_path / "cancelled", SyntheticRuntimeAdapter())
    assert cancelled.cancel() == "cancelled"
    assert cancelled.close()["unexecuted_steps"] == [0, 1, 2]


def test_resume_rejects_foreign_or_corrupt_checkpoint(tmp_path: Path) -> None:
    run = _run(tmp_path, SyntheticRuntimeAdapter(interrupt_at=0))
    assert run.start() == "interrupted"
    original = run.checkpoint_path.read_text(encoding="utf-8")
    data = __import__("json").loads(original)
    data["run_id"] = "foreign"
    run.checkpoint_path.write_text(__import__("json").dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="different run"):
        run.resume()


def test_one_chain_has_monotonic_sequence_and_no_unexecuted_claims(tmp_path: Path) -> None:
    run = _run(tmp_path, SyntheticRuntimeAdapter(fail_at=2))
    assert run.start() == "failed"
    events = validate_event_chain_integrity(run.events_dir)
    assert events["valid"] is True
    assert events["event_count"] == 4  # prepare, step 0, step 1, failure
    receipt = run.close()
    assert receipt["unexecuted_steps"] == [2]
    assert receipt["grants_authority"] is False


def test_wrp_adapter_is_the_existing_subagent_caller(route_sources_factory) -> None:
    adapter = WrpSubagentRuntimeAdapter(
        role="code_reviewer",
        route_sources=route_sources_factory("adapter"),
        plan_digest="1" * 64,
        approved_by="test-operator",
    )
    assert adapter.name == "wrp-subagent"
    assert adapter.version == "1"
    assert adapter.executes_model is True
