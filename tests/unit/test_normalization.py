from rjp.transform.normalization import canonical_url, normalize_company, normalize_title


def test_normalize_title_strips_remote_annotation():
    assert normalize_title("Data Engineer (Remote, US)") == "data engineer"


def test_normalize_title_expands_sr_jr():
    assert "senior" in normalize_title("Sr. Data Engineer")
    assert "junior" in normalize_title("Jr Data Engineer")


def test_normalize_company_strips_suffix():
    assert normalize_company("Acme Inc.") == normalize_company("Acme")


def test_canonical_url_strips_tracking_params():
    a = canonical_url("https://example.com/job/123?utm_source=x&ref=y")
    b = canonical_url("https://example.com/job/123")
    assert a == b


def test_canonical_url_strips_trailing_slash():
    assert canonical_url("https://example.com/job/123/") == canonical_url("https://example.com/job/123")
