import pytest

from rjp.transform.role_filter import classify


@pytest.mark.parametrize("title", [
    "Senior Data Engineer",
    "Sr. ETL Developer",
    "Lead Data Engineer",
    "Staff Data Engineer",
])
def test_senior_titles_dropped(title):
    d = classify(title, "")
    assert d.keep is False
    assert d.reason == "dropped:senior_title"


def test_management_title_excluded_as_non_de_role():
    # "manager" titles are excluded at the role-family stage (not a DE/ETL role),
    # so the reported reason is the role exclusion, not the seniority check.
    d = classify("Data Engineering Manager", "")
    assert d.keep is False
    assert d.reason == "dropped:not_data_engineering_role"


@pytest.mark.parametrize("title", [
    "Junior Data Engineer",
    "Data Engineer, Entry Level",
    "Associate Data Engineer",
])
def test_junior_titles_kept(title):
    d = classify(title, "3+ years required")  # junior title keyword wins regardless of years text
    assert d.keep is True
    assert d.seniority == "junior"


@pytest.mark.parametrize("desc,expected_keep", [
    ("3+ years of experience required.", False),
    ("2-3 years of experience required.", True),
    ("3-5 years of experience.", False),
    ("up to 3 years of experience.", True),          # ceiling, not a minimum
    ("less than 3 years experience needed.", True),  # ceiling
    ("at least 1 year, 3+ years preferred.", True),  # preferred is not required
    ("5 years Spark, 1 year Airflow.", False),        # largest lower bound wins
    ("three years of experience.", False),            # spelled-out number
    ("No specific years mentioned.", True),           # unknown, kept
])
def test_years_cutoff_on_neutral_title(desc, expected_keep):
    d = classify("Data Engineer", desc)
    assert d.keep is expected_keep, d.reason


def test_senior_keyword_in_description_does_not_trigger_drop():
    # "senior stakeholders" in the description must not be read as a senior title.
    d = classify("Data Engineer", "You will work with senior stakeholders across the org.")
    assert d.keep is True


def test_non_data_engineering_role_excluded():
    d = classify("Data Scientist", "")
    assert d.keep is False
    assert d.reason == "dropped:not_data_engineering_role"


def test_adjacent_role_kept():
    d = classify("Analytics Engineer", "")
    assert d.keep is True
    assert d.role_match == "adjacent"
