"""Tests for draft autosave snapshot history management."""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from gui.views.ingestion_lab import drafts
from gui.views.ingestion_lab.drafts import DraftSnapshot, DraftingMixin


class _DummyEditor:
    def __init__(self) -> None:
        self._text = ""

    def set_text(self, text: str) -> None:
        self._text = text

    def toPlainText(self) -> str:  # noqa: N802 - Qt compatibility
        return self._text


class _DraftHarness(DraftingMixin):
    def __init__(self, root: Path, max_entries: int = 5) -> None:
        self.rule_editor = _DummyEditor()
        self._draft_path = str(root / ".ingestion_rules_draft.json")
        self._draft_history_path = str(root / ".ingestion_rules_draft_history.json")
        self._draft_history_max_entries = max_entries
        self._draft_dirty = True
        self._log_messages: List[str] = []
        self._timeline_refresh_invocations = 0

    def _append_log(
        self, message: str
    ) -> None:  # pragma: no cover - behavior asserted via side effects
        self._log_messages.append(message)

    def _timeline_refresh_snapshots(self) -> None:
        self._timeline_refresh_invocations += 1


@pytest.fixture
def harness(tmp_path: Path) -> _DraftHarness:
    return _DraftHarness(tmp_path)


def test_autosave_history_keeps_last_five_entries(
    harness: _DraftHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter(range(1_700_000_000, 1_700_000_000 + 40))
    monkeypatch.setattr(drafts.time, "time", lambda: next(times))

    texts = [f'{{"value": {idx}}}' for idx in range(7)]
    for text in texts:
        harness.rule_editor.set_text(text)
        harness._draft_dirty = True
        harness._autosave_draft()

    snapshots = harness._get_recent_draft_snapshots()
    assert len(snapshots) == 5
    snapshot_texts = [snap.text for snap in snapshots]
    expected = list(reversed(texts[-5:]))
    assert snapshot_texts == expected
    assert all(isinstance(snap, DraftSnapshot) for snap in snapshots)
    # Ensure history refresh hook invoked for each autosave attempt
    assert harness._timeline_refresh_invocations == len(texts)


def test_autosave_history_deduplicates_consecutive_matches(
    harness: _DraftHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter(range(2_100_000_000, 2_100_000_000 + 20))
    monkeypatch.setattr(drafts.time, "time", lambda: next(times))

    repeated_text = '{"shared": 1}'
    harness.rule_editor.set_text(repeated_text)
    harness._draft_dirty = True
    harness._autosave_draft()
    first_snapshot = harness._get_recent_draft_snapshots()[0]

    harness.rule_editor.set_text(repeated_text)
    harness._draft_dirty = True
    harness._autosave_draft()

    snapshots = harness._get_recent_draft_snapshots()
    assert len(snapshots) == 1
    # Timestamp should update to the most recent autosave even when content is identical
    assert snapshots[0].timestamp > first_snapshot.timestamp
    assert snapshots[0].text == repeated_text
    assert harness._timeline_refresh_invocations == 2
