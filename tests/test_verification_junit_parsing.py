"""Degradation contract for the runner's JUnit structured-outcome parser (PR #47 hardening).

The parser must never raise on file *content*: valid junit yields counts, malformed junit yields
a digest-bound ``parse_error`` record, and defused-forbidden constructs (entities/DTD/external
references — the B405/B314 hardening) yield the same graceful record. The forbidden path matters
because ``EntitiesForbidden`` is a ``ValueError`` subclass, not ``ParseError``: without its own
catch it would escape mid-receipt and the run's evidence would be lost after the subprocess
already ran.
"""

from pathlib import Path

from builder_ii.verification_execution_runner import _parse_junit_structured_outcome


def test_valid_junit_yields_structured_counts(tmp_path: Path) -> None:
    junit = tmp_path / "verification-junit.xml"
    junit.write_text(
        '<?xml version="1.0"?>'
        '<testsuites><testsuite tests="5" failures="1" errors="0" skipped="2"/></testsuites>',
        encoding="utf-8",
    )
    outcome = _parse_junit_structured_outcome(junit)
    assert outcome is not None
    assert outcome["source"] == "junit_xml"
    assert outcome["tests"] == 5
    assert outcome["passed"] == 2
    assert outcome["failed"] == 1
    assert outcome["skipped"] == 2
    assert outcome["errors"] == 0


def test_malformed_junit_degrades_to_parse_error_record(tmp_path: Path) -> None:
    junit = tmp_path / "verification-junit.xml"
    junit.write_text("<testsuite tests=", encoding="utf-8")
    outcome = _parse_junit_structured_outcome(junit)
    assert outcome is not None
    assert outcome["parse_error"] == "invalid junit xml"
    assert len(outcome["sha256"]) == 64


def test_forbidden_xml_construct_refused_without_raising(tmp_path: Path) -> None:
    junit = tmp_path / "verification-junit.xml"
    junit.write_text(
        '<?xml version="1.0"?>'
        '<!DOCTYPE testsuite [<!ENTITY x "y">]>'
        '<testsuite tests="1">&x;</testsuite>',
        encoding="utf-8",
    )
    outcome = _parse_junit_structured_outcome(junit)  # must not raise: this is the receipt path
    assert outcome is not None
    assert "forbidden xml construct" in outcome["parse_error"]
    assert len(outcome["sha256"]) == 64


def test_missing_junit_file_returns_none(tmp_path: Path) -> None:
    assert _parse_junit_structured_outcome(tmp_path / "absent.xml") is None
