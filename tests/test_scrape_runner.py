from gui.services.scrape_runner import ScrapeRunner


class DummyPipeline:
    def __init__(self, should_fail: bool = False):
        self.calls = 0
        self.should_fail = should_fail

    def __call__(self, club_id: int, season=None, data_dir=None):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("boom")
        return {"ok": True, "club": club_id, "season": season, "data_dir": data_dir}


def test_scrape_runner_success(qtbot):  # qtbot fixture if available; else acts as smoke
    dummy = DummyPipeline()
    runner = ScrapeRunner(pipeline_func=dummy)
    results = {}

    def on_finished(res):
        results.update(res)

    runner.scrape_finished.connect(on_finished)  # type: ignore
    runner.start(1234, 2025, "./tmp-data")
    runner._worker.wait()  # wait for thread completion
    assert results["ok"] is True
    assert dummy.calls == 1


def test_scrape_runner_failure(qtbot):
    dummy = DummyPipeline(should_fail=True)
    runner = ScrapeRunner(pipeline_func=dummy)
    failed = {"msg": None}

    def on_failed(msg: str):
        failed["msg"] = msg

    runner.scrape_failed.connect(on_failed)  # type: ignore
    runner.start(1234, 2025, "./tmp-data")
    runner._worker.wait()
    assert failed["msg"] == "boom"
