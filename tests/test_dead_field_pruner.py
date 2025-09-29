from typing import Dict, List

from gui.ingestion.dead_field_pruner import (
    DeadFieldAction,
    DeadFieldHistory,
    DeadFieldObservation,
    FieldUsageSample,
    apply_dead_field_actions,
    compute_dead_field_suggestions,
)


def _make_observation(
    file_label: str, samples: List[FieldUsageSample], ts: float = 0.0
) -> DeadFieldObservation:
    return DeadFieldObservation(file_label=file_label, timestamp=ts, samples=samples)


def test_dead_field_pruner_detects_zero_fields():
    history = DeadFieldHistory(capacity=3)
    history.record(
        _make_observation(
            "file1.html",
            [
                FieldUsageSample("players", "name", "list", non_empty=2, total=2),
                FieldUsageSample("players", "rating", "list", non_empty=0, total=2),
            ],
            ts=1.0,
        )
    )
    history.record(
        _make_observation(
            "file2.html",
            [
                FieldUsageSample("players", "name", "list", non_empty=1, total=1),
                FieldUsageSample("players", "rating", "list", non_empty=0, total=1),
            ],
            ts=2.0,
        )
    )

    suggestions = compute_dead_field_suggestions(history, window=2)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.resource == "players"
    assert suggestion.field == "rating"
    assert suggestion.preview_count() == 2
    assert suggestion.evidence_count() == 2
    assert suggestion.reason().startswith("0 populated values")


def test_dead_field_pruner_requires_evidence():
    history = DeadFieldHistory(capacity=3)
    # Two previews but only one has rows for field `notes`
    history.record(
        _make_observation(
            "file1.html",
            [
                FieldUsageSample("players", "notes", "list", non_empty=0, total=0),
            ],
            ts=1.0,
        )
    )
    history.record(
        _make_observation(
            "file2.html",
            [
                FieldUsageSample("players", "notes", "list", non_empty=1, total=2),
            ],
            ts=2.0,
        )
    )

    suggestions = compute_dead_field_suggestions(history, window=2)

    assert suggestions == []


def test_apply_dead_field_actions_handles_comment_and_delete():
    rules_doc: Dict[str, object] = {
        "resources": {
            "players": {
                "kind": "list",
                "selector": "div.player",
                "item_selector": "div.row",
                "fields": {
                    "name": {"selector": ".name"},
                    "rating": {"selector": ".rating"},
                    "club": {"selector": ".club"},
                },
            }
        }
    }

    comment_action = DeadFieldAction(resource="players", field="rating", mode="comment")
    delete_action = DeadFieldAction(resource="players", field="club", mode="delete")

    commented, deleted = apply_dead_field_actions(rules_doc, [comment_action, delete_action])

    assert (commented, deleted) == (1, 1)
    resources = rules_doc["resources"]  # type: ignore[index]
    players = resources["players"]  # type: ignore[index]
    fields = players["fields"]  # type: ignore[index]
    assert "rating" not in fields
    assert "club" not in fields
    inactive = rules_doc.get("inactive_fields")
    assert isinstance(inactive, dict)
    assert inactive["players"]["rating"] == {"selector": ".rating"}


def test_dead_field_history_respects_capacity():
    history = DeadFieldHistory(capacity=2)
    history.record(_make_observation("a", [], ts=1.0))
    history.record(_make_observation("b", [], ts=2.0))
    history.record(_make_observation("c", [], ts=3.0))

    recent = history.recent()
    assert len(recent) == 2
    assert recent[0].file_label == "b"
    assert recent[1].file_label == "c"
