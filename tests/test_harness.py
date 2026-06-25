from builder_ii.harness import parse_pytest_summary


def test_parse_pass_summary():
    output = "....\n5 passed in 1.2s"
    passed, line, elapsed = parse_pytest_summary(output)
    assert passed
    assert "passed" in (line or "")
    assert elapsed == 1.2


def test_parse_fail_summary():
    output = "F\n1 failed, 4 passed in 2s"
    passed, line, elapsed = parse_pytest_summary(output)
    assert not passed
    assert "failed" in (line or "")
    assert elapsed is None
