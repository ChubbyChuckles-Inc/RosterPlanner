"""Simple internationalization (i18n) infrastructure.

Goals for milestone 0.12 (readiness):
 - Minimal translation registry with locale switch & fallback.
 - String interpolation via ``str.format`` with named placeholders.
 - Basic pluralisation helper (English style singular/plural selection).
 - Key extraction helper scanning source files for ``t("...")`` / ``translate("...")`` / ``tp("...","...",``.
 - Zero external dependencies; Python 3.8 compatible.

Design decisions / assumptions:
 - A *default locale* (``_DEFAULT_LOCALE``) always exists (``"en"``) and is consulted as fallback.
 - Missing key after fallback returns the key itself (easy to spot during audits) rather than raising.
 - Plural helper expects two keys: singular_key, plural_key. Language‑specific plural rules are out of scope now.
 - Thread safety not critical at this stage; a simple module‑level lock can be added later if needed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any, Set, Iterable, Optional

__all__ = [
    "register_catalog",
    "set_locale",
    "get_locale",
    "t",
    "translate",
    "tp",
    "translate_plural",
    "extract_translation_keys",
]

_DEFAULT_LOCALE = "en"
_current_locale = _DEFAULT_LOCALE

_catalogs: Dict[str, Dict[str, str]] = {}


def register_catalog(locale: str, catalog: Dict[str, str]) -> None:
    """Register or extend a catalog for a locale.

    Existing keys are updated (last registration wins). Empty catalogs allowed.
    """
    existing = _catalogs.setdefault(locale, {})
    existing.update(catalog)


def set_locale(locale: str) -> None:
    global _current_locale
    _current_locale = locale


def get_locale() -> str:
    return _current_locale


def _lookup(locale: str, key: str) -> Optional[str]:
    catalog = _catalogs.get(locale)
    if not catalog:
        return None
    return catalog.get(key)


def translate(key: str, **variables: Any) -> str:
    """Translate a key using the current locale with fallback.

    Variables are interpolated using ``str.format``. Missing variables raise ``KeyError``
    to surface programmer error.
    """
    # Try current locale first
    text = _lookup(_current_locale, key)
    if text is None and _current_locale != _DEFAULT_LOCALE:
        text = _lookup(_DEFAULT_LOCALE, key)
    if text is None:
        text = key  # final fallback
    # Always attempt formatting if the string appears to contain placeholders so that
    # missing variables surface as KeyError for developer feedback.
    needs_format = "{" in text and "}" in text
    try:
        if needs_format:
            return text.format(**variables)
        return text
    except KeyError as e:  # pragma: no cover - defensive
        # Surface clearer message while preserving offending key.
        raise KeyError(f"Missing interpolation variable {e.args[0]!r} for key '{key}'") from e


# Short alias commonly used in UI code.
t = translate


def translate_plural(singular_key: str, plural_key: str, n: int, **variables: Any) -> str:
    """Very small pluralisation helper.

    Chooses ``singular_key`` when ``n == 1`` else ``plural_key``. The chosen key is
    passed through ``translate`` with an automatic ``n`` variable added (unless user supplied).
    """
    chosen = singular_key if n == 1 else plural_key
    if "n" not in variables:
        variables["n"] = n
    return translate(chosen, **variables)


# Short alias
tp = translate_plural


_RE_T_CALL = re.compile(r"\b(?:t|translate)\(\s*['\"]([^'\"]+)['\"]")
_RE_TP_CALL = re.compile(
    r"\b(?:tp|translate_plural)\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"
)


def extract_translation_keys(paths: Iterable[str | Path]) -> Set[str]:
    """Scan provided directories / files for translation key usages.

    Recognises:
      - t("key.path") / translate("key.path")
      - tp("singular.key", "plural.key", <expr>) / translate_plural(...)

    Returns a set of all discovered keys (both singular & plural forms).
    """
    collected: Set[str] = set()
    for p in paths:
        path = Path(p)
        if path.is_dir():
            for file in path.rglob("*.py"):
                _extract_file(file, collected)
        elif path.is_file() and path.suffix == ".py":
            _extract_file(path, collected)
    return collected


def _extract_file(file: Path, sink: Set[str]) -> None:
    try:
        text = file.read_text(encoding="utf-8")
    except Exception:  # pragma: no cover - IO safety
        return
    for m in _RE_T_CALL.finditer(text):
        sink.add(m.group(1))
    for m in _RE_TP_CALL.finditer(text):
        sink.add(m.group(1))
        sink.add(m.group(2))


# Register default English catalog.
register_catalog(
    _DEFAULT_LOCALE,
    {
        "greeting.hello": "Hello from project-template!",
        "greeting.named": "Hello {name}",
        "items.count.one": "{n} item",
        "items.count.other": "{n} items",
    },
)
