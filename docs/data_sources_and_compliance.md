# Data Sources & Compliance

This project only uses sources with a public API or feed intended for this
purpose (see `docs/decisions.md` ADR-001).

| Source | Access | Notes |
|---|---|---|
| RemoteOK | Public JSON API | May require attribution; no key needed |
| Remotive | Public API | Category and location filters available |
| Himalayas | API / feed | Structured location fields aid eligibility detection |
| JSearch (RapidAPI) | Aggregator API | Small free quota (200 req/month on the current plan); quota-aware (ADR-021) |

## Why not LinkedIn

LinkedIn has no public job-search API for individual developers, and
scraping it conflicts with its User Agreement and risks account
restrictions. Datacenter IPs (including GitHub Actions runners) are also
blocked quickly. Coverage of LinkedIn-originated postings comes indirectly
through JSearch, which aggregates from Google for Jobs; the originating
portal is recorded in `origin_portal`, separate from `source`.

## Why Selenium/Glints is out of the default pipeline

Regional scraping (Glints, Jobstreet) is kept out of the scheduled run
(ADR-022): it adds build overhead, is fragile, and needs its own terms-of-
service review. The extractor exists as a disabled stub under
`src/rjp/extract/experimental/glints.py` for future, deliberate enablement.

## Retention and reprocessing

Raw payloads are kept in R2 exactly as received, partitioned by date, and
are never filtered before storage (ADR-002). Rules can change and data can
be reprocessed with `scripts/reprocess_from_r2.py` without calling any
source API again.
