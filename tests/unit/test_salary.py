from rjp.transform.salary import parse_salary


def test_disclosed_range():
    r = parse_salary("We offer a competitive salary of $80,000 - $100,000 per year.")
    assert r.status == "disclosed"
    assert r.min_usd == 80000
    assert r.max_usd == 100000


def test_not_disclosed_when_no_salary_text():
    r = parse_salary("Join our amazing team and build great products.")
    assert r.status == "not_disclosed"


def test_corporate_does_not_trigger_rate_keyword():
    # "rate" inside "Corporate" must not be treated as a salary keyword (word boundary).
    r = parse_salary("Join our Corporate team, based in a modern 100 - 200 person office.")
    assert r.status == "not_disclosed"


def test_partial_up_to():
    r = parse_salary("Compensation: up to $120,000 per year depending on experience.")
    assert r.status == "partial"
    assert r.max_usd == 120000


def test_partial_from():
    r = parse_salary("Salary starting at $70,000 annually.")
    assert r.status == "partial"
    assert r.min_usd == 70000


def test_k_suffix_parsed():
    r = parse_salary("Salary range: $80k - $100k per year.")
    assert r.status == "disclosed"
    assert r.min_usd == 80000
    assert r.max_usd == 100000
