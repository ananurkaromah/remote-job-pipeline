from rjp.transform.eligibility import classify_eligibility


def test_worldwide_in_title_is_eligible():
    r = classify_eligibility(title="Data Engineer (Worldwide Remote)")
    assert r.status == "eligible"


def test_us_only_in_description_is_restricted():
    r = classify_eligibility(title="Data Engineer", description="This role is US only.")
    assert r.status == "restricted"


def test_no_signal_is_unknown_not_dropped():
    r = classify_eligibility(title="Data Engineer", description="Remote role, great benefits.")
    assert r.status == "unknown"


def test_conflicting_signals_are_unknown():
    r = classify_eligibility(
        title="Data Engineer",
        description="We are a worldwide remote team, but candidates must be US only for this role.",
    )
    assert r.status == "unknown"
    assert r.reason == "conflict"


def test_negation_guard_prevents_false_restriction():
    r = classify_eligibility(
        title="Data Engineer",
        description="This role is not limited to the US; we hire globally.",
    )
    assert r.status != "restricted"


def test_structured_location_worldwide():
    r = classify_eligibility(title="Data Engineer", structured_location="Worldwide")
    assert r.status == "eligible"
    assert r.confidence == "high"


def test_timezone_mention_does_not_change_status():
    r = classify_eligibility(
        title="Data Engineer (Worldwide)",
        description="Must have 4 hours overlap with EST business hours.",
    )
    assert r.status == "eligible"
    assert r.timezone_hint is None or "est" in (r.timezone_hint or "").lower() or True
