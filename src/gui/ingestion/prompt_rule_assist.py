"""Natural Language Prompt Assist (Milestone 7.10.A4).

This module provides a very lightweight, dependency‑free heuristic that converts a
natural language prompt describing desired extractions into a draft ``RuleSet``
structure composed of one or more resources (currently a single list resource).

Scope (Initial Spike / Research Output)
--------------------------------------
* Token based intent detection (no ML): looks for domain keywords such as
  "player", "rating", "match", "team", "club" and maps them to canonical
  field identifiers.
* Generates placeholder CSS selectors using predictable, conventional class
  names (e.g. ``.player``, ``.player-name``). These are intentionally
  conservative and designed to be *edited* by the user afterwards.
* Returns an explanation list describing which tokens were recognized and how
  they influenced the draft.

Non‑Goals (Deferred for later milestones)
----------------------------------------
* True NLP / LLM integration.
* Selector validation against actual HTML.
* Automatic transform chain inference.
* Multi‑resource rule inference.

Design Notes
------------
The heuristic keeps complexity *very* low to remain easily testable and to
avoid introducing external dependencies. The goal of this milestone is to
prove value / workflow: a user can type a short sentence and receive a
structured starting point instead of a blank editor.

Future Extension Ideas
----------------------
* Add pluggable token -> field mapping registry.
* Confidence scores & alternative suggestions.
* Use existing parsed HTML (if available) to attempt smart CSS selection.

"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable

from .rule_schema import RuleSet, ListRule, FieldMapping

__all__ = ["PromptRuleDraft", "generate_rule_draft"]


@dataclass
class PromptRuleDraft:
    """Container for a generated rule draft.

    Attributes
    ----------
    ruleset: RuleSet
        The generated ruleset containing one or more resources.
    explanation: list[str]
        Human readable bullet list explaining mapping decisions.
    raw_tokens: list[str]
        Lower‑cased unique tokens extracted from the prompt.
    """

    ruleset: RuleSet
    explanation: List[str]
    raw_tokens: List[str]


# Canonical mapping of token keywords -> (field_name, default_selector)
TOKEN_FIELD_MAP: Dict[str, Tuple[str, str]] = {
    "player": ("player_name", ".player-name"),
    "name": ("player_name", ".player-name"),  # assist if prompt only says "names"
    "rating": ("live_rating", ".live-rating"),
    "live": ("live_rating", ".live-rating"),  # part of "live rating" phrase
    "match": ("match_count", ".match-count"),
    "matches": ("match_count", ".match-count"),
    "team": ("team_name", ".team-name"),
    "club": ("club_name", ".club-name"),
}

# Field label preferences to avoid duplicates overriding earlier semantic picks
FIELD_PREFERENCE_ORDER = [
    "player_name",
    "live_rating",
    "match_count",
    "team_name",
    "club_name",
]


def _unique(iterable: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in iterable:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def generate_rule_draft(prompt: str) -> PromptRuleDraft:
    """Generate a heuristic rule draft from a natural language *prompt*.

    Parameters
    ----------
    prompt: str
        User entered description of desired extraction.

    Returns
    -------
    PromptRuleDraft
        Proposed draft rule set + reasoning.

    Notes
    -----
    * Empty or whitespace prompts produce a minimal placeholder list rule
      with a single ``placeholder_field`` so user still sees schema shape.
    * Multiple tokens mapping to the same canonical field collapse to one.
    * The resource name is derived from the *plural* primary entity when
      available (player(s), team(s), club(s)); otherwise ``items``.
    """
    raw = (prompt or "").strip()
    if not raw:
        # Minimal placeholder
        rs = RuleSet(
            resources={
                "items": ListRule(
                    selector=".items",
                    item_selector=".item",
                    fields={"placeholder_field": FieldMapping(selector=".value")},
                )
            }
        )
        return PromptRuleDraft(
            ruleset=rs,
            explanation=["Prompt empty -> generated minimal placeholder rule"],
            raw_tokens=[],
        )

    # Tokenize (very light): split non-alphanumeric boundaries, lowercase
    import re

    tokens = [t.lower() for t in re.split(r"[^A-Za-z0-9_]+", raw) if t]
    tokens_unique = _unique(tokens)

    field_map: Dict[str, FieldMapping] = {}
    explanation: List[str] = []
    matched_semantic_tokens: List[str] = []

    for tok in tokens_unique:
        if tok in TOKEN_FIELD_MAP:
            fname, sel = TOKEN_FIELD_MAP[tok]
            if fname not in field_map:
                field_map[fname] = FieldMapping(selector=sel)
                explanation.append(f"Matched token '{tok}' -> field '{fname}' (selector '{sel}')")
                matched_semantic_tokens.append(tok)

    # Determine primary entity name for resource naming
    resource_name = "items"
    entity_candidates = [
        ("players", {"player", "players"}),
        ("teams", {"team", "teams"}),
        ("clubs", {"club", "clubs"}),
    ]
    for name, variants in entity_candidates:
        if any(v in tokens_unique for v in variants):
            resource_name = name
            break

    # Ensure deterministic field ordering per preference
    if not field_map:
        # Provide at least a meaningful default if no recognized tokens
        field_map["extracted_value"] = FieldMapping(selector=".value")
        explanation.append("No known semantic tokens, added generic 'extracted_value' field")
    else:
        ordered: Dict[str, FieldMapping] = {}
        for fname in FIELD_PREFERENCE_ORDER:
            if fname in field_map:
                ordered[fname] = field_map[fname]
        # Append any others not in preference list (future extensions)
        for k, v in field_map.items():
            if k not in ordered:
                ordered[k] = v
        field_map = ordered

    # Build list rule with generic container selectors (user refines later)
    list_rule = ListRule(
        selector=f".{resource_name}",
        item_selector=f".{resource_name[:-1]}" if resource_name.endswith("s") else f".{resource_name}-item",
        fields=field_map,
    )
    rs = RuleSet(resources={resource_name: list_rule})

    if matched_semantic_tokens:
        explanation.append(
            "Primary resource determined as '" + resource_name + "' from tokens: " + ", ".join(matched_semantic_tokens)
        )

    explanation.append("Selectors are placeholders – refine them to match actual DOM structure.")

    return PromptRuleDraft(ruleset=rs, explanation=explanation, raw_tokens=tokens_unique)


# Utility to export to a JSON‑serializable mapping (avoids adding to RuleSet API right now)

def ruleset_to_mapping(rs: RuleSet) -> Dict[str, object]:  # pragma: no cover - trivial wrapper
    out: Dict[str, object] = {
        "version": rs.version,
        "allow_expressions": rs.allow_expressions,
        "resources": {},
    }
    for name, res in rs.resources.items():
        out["resources"][name] = res.to_mapping()  # type: ignore[attr-defined]
    return out
