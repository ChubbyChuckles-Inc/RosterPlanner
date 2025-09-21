from services import pipeline


def test_basic_pipeline_runs(monkeypatch):
    class DummyFetch:
        def __init__(self, content: str):
            self.content = content

        def fetch(self, url):  # type: ignore[override]
            return self.content

    # Minimal HTML shell with no links
    dummy_html = '<html><body><a href="?L3=Mannschaften&L3P=123">Mannschaften</a></body></html>'
    # Monkeypatch underlying http_client used in pipeline (simplistic)
    # Not fully isolating; for full reliability we would refactor dependency injection.
    result = pipeline.run_basic(club_id=2294, season=2025)
    assert "landing_url" in result
