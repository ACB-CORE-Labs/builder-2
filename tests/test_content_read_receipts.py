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


def test_content_read_redacts_secrets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    secret_file = repo / "config.txt"
    secret_file.write_text("api_key = 'supersecretvalue123456'", encoding="utf-8")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["config.txt"])
    receipt = execute_content_read(policy, secret_file)
    assert receipt["kind"] == CONTENT_READ_RECEIPT_KIND
    assert "[REDACTED]" in receipt["redacted_excerpt"]


def test_content_read_denies_huge_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    big = repo / "big.txt"
    big.write_text("x" * 5000, encoding="utf-8")
    policy = create_read_policy(target_name="generic", target_repo=repo, allowed_paths=["big.txt"])
    receipt = execute_content_read(policy, big, max_bytes_per_file=100)
    assert receipt["kind"] == DENIED_READ_KIND