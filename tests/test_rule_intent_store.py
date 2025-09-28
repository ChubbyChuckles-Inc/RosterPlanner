import json

from gui.ingestion.rule_intent_store import RuleIntentStore, RuleIntent


def test_rule_intent_store_roundtrip(tmp_path):
    path = tmp_path / "intents.json"
    store = RuleIntentStore(str(path))
    store.set(
        "players",
        RuleIntent(purpose="  Extract roster  ", assumptions="source has stable layout", todo="  "),
    )
    store.save()
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["resources"]["players"]["purpose"] == "Extract roster"
    assert payload["resources"]["players"]["assumptions"] == "source has stable layout"
    assert payload["resources"]["players"]["todo"] == ""

    reloaded = RuleIntentStore(str(path))
    intent = reloaded.get("players")
    assert intent.purpose == "Extract roster"
    assert intent.assumptions == "source has stable layout"
    assert intent.todo == ""


def test_rule_intent_store_remove_when_empty(tmp_path):
    path = tmp_path / "intents.json"
    path.write_text(
        json.dumps(
            {"resources": {"players": {"purpose": "Initial", "assumptions": "", "todo": ""}}}
        ),
        encoding="utf-8",
    )
    store = RuleIntentStore(str(path))
    assert "players" in store.resources()

    store.set("players", RuleIntent(purpose="   ", assumptions="  ", todo=""))
    store.save()

    assert store.resources() == {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["resources"] == {}


def test_rule_intent_store_graceful_on_invalid_json(tmp_path):
    path = tmp_path / "intents.json"
    path.write_text("not-json", encoding="utf-8")
    store = RuleIntentStore(str(path))
    assert store.resources() == {}
