from builder_ii.compliance import check_init_artifact, refusal_response_for, run_compliance_checks
from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT


def test_init_literals_present():
    ok, missing = check_init_artifact(CORE_INIT_SYSTEM_PROMPT)
    assert ok, missing


def test_cosine_vault_refusal_under_core():
    msg = refusal_response_for("add cosine similarity to vault/store.py for speed", target_profile="core")
    assert msg is not None
    assert "versor_condition" in msg
    assert "cga_inner" in msg


def test_cosine_vault_bypass_under_generic():
    msg = refusal_response_for("add cosine similarity to vault/store.py for speed", target_profile="generic")
    assert msg is None


def test_cosine_vault_bypass_under_builder():
    msg = refusal_response_for("add cosine similarity to vault/store.py for speed", target_profile="builder")
    assert msg is None


def test_false_positive_cosine_without_vault_context():
    # Cosine mentioned but vault is not in text -> should not refuse
    msg = refusal_response_for("The cosine of the angle is 0.5", target_profile="core")
    assert msg is None


def test_case_insensitive_matching():
    msg1 = refusal_response_for("ADD COSINE SIMILARITY TO VAULT/STORE.PY FOR SPEED", target_profile="core")
    assert msg1 is not None
    assert "versor_condition" in msg1

    msg2 = refusal_response_for("hnsw index in search", target_profile="core")
    assert msg2 is not None

    msg3 = refusal_response_for("HNSW index in search", target_profile="core")
    assert msg3 is not None


def test_compliance_report_passes():
    report = run_compliance_checks()
    assert report.init_literals_ok
    assert report.refusal_probe_ok
