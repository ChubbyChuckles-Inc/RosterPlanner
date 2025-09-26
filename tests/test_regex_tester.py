from gui.ingestion.regex_tester import find_regex_matches
import re


def test_find_regex_matches_basic():
    text = "Team Alpha beat Team Beta 3-2 on 2025-09-21"
    pat = r"Team\s+(\w+)"
    matches = find_regex_matches(pat, text)
    assert len(matches) == 2
    assert matches[0].text == "Team Alpha"
    assert matches[0].groups == ["Alpha"]
    assert matches[1].groups == ["Beta"]


def test_find_regex_matches_flags():
    text = "one\nTWO\nThree"
    pat = r"^t(\w+)"  # should match 'TWO' in multiline ignorecase
    matches = find_regex_matches(pat, text, re.IGNORECASE | re.MULTILINE)
    # Should match TWO and Three (start of lines)
    assert len(matches) == 2
    assert matches[0].text.lower() == "two"
    assert matches[1].text.lower() == "three"


def test_find_regex_matches_invalid_pattern():
    try:
        find_regex_matches(r"(unclosed", "text")
    except ValueError as e:
        assert "Invalid regex" in str(e)
    else:  # pragma: no cover
        assert False, "Expected ValueError for invalid pattern"
