from gui.ingestion.prompt_rule_assist import generate_rule_draft, ruleset_to_mapping

def test_generate_rule_draft_empty():
    draft = generate_rule_draft("")
    mapping = ruleset_to_mapping(draft.ruleset)
    assert "items" in mapping["resources"]
    assert draft.explanation and "empty" in draft.explanation[0].lower()


def test_generate_rule_draft_player_rating():
    prompt = "Extract player names and their live rating and match count"
    draft = generate_rule_draft(prompt)
    mapping = ruleset_to_mapping(draft.ruleset)
    assert "players" in mapping["resources"]  # resource name derived
    res = mapping["resources"]["players"]
    fields = res["fields"]
    # Ensure canonical fields present
    assert "player_name" in fields
    assert "live_rating" in fields
    assert "match_count" in fields
    # Explanation should mention tokens
    joined = " ".join(draft.explanation).lower()
    assert "player" in joined and "rating" in joined
