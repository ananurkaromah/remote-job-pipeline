from rjp.transform.dedup import deduplicate, is_duplicate


def _job(job_id, source, company_norm, title_norm, canonical_url="", description_clean="", **kw):
    base = {
        "job_id": job_id, "source": source, "company_norm": company_norm,
        "title_norm": title_norm, "canonical_url": canonical_url,
        "description_clean": description_clean, "posted_at": None,
    }
    base.update(kw)
    return base


def test_same_url_is_duplicate():
    a = _job("a", "remoteok", "acme", "data engineer", canonical_url="https://x.com/1")
    b = _job("b", "remotive", "acme", "data engineer", canonical_url="https://x.com/1")
    assert is_duplicate(a, b)


def test_same_title_different_region_not_merged():
    desc_us = "This role is US only. " * 20
    desc_id = "This role is worldwide remote. " * 20
    a = _job("a", "remoteok", "acme", "data engineer", description_clean=desc_us)
    b = _job("b", "remotive", "acme", "data engineer", description_clean=desc_id)
    assert not is_duplicate(a, b)


def test_deduplicate_keeps_most_complete():
    desc_common = "We are looking for a data engineer to join our growing team building pipelines. "
    a = _job("a", "jsearch", "acme", "data engineer", description_clean=desc_common, salary_status="not_disclosed")
    b = _job(
        "b", "himalayas", "acme", "data engineer",
        description_clean=desc_common * 20, salary_status="disclosed",
        eligibility_status="eligible", location_raw="Worldwide", tech_stack=["Python", "SQL"],
    )
    winners, losers = deduplicate([a, b])
    assert len(winners) == 1
    assert winners[0]["job_id"] == "b"
    assert losers[0]["job_id"] == "a"
    assert losers[0]["duplicate_of"] == "b"


def test_deduplicate_is_deterministic():
    a = _job("a", "remoteok", "acme", "data engineer")
    b = _job("b", "remoteok", "beta", "etl developer")
    winners1, _ = deduplicate([a, b])
    winners2, _ = deduplicate([b, a])
    assert {w["job_id"] for w in winners1} == {w["job_id"] for w in winners2}
