"""Tests for token metadata annotation (Milestone 0.43)."""

from __future__ import annotations

import pytest

from gui.design import load_tokens
from gui.design.token_metadata import (
    annotate_usage,
    mark_deprecated,
    get_metadata,
    list_metadata,
    list_deprecated,
    clear_metadata,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_metadata()
    yield
    clear_metadata()


@pytest.fixture(scope="module")
def tokens():
    return load_tokens()


def test_annotate_usage_increments(tokens):
    # Pick a known token key (use first heading size token path via loader introspection)
    # We'll rely on presence of typography.scale.body (from baseline tokens)
    key = "typography.scale.base"
    meta1 = annotate_usage(key, tokens=tokens)
    assert meta1.usage_count == 1
    meta2 = annotate_usage(key)
    assert meta2.usage_count == 2
    assert meta2.usage_events == [1, 1]


def test_mark_deprecated_sets_flags(tokens):
    # Seed known keys by annotating one valid key
    annotate_usage("spacing.1", tokens=tokens)  # seed known keys (spacing '1' exists)
    # Choose a real spacing key present in tokens
    candidate = None
    for k in list_metadata():
        if k.key.startswith("spacing."):
            candidate = k.key
            break
    assert candidate is not None
    meta = mark_deprecated(candidate, replacement="spacing.2", reason="Consolidated")
    assert meta.deprecated is True
    assert meta.replacement == "spacing.2"
    assert meta.reason == "Consolidated"
    assert meta in list_deprecated()


def test_unknown_key_rejected(tokens):
    with pytest.raises(KeyError):
        annotate_usage("nonexistent.group.token", tokens=tokens)


def test_get_metadata_none_when_missing(tokens):
    assert get_metadata("color.background.base") is None  # not yet annotated
