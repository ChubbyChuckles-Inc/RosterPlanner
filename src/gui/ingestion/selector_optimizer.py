"""Selector optimization heuristics for batch simplification passes.

This module inspects CSS selectors extracted from rule field definitions and
attempts to propose simpler, equivalent alternatives. The optimization focuses
on trimming redundant ancestor segments while verifying that the simplified
selector still resolves to the exact same DOM nodes within a provided HTML
sample. Suggestions are kept conservative to avoid unintended broadening.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional dependency guard for headless testing
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover - bs4 not available in minimal envs
    BeautifulSoup = None  # type: ignore


__all__ = [
    "FieldSelectorContext",
    "SelectorOptimizationSuggestion",
    "compute_selector_optimizations",
]


@dataclass
class FieldSelectorContext:
    """Context for a field selector participating in the optimization pass."""

    field_id: str
    field_label: str
    resource_label: str
    selector: str


@dataclass
class SelectorOptimizationSuggestion:
    """Proposed simplification keeping selector matches equivalent."""

    field_id: str
    field_label: str
    resource_label: str
    original_selector: str
    optimized_selector: str
    match_count: int
    character_reduction: int

    def description(self) -> str:
        return (
            f"{self.field_label} ({self.resource_label}):"
            f" {self.original_selector!r} → {self.optimized_selector!r}"
        )


def compute_selector_optimizations(
    html: str,
    field_contexts: Sequence[FieldSelectorContext],
    *,
    max_candidates_per_field: int = 5,
) -> List[SelectorOptimizationSuggestion]:
    """Return optimization suggestions for the provided field selectors.

    The function parses *html* using BeautifulSoup (if available) and evaluates
    simplified selector variants generated via :func:`_generate_candidates`.
    Suggestions are only emitted when the simplified selector returns the exact
    same DOM nodes (identity check) as the original selector.
    """

    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    suggestions: List[SelectorOptimizationSuggestion] = []
    for context in field_contexts:
        selector = (context.selector or "").strip()
        if not selector:
            continue
        try:
            original_matches = soup.select(selector)
        except Exception:
            continue
        if not original_matches:
            continue
        original_set = set(original_matches)
        candidates = _generate_candidates(selector)[:max_candidates_per_field]
        best_candidate: Optional[Tuple[str, int]] = None
        for candidate in candidates:
            if not candidate or candidate == selector:
                continue
            try:
                candidate_matches = soup.select(candidate)
            except Exception:
                continue
            if not candidate_matches:
                continue
            if len(candidate_matches) != len(original_matches):
                continue
            if set(candidate_matches) != original_set:
                continue
            reduction = len(selector) - len(candidate)
            if reduction <= 0:
                continue
            if not best_candidate or reduction > best_candidate[1]:
                best_candidate = (candidate, reduction)
        if best_candidate:
            suggestions.append(
                SelectorOptimizationSuggestion(
                    field_id=context.field_id,
                    field_label=context.field_label,
                    resource_label=context.resource_label,
                    original_selector=selector,
                    optimized_selector=best_candidate[0],
                    match_count=len(original_matches),
                    character_reduction=best_candidate[1],
                )
            )
    suggestions.sort(key=lambda s: (s.character_reduction, len(s.optimized_selector)), reverse=True)
    return suggestions


def _generate_candidates(selector: str) -> List[str]:
    """Yield selector variants by trimming redundant leading segments."""

    tokens = _split_selector_tokens(selector)
    candidates: List[str] = []
    working = list(tokens)
    while len(working) > 1:
        working = working[1:]
        while working and working[0] == ">":
            working = working[1:]
        if not working:
            break
        candidate = _join_selector_tokens(working)
        if candidate:
            candidates.append(candidate)
    return candidates


def _split_selector_tokens(selector: str) -> List[str]:
    """Split selector into tokens, preserving combinators and attribute values."""

    stripped = selector.strip()
    if not stripped:
        return []
    tokens: List[str] = []
    current: List[str] = []
    bracket_depth = 0
    quote_char: Optional[str] = None
    i = 0
    while i < len(stripped):
        ch = stripped[i]
        if quote_char:
            current.append(ch)
            if ch == quote_char:
                quote_char = None
            i += 1
            continue
        if ch in {'"', "'"}:
            current.append(ch)
            quote_char = ch
            i += 1
            continue
        if ch == "[":
            bracket_depth += 1
            current.append(ch)
            i += 1
            continue
        if ch == "]":
            bracket_depth = max(0, bracket_depth - 1)
            current.append(ch)
            i += 1
            continue
        if ch == ">" and bracket_depth == 0:
            if current:
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
            tokens.append(">")
            i += 1
            continue
        if ch.isspace() and bracket_depth == 0:
            if current:
                token = "".join(current).strip()
                if token:
                    tokens.append(token)
                current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    if current:
        token = "".join(current).strip()
        if token:
            tokens.append(token)
    return tokens


def _join_selector_tokens(tokens: Sequence[str]) -> str:
    """Rebuild selector text from token sequence."""

    pieces: List[str] = []
    for token in tokens:
        if token == ">":
            if pieces and not pieces[-1].endswith(" "):
                pieces[-1] = pieces[-1].rstrip()
            pieces.append(">")
        else:
            pieces.append(token)
    result = []
    for idx, piece in enumerate(pieces):
        if piece == ">":
            if idx > 0 and not result[-1].endswith(" "):
                result[-1] = result[-1].rstrip()
            if result and not result[-1].endswith(" "):
                result[-1] = result[-1].rstrip()
            result.append(">")
        else:
            result.append(piece)
    rebuilt = " ".join(result)
    rebuilt = rebuilt.replace(" >", " >").replace("> ", "> ")
    return rebuilt.strip()
