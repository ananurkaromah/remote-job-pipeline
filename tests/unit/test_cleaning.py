from rjp.transform.cleaning import clean_description, strip_html


def test_strips_tags():
    assert strip_html("<p>Hello <b>World</b></p>") == "Hello World\n\n"


def test_decodes_entities():
    assert "&" in strip_html("Tom &amp; Jerry")


def test_clean_description_normalizes_whitespace():
    raw = "<p>Line one</p><p>Line   two</p>"
    result = clean_description(raw)
    assert "Line one" in result
    assert "Line two" in result
    assert "   " not in result
