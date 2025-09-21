"""i18n audit helpers.

These utilities support milestone 0.12 by enabling an automated check for:
 - Missing keys: referenced in code but absent from one or more locale catalogs.
 - Unused keys: present in catalogs but not referenced anywhere.

Design:
 - We reuse the extraction regexes from the main i18n module by importing them.
 - Audits operate on an explicit set of search roots (directories / files) plus the in-memory catalogs.
 - Returns plain dataclasses (emulated with TypedDict for 3.8 compatibility) for easy test assertions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Set, TypedDict

from . import extract_translation_keys, _catalogs  # type: ignore

__all__ = ["collect_used_keys", "audit_locales"]


def collect_used_keys(paths: Iterable[str | Path]) -> Set[str]:
    """Collect translation keys referenced in code under the given paths."""
    return extract_translation_keys(paths)


class LocaleAuditResult(TypedDict):
    locale: str
    missing: List[str]
    unused: List[str]


def audit_locales(paths: Iterable[str | Path]) -> Dict[str, LocaleAuditResult]:
    """Audit all registered locale catalogs.

    For each locale we compute:
      - missing: keys used in code but not present in that locale (excluding fallback semantics)
      - unused: keys present in the locale catalog but not referenced anywhere
    """
    used = collect_used_keys(paths)
    results: Dict[str, LocaleAuditResult] = {}
    for locale, catalog in _catalogs.items():  # type: ignore[attr-defined]
        keys = set(catalog.keys())
        missing = sorted(k for k in used if k not in keys)
        unused = sorted(k for k in keys if k not in used)
        results[locale] = {
            "locale": locale,
            "missing": missing,
            "unused": unused,
        }
    return results
