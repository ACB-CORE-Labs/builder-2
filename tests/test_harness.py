from core_agent.harness import parse_pytest_summary


def test_parse_pass_summary():
    output = "....\n5 passed in 1.2s"
    passed, line = parse_pytest_summary(output)
    assert passed
    assert "passed" in (line or "")


def test_parse_fail_summary():
    output = "F\n1 failed, 4 passed in 2s"
    passed, line = parse_pytest_summary(output)
    assert not passed