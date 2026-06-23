from builder_ii.model_router import classify_task, plan_session, tier_for_mode


def test_quick_mode_uses_fast_tier():
    plan = plan_session("quick")
    assert plan.model_tier == "fast"


def test_deep_mode_uses_primary():
    plan = plan_session("deep")
    assert plan.model_tier == "primary"


def test_classify_write_as_primary():
    assert classify_task("write a new test for versor") == "primary"


def test_classify_explain_as_fast():
    assert classify_task("explain what versor_apply does") == "fast"