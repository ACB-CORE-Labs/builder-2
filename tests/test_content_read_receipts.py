import json
from pathlib import Path

from builder_ii.readonly_authority import (
    CONTENT_READ_RECEIPT_KIND,
    DENIED_READ_KIND,
    create_read_policy,
    execute_content_read,
    validate_content_read_receipt,
)


def test_content_read_success_and_digest_stability(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "hello.txt"
    target.write_text("hello governed content", encoding="utf-8")

    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["hello.txt"],
    )
    receipt1 = execute_content_read(policy, target)
    receipt2 = execute_content_read(policy, target)
    assert receipt1["kind"] == CONTENT_READ_RECEIPT_KIND
    assert receipt1["content_digest"] == receipt2["content_digest"]
    assert not validate_content_read_receipt(receipt1)


def test_content_read_denies_path_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["inside.txt"])
    receipt = execute_content_read(policy, outside)
    assert receipt["kind"] == DENIED_READ_KIND


def test_content_read_denies_secrets_and_never_persists_their_value(tmp_path: Path) -> None:
    """The lane refuses a secret-bearing file; the old form substituted the keyword and left the
    VALUE verbatim in the excerpt. The keyword-less cases (a token, an AWS key, a PEM body) are the
    ones the substitution form missed entirely -- they carry no keyword to replace."""
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["config.txt"])

    cases = [
        ("api_key = 'supersecretvalue123456'", "supersecretvalue123456"),
        ("token=ghp_0123456789abcdefghijABCDEFGHIJ0123", "ghp_0123456789abcdefghijABCDEFGHIJ0123"),
        ("aws = AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEbody\n-----END RSA PRIVATE KEY-----", "MIIEbody"),
    ]
    for content, secret_value in cases:
        secret_file = repo / "config.txt"
        secret_file.write_text(content, encoding="utf-8")
        receipt = execute_content_read(policy, secret_file)
        assert receipt["kind"] == DENIED_READ_KIND, f"secret-bearing file must be denied: {content!r}"
        # The whole point: the secret value appears in NO field of the receipt.
        assert secret_value not in json.dumps(receipt), f"secret value leaked into the receipt: {secret_value!r}"


def test_content_read_captures_a_clean_file(tmp_path: Path) -> None:
    """A file with no secret pattern still yields a content receipt with a real excerpt."""
    repo = tmp_path / "repo"
    repo.mkdir()
    clean = repo / "notes.txt"
    clean.write_text("ordinary project notes, nothing sensitive here", encoding="utf-8")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["notes.txt"])
    receipt = execute_content_read(policy, clean)
    assert receipt["kind"] == CONTENT_READ_RECEIPT_KIND
    assert "ordinary project notes" in receipt["redacted_excerpt"]


def test_content_read_denies_symlink(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    real = repo / "real.txt"
    real.write_text("real content", encoding="utf-8")
    link = repo / "link.txt"
    link.symlink_to(real)
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["link.txt"])
    receipt = execute_content_read(policy, link)
    assert receipt["kind"] == DENIED_READ_KIND
    assert "Symlink" in receipt["reason"]


def test_content_read_binary_digest_only_mode(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    binary = repo / "data.bin"
    binary.write_bytes(b"hello\x00world")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["data.bin"])
    receipt = execute_content_read(policy, binary)
    assert receipt["kind"] == CONTENT_READ_RECEIPT_KIND
    assert receipt["binary_digest_only"] is True
    assert receipt["redacted_excerpt"] == ""


def test_content_read_denies_huge_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    big = repo / "big.txt"
    big.write_text("x" * 5000, encoding="utf-8")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["big.txt"])
    receipt = execute_content_read(policy, big, max_bytes_per_file=100)
    assert receipt["kind"] == DENIED_READ_KIND
