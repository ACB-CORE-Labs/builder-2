from __future__ import annotations

from typing import Any

import builder_ii.verification_runner_entrypoints as entrypoints


def test_main_dispatches_platform_status(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_platform_status", lambda: 0)
    assert entrypoints.main(["platform-status"]) == 0


def test_main_dispatches_docs_audit(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_docs_audit", lambda: 0)
    assert entrypoints.main(["docs-audit"]) == 0


def test_main_dispatches_pytest_full(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_pytest_full", lambda: 0)
    assert entrypoints.main(["pytest-full"]) == 0


def test_main_dispatches_builder_full(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_builder_full", lambda: 0)
    assert entrypoints.main(["builder-full"]) == 0


def test_main_unknown_entrypoint_returns_2() -> None:
    assert entrypoints.main(["not-a-real-entrypoint"]) == 2


def test_run_pytest_full_invokes_pytest_main_with_fixed_args(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_main(args: list[str]) -> int:
        captured["args"] = args
        return 0

    monkeypatch.setattr("pytest.main", fake_main)
    assert entrypoints.run_pytest_full() == 0
    # cache provider disabled so no `.pytest_cache` byproduct is created
    assert captured["args"] == ["-q", "-p", "no:cacheprovider"]


def test_run_builder_full_aggregates_nonzero_exit(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_pytest_full", lambda: 0)
    monkeypatch.setattr(entrypoints, "run_platform_status", lambda: 1)
    monkeypatch.setattr(entrypoints, "run_docs_audit", lambda: 0)
    assert entrypoints.run_builder_full() == 1


def test_run_builder_full_is_zero_when_all_pass(monkeypatch: Any) -> None:
    monkeypatch.setattr(entrypoints, "run_pytest_full", lambda: 0)
    monkeypatch.setattr(entrypoints, "run_platform_status", lambda: 0)
    monkeypatch.setattr(entrypoints, "run_docs_audit", lambda: 0)
    assert entrypoints.run_builder_full() == 0
