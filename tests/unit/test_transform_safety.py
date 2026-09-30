from rjp.transform.pipeline import transform_all


def test_none_job_does_not_crash_the_loop():
    kept, rejected, skipped = transform_all([None])
    assert skipped == 1  # None raised inside transform_one, caught by the generic except
    assert len(kept) == 0


def test_mixed_valid_and_invalid_jobs():
    valid = {
        "title": "Data Engineer", "company": "Acme", "description": "Worldwide remote role.",
        "url": "https://example.com/1", "source": "remoteok", "posted_at": None,
    }
    jobs = [None, "not a dict either", valid]
    kept, rejected, skipped = transform_all(jobs)
    assert skipped == 2  # neither None nor a plain string has .get(); both are caught safely
    assert len(kept) == 1
    assert kept[0]["title"] == "Data Engineer"
