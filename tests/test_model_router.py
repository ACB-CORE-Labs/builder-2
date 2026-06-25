from builder_ii.model_router import classify_task, choose_model_alias, plan_session, tier_for_mode


def test_quick_mode_uses_fast_tier_and_phi_alias():
    plan = plan_session("quick")
    assert plan.model_tier == "fast"
    assert plan.model_alias == "phi-reasoning"


def test_deep_mode_uses_primary_qwen_alias():
    plan = plan_session("deep")
    assert plan.model_tier == "primary"
    assert plan.model_alias == "qwen-coder"


def test_classify_write_as_primary_triple():
    tier, confidence, rationale = classify_task("write a new test for versor")
    assert tier == "primary"
    assert confidence == "high"
    assert "qwen-coder" in rationale


def test_classify_explain_as_fast_triple():
    tier, confidence, rationale = classify_task("explain what versor_apply does")
    assert tier == "fast"
    assert confidence == "high"
    assert "phi-reasoning" in rationale


def test_logic_review_prefers_phi_when_not_implementation():
    tier, alias, confidence, rationale = choose_model_alias("audit the versor_condition invariant")
    assert tier == "fast"
    assert alias == "phi-reasoning"
    assert confidence == "high"
    assert "versor" in rationale


def test_heavy_hint_does_not_auto_select_heavy_model():
    tier, alias, _confidence, rationale = choose_model_alias("deep refactor the whole repo call graph")
    assert tier == "primary"
    assert alias == "qwen-coder"
    assert "explicit opt-in" in rationale


def test_tier_for_mode_preserved():
    assert tier_for_mode("quick") == "fast"
    assert tier_for_mode("deep") == "primary"
