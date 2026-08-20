from career_scout.role_state import apply_transition, mark_verified_expired, should_suppress_as_new


def ledger():
    return {
        "statuses": ["NEW", "SHORTLISTED", "CV_CREATED", "APPLIED", "INTERVIEW", "REJECTED", "CLOSED", "EXPIRED"],
        "allowed_transitions": {
            "NEW": ["SHORTLISTED", "REJECTED", "EXPIRED"],
            "SHORTLISTED": ["CV_CREATED", "APPLIED", "REJECTED", "EXPIRED"],
            "CV_CREATED": ["APPLIED", "REJECTED", "EXPIRED"],
            "APPLIED": ["INTERVIEW", "REJECTED", "CLOSED", "EXPIRED"],
            "INTERVIEW": ["REJECTED", "CLOSED"],
            "REJECTED": [], "CLOSED": [], "EXPIRED": [],
        },
        "suppress_as_new": ["SHORTLISTED", "CV_CREATED", "APPLIED", "INTERVIEW", "REJECTED", "CLOSED", "EXPIRED"],
        "roles": {},
    }


def test_normal_funnel_transition_and_suppression():
    data = ledger()
    assert apply_transition(data, "seek", "123", "SHORTLISTED", title="Program Manager")
    assert should_suppress_as_new(data, "seek", "123")
    assert apply_transition(data, "seek", "123", "CV_CREATED")
    assert apply_transition(data, "seek", "123", "APPLIED")
    assert apply_transition(data, "seek", "123", "INTERVIEW")


def test_does_not_regress_without_explicit_override():
    data = ledger()
    apply_transition(data, "seek", "123", "SHORTLISTED")
    apply_transition(data, "seek", "123", "APPLIED")
    assert not apply_transition(data, "seek", "123", "CV_CREATED")
    assert data["roles"]["seek:123"]["status"] == "APPLIED"


def test_verified_expiry_does_not_overwrite_active_application():
    data = ledger()
    apply_transition(data, "seek", "123", "SHORTLISTED")
    apply_transition(data, "seek", "123", "APPLIED")
    assert not mark_verified_expired(data, "seek", "123")
    assert data["roles"]["seek:123"]["status"] == "APPLIED"


def test_verified_expiry_closes_pre_application_role():
    data = ledger()
    apply_transition(data, "seek", "123", "SHORTLISTED")
    assert mark_verified_expired(data, "seek", "123")
    assert data["roles"]["seek:123"]["status"] == "EXPIRED"
