"""Format inference utilities for transform suggestions.

This module analyses raw sample values collected from HTML selections and
produces recommendations for numeric and date parsing transforms.  The
functions are intentionally UI-agnostic so they can be exercised in unit
tests and reused by both GUI workflows and potential CLI helpers.

The heuristics favour maintainability over exhaustive locale support: we
attempt to recognise common numeric separators via Babel and a curated list
of locales, and we match dates against an explicit catalogue of
``strptime`` patterns.  The result objects capture confidence scores and
ready-to-apply transform payloads that the GUI can feed directly into the
rule builder model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import math
import re
from typing import Iterable, List, Optional, Sequence

try:  # pragma: no cover - optional babel import guard
    from babel import Locale
    from babel.core import UnknownLocaleError
    from babel.numbers import NumberFormatError, parse_decimal
except Exception:  # pragma: no cover - fallback when Babel unavailable
    Locale = None  # type: ignore
    parse_decimal = None  # type: ignore
    NumberFormatError = Exception  # type: ignore
    UnknownLocaleError = Exception  # type: ignore

__all__ = [
    "NumberFormatSuggestion",
    "DateFormatSuggestion",
    "FormatInferenceResult",
    "infer_number_format",
    "infer_date_formats",
    "infer_formats",
]

_DEFAULT_NUMERIC_LOCALES: tuple[str, ...] = (
    "en_US",
    "en_GB",
    "de_DE",
    "fr_FR",
    "es_ES",
    "it_IT",
    "nl_NL",
    "sv_SE",
    "pl_PL",
    "cs_CZ",
)

_BASIC_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y%m%d",
    "%d.%m.%Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d.%m.%y",
    "%d-%m-%y",
    "%d/%m/%y",
    "%m/%d/%y",
    "%y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%d %b %y",
)

_TIME_SUFFIXES: tuple[str, ...] = (" %H:%M", " %H:%M:%S", "T%H:%M", "T%H:%M:%S")

_CANDIDATE_DATE_FORMATS: List[str] = []
for base in _BASIC_DATE_FORMATS:
    _CANDIDATE_DATE_FORMATS.append(base)
    for suffix in _TIME_SUFFIXES:
        _CANDIDATE_DATE_FORMATS.append(f"{base}{suffix}")
_CANDIDATE_DATE_FORMATS.extend(
    [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%d.%m.%YT%H:%M",
        "%d.%m.%Y %H:%M:%S",
    ]
)

_NUMERIC_SAMPLE_RE = re.compile(r"[0-9]")
_DATE_TOKEN_RE = re.compile(r"[0-9]{2,4}")


@dataclass()
class NumberFormatSuggestion:
    """Suggested transform payload for numeric values."""

    locale: Optional[str]
    decimal_separator: Optional[str]
    grouping_separator: Optional[str]
    sample_count: int
    success_count: int
    normalized_samples: List[str]
    confidence: float

    def build_transforms(self) -> List[dict]:
        """Return the recommended transform chain payload."""

        return [{"kind": "to_number"}]

    def summary(self) -> str:
        """Human-readable summary string."""

        parts = [
            f"locale={self.locale}" if self.locale else "locale=auto",
            f"decimal='{self.decimal_separator or '.'}'",
        ]
        if self.grouping_separator:
            parts.append(f"group='{self.grouping_separator}'")
        parts.append(f"confidence={self.confidence:.0%}")
        return ", ".join(parts)


@dataclass()
class DateFormatSuggestion:
    """Suggested transform payload for date parsing."""

    formats: List[str]
    sample_count: int
    success_count: int
    confidence: float
    example_iso: str

    def build_transforms(self) -> List[dict]:
        """Return the recommended parse_date payload."""

        return [{"kind": "parse_date", "formats": self.formats}]

    def summary(self) -> str:
        """Human-readable summary."""

        return f"formats={self.formats} confidence={self.confidence:.0%}"


@dataclass()
class FormatInferenceResult:
    """Aggregate inference output for both numeric and date suggestions."""

    number: Optional[NumberFormatSuggestion]
    dates: List[DateFormatSuggestion]

    @property
    def has_suggestions(self) -> bool:
        """Return ``True`` when at least one suggestion is available."""

        return (self.number is not None) or bool(self.dates)


def _prepare_numeric_sample(sample: str) -> str:
    text = sample.strip()
    if not text:
        return ""
    # Remove common currency symbols / percent signs while keeping separators.
    text = re.sub(r"[\u00a0\s]+", " ", text)  # normalise spaces / NBSP
    text = re.sub(r"[^0-9,\.\-+ ]", "", text)
    return text.strip()


def _manual_parse_number(text: str) -> Optional[Decimal]:
    if not text:
        return None
    normalized = text.replace("\xa0", " ")
    normalized = re.sub(r"(?<=\d)[\s_]+(?=\d)", "", normalized)
    last_comma = normalized.rfind(",")
    last_dot = normalized.rfind(".")
    if last_comma == -1 and last_dot == -1:
        pass
    elif last_comma > last_dot:
        normalized = normalized.replace(".", "")
        normalized = normalized.replace(",", ".")
    elif last_dot > last_comma:
        normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", "")
        normalized = normalized.replace(".", "")
    try:
        if re.fullmatch(r"[-+]?\d+", normalized):
            return Decimal(int(normalized))
        return Decimal(normalized)
    except Exception:
        return None


def _guess_separators(samples: Sequence[str]) -> tuple[Optional[str], Optional[str]]:
    decimal_sep: Optional[str] = None
    grouping_sep: Optional[str] = None
    for sample in samples:
        if not sample:
            continue
        if decimal_sep is None:
            comma_pos = sample.rfind(",")
            dot_pos = sample.rfind(".")
            if comma_pos > dot_pos >= 0 or (comma_pos >= 0 and dot_pos == -1):
                decimal_sep = ","
            elif dot_pos >= 0:
                decimal_sep = "."
        if grouping_sep is None:
            for sep in (".", ",", " "):
                parts = sample.split(sep)
                if len(parts) > 2 and all(len(p) == 3 for p in parts[1:-1]):
                    grouping_sep = sep
                    break
        if decimal_sep and grouping_sep:
            break
    return decimal_sep, grouping_sep


def infer_number_format(
    samples: Sequence[str],
    *,
    locales: Sequence[str] | None = None,
    min_confidence: float = 0.5,
    max_preview: int = 5,
) -> Optional[NumberFormatSuggestion]:
    """Infer numeric formatting heuristics from the given *samples*.

    The function attempts to parse each sample using Babel's ``parse_decimal``
    for a curated list of locales.  If no locale reaches the required
    *min_confidence*, a manual fallback parser is used so that we still offer a
    suggestion for obviously numeric strings.
    """

    locales = tuple(locales) if locales else _DEFAULT_NUMERIC_LOCALES
    numeric_candidates = [
        _prepare_numeric_sample(sample)
        for sample in samples
        if sample and _NUMERIC_SAMPLE_RE.search(sample)
    ]
    if not numeric_candidates:
        return None

    best: Optional[NumberFormatSuggestion] = None
    best_score = -1.0
    baseline_decimals = [_manual_parse_number(sample) for sample in numeric_candidates]
    if parse_decimal is not None:
        for locale in locales:
            success = 0
            parsed: List[str] = []
            for sample in numeric_candidates:
                try:
                    value = parse_decimal(sample, locale=locale)
                except NumberFormatError:
                    continue
                except UnknownLocaleError:  # pragma: no cover - defensive
                    break
                normalized = format(value, "f").rstrip("0").rstrip(".")
                parsed.append(normalized or "0")
                success += 1
            if not success:
                continue
            confidence = success / len(numeric_candidates)
            decimal_sep = grouping_sep = None
            if Locale is not None:
                try:
                    locale_obj = Locale.parse(locale)
                    decimal_sep = locale_obj.number_symbols.get("decimal")
                    grouping_sep = locale_obj.number_symbols.get("group")
                except (UnknownLocaleError, AttributeError):
                    decimal_sep = grouping_sep = None
            guess_decimal, guess_grouping = _guess_separators(numeric_candidates)
            if decimal_sep is None:
                decimal_sep = guess_decimal
            if grouping_sep is None:
                grouping_sep = guess_grouping
            score = confidence
            if decimal_sep and guess_decimal and decimal_sep == guess_decimal:
                score += 0.01
            if grouping_sep and guess_grouping and grouping_sep == guess_grouping:
                score += 0.005
            baseline_count = sum(1 for item in baseline_decimals if item is not None)
            if baseline_count:
                match_count = 0
                for parsed_value, baseline_value in zip(parsed, baseline_decimals):
                    if baseline_value is None:
                        continue
                    try:
                        if Decimal(parsed_value) == baseline_value:
                            match_count += 1
                    except Exception:
                        continue
                score += (match_count / baseline_count) * 0.05
            if score > best_score:
                best_score = score
                best = NumberFormatSuggestion(
                    locale=locale,
                    decimal_separator=decimal_sep,
                    grouping_separator=grouping_sep,
                    sample_count=len(numeric_candidates),
                    success_count=success,
                    normalized_samples=parsed[:max_preview],
                    confidence=confidence,
                )

    if best and best.confidence >= min_confidence:
        return best

    # Fallback heuristic
    successes = 0
    parsed_samples: List[str] = []
    for sample in numeric_candidates:
        parsed_value = _manual_parse_number(sample)
        if parsed_value is None:
            continue
        parsed_samples.append(format(parsed_value, "f").rstrip("0").rstrip(".") or "0")
        successes += 1
    if not successes:
        return None

    decimal_sep, grouping_sep = _guess_separators(numeric_candidates)
    confidence = successes / len(numeric_candidates)
    return NumberFormatSuggestion(
        locale=None,
        decimal_separator=decimal_sep,
        grouping_separator=grouping_sep,
        sample_count=len(numeric_candidates),
        success_count=successes,
        normalized_samples=parsed_samples[:max_preview],
        confidence=confidence,
    )


def infer_date_formats(
    samples: Sequence[str],
    *,
    min_confidence: float = 0.5,
    max_suggestions: int = 3,
) -> List[DateFormatSuggestion]:
    """Return candidate ``parse_date`` format lists for the given *samples*."""

    cleaned: List[str] = [sample.strip() for sample in samples if sample and sample.strip()]
    cleaned = [sample for sample in cleaned if _DATE_TOKEN_RE.search(sample)]
    if not cleaned:
        return []

    matches: dict[str, List[str]] = {}
    for fmt in _CANDIDATE_DATE_FORMATS:
        matched_samples: List[str] = []
        for sample in cleaned:
            try:
                dt = datetime.strptime(sample, fmt)
            except ValueError:
                continue
            normalized = dt.date().isoformat()
            matched_samples.append(normalized)
        if matched_samples:
            matches[fmt] = matched_samples

    if not matches:
        return []

    scored: List[DateFormatSuggestion] = []
    total = len(cleaned)
    for fmt, normalized_samples in matches.items():
        success = len(normalized_samples)
        confidence = success / total
        if confidence < min_confidence and success < math.ceil(total * min_confidence):
            continue
        scored.append(
            DateFormatSuggestion(
                formats=[fmt],
                sample_count=total,
                success_count=success,
                confidence=confidence,
                example_iso=normalized_samples[0],
            )
        )

    scored.sort(key=lambda s: (s.confidence, s.success_count), reverse=True)
    unique: List[DateFormatSuggestion] = []
    seen_formats: set[tuple[str, ...]] = set()
    for suggestion in scored:
        key = tuple(suggestion.formats)
        if key in seen_formats:
            continue
        unique.append(suggestion)
        seen_formats.add(key)
        if len(unique) >= max_suggestions:
            break
    return unique


def infer_formats(samples: Sequence[str]) -> FormatInferenceResult:
    """Infer both numeric and date format hints for *samples*."""

    number = infer_number_format(samples)
    dates = infer_date_formats(samples)
    return FormatInferenceResult(number=number, dates=dates)
