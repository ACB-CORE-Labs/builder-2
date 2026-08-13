from __future__ import annotations

import subprocess

from builder_ii.core.repository_identity import check_repository_identity


def test_repository_identity_matches_git_remote(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, "https://github.com/ACB-CORE-Labs/builder-2.git\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = check_repository_identity()
    assert report.matches is True
    assert report.error is None
    assert report.as_dict()["governance"]["artifact_is_authority"] is False


def test_repository_identity_fails_closed_on_wrong_remote(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, "https://example.invalid/other.git\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = check_repository_identity()
    assert report.matches is False
    assert report.error == "configured remote does not match the canonical repository"


def test_repository_identity_fails_closed_when_remote_is_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    report = check_repository_identity(remote_name="upstream")
    assert report.matches is False
    assert "not configured" in (report.error or "")
