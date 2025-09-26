from gui.ingestion.caching_inspector import diff_provenance


def test_diff_provenance_basic_classification():
    current = {
        "a.html": "sha1a",
        "b.html": "sha1bNEW",  # changed vs provenance
        "c.html": "sha1c",  # new file
    }
    provenance = {
        "a.html": "sha1a",  # unchanged
        "b.html": "sha1bOLD",  # updated
        "old.html": "sha1old",  # missing now
    }
    diff = diff_provenance(current, provenance)
    assert diff.unchanged == ["a.html"]
    assert diff.updated == ["b.html"]
    assert diff.new == ["c.html"]
    assert diff.missing == ["old.html"]
    # Summary includes all categories counts
    summary = diff.summary()
    for token in ["Updated", "Unchanged", "New", "Missing"]:
        assert token in summary
