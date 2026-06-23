from core_agent.compliance import check_init_artifact, refusal_response_for, run_compliance_checks
from core_agent.init_content import CORE_INIT_SYSTEM_PROMPT


def test_init_literals_present():
    ok, missing = check_init_artifact(CORE_INIT_SYSTEM_PROMPT)
    assert ok, missing


def test_cosine_vault_refusal():
    msg = refusal_response_for("add cosine similarity to vault/store.py for speed")
    assert msg is not None
    assert "versor_condition" in msg
    assert "cga_inner" in msg


def test_compliance_report_passes():
    report = run_compliance_checks()
    assert report.init_literals_ok
    assert report.refusal_probe_ok