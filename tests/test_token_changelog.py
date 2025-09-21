"""Tests for design token changelog generation (Milestone 0.42)."""

from __future__ import annotations

from gui.design.token_changelog import (
    flatten_tokens,
    diff_tokens,
    TokenChange,
    TokenChangelog,
)


def test_flatten_simple_nested_mapping():
    data = {"color": {"background": {"base": "#fff", "alt": "#eee"}}}
    flat = flatten_tokens(data)
    assert flat["color.background.base"] == "#fff"
    assert flat["color.background.alt"] == "#eee"
    assert len(flat) == 2


def test_flatten_including_list_indices():
    data = {"palette": ["#000", "#111"], "spacing": {"s": 4}}
    flat = flatten_tokens(data)
    assert flat["palette.0"] == "#000"
    assert flat["palette.1"] == "#111"
    assert flat["spacing.s"] == 4


def test_diff_tokens_added_removed_changed():
    old = {
        "color": {"background": {"base": "#000"}},
        "spacing": {"s": 4, "m": 8},
        "typography": {"scale": {"body": 14}},
    }
    new = {
        "color": {"background": {"base": "#111", "alt": "#222"}},  # changed + added
        "spacing": {"m": 8, "l": 16},  # removed 's', added 'l'
        "typography": {"scale": {"body": 14}},  # unchanged
    }
    changelog = diff_tokens(old, new)

    added_keys = {c.key for c in changelog.added}
    removed_keys = {c.key for c in changelog.removed}
    changed_keys = {c.key for c in changelog.changed}

    assert "color.background.alt" in added_keys
    assert "spacing.s" in removed_keys
    assert "color.background.base" in changed_keys

    # Ensure stable ordering (sorted) - compare list of keys to its sorted variant
    assert [c.key for c in changelog.added] == sorted([c.key for c in changelog.added])
    assert [c.key for c in changelog.changed] == sorted([c.key for c in changelog.changed])

    # Validate old/new values for changed entry
    changed_entry = next(c for c in changelog.changed if c.key == "color.background.base")
    assert changed_entry.old == "#000"
    assert changed_entry.new == "#111"


def test_summary_by_category_counts_correct():
    old = {"color": {"text": {"fg": "#000"}}, "spacing": {"s": 4}}
    new = {"color": {"text": {"fg": "#111", "muted": "#333"}}, "spacing": {"s": 4, "m": 8}}
    cl = diff_tokens(old, new)
    summary = cl.summary_by_category()
    assert summary["color"]["changed"] == 1  # fg changed
    assert summary["color"]["added"] == 1  # muted added
    assert summary["spacing"]["added"] == 1  # m added
    assert summary["spacing"]["changed"] == 0
    assert summary["spacing"]["removed"] == 0


def test_is_empty_helper():
    old = {"color": {"a": 1}}
    new = {"color": {"a": 1}}
    cl = diff_tokens(old, new)
    assert cl.is_empty()
