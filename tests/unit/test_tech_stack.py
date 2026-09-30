from rjp.transform.tech_stack import extract_tech_stack


def test_extracts_known_technologies():
    result = extract_tech_stack("We use Python, SQL, Airflow and Spark daily.")
    assert set(result) == {"Python", "SQL", "Airflow", "Spark"}


def test_no_false_positive_on_substring():
    # "java" should not match inside "javascript" incorrectly, and vice versa.
    result = extract_tech_stack("We use JavaScript for the frontend.")
    assert "Java" not in result


def test_case_insensitive():
    result = extract_tech_stack("PYTHON and airflow")
    assert "Python" in result
    assert "Airflow" in result
