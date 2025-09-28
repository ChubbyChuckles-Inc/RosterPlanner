from gui.ingestion.selector_watchlist_store import SelectorWatchEntry, SelectorWatchlistStore


def test_watchlist_store_roundtrip(tmp_path):
    path = tmp_path / "watch.json"
    store = SelectorWatchlistStore(str(path))
    assert store.entries() == []

    entry = SelectorWatchEntry(
        resource="roster",
        target_type="field",
        target_name="name",
        baseline_count=5,
        last_count=4,
        threshold_percent=40,
    )
    store.upsert(entry)
    store.save()

    reloaded = SelectorWatchlistStore(str(path))
    entries = reloaded.entries()
    assert len(entries) == 1
    loaded = entries[0]
    assert loaded.resource == "roster"
    assert loaded.target_type == "field"
    assert loaded.target_name == "name"
    assert loaded.baseline_count == 5
    assert loaded.last_count == 4
    assert loaded.threshold_percent == 40

    reloaded.remove(loaded.identifier())
    assert reloaded.entries() == []
