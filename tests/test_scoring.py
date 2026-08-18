from types import SimpleNamespace

from career_scout.scoring import score_job


PROFILE = {
    "core_deep": {"delivery": ["Program Management", "Stakeholder Management", "Strategy-to-execution"]},
    "strong_direct": {"digital": ["Digital transformation", "eCommerce platforms", "SaaS implementation"]},
    "ai_agentic_technology": {"hands_on": ["AI agents", "OpenAI"]},
    "delivery_methods": ["Agile", "Scrum"],
    "target_role_families": {"program": ["Program Manager", "Transformation Director"]},
}


def job(title, description, hybrid=True):
    return SimpleNamespace(title=title, teaser="", description=description, is_hybrid=hybrid, is_remote=False)


def test_good_program_role_scores_without_hard_gap():
    result = score_job(job("Program Manager", "Lead digital transformation, Agile delivery, stakeholder management and strategy-to-execution."), PROFILE, {})
    assert not result.hard_gaps
    assert result.score >= 50


def test_mandatory_bss_oss_is_hard_gap():
    result = score_job(job("Program Director", "Must have deep BSS/OSS expertise for telecommunications transformation."), PROFILE, {})
    assert "BSS/OSS specialist experience" in result.hard_gaps
    assert result.verdict == "SKIP"


def test_existing_baseline_is_hard_gap():
    result = score_job(job("Program Manager", "Applicants must hold a current Baseline clearance."), PROFILE, {})
    assert "existing security clearance" in result.hard_gaps
    assert result.verdict == "SKIP"
