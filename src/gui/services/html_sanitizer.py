"""HTML sanitization helpers for ingestion and GUI preview.

Provides a minimal, dependency-light sanitizer using BeautifulSoup to strip
dangerous elements (script/style) and unsafe attributes (on* event handlers,
javascript: hrefs, inline styles). This is a baseline helper; for higher
security requirements consider a dedicated library (e.g., bleach) and a
whitelist approach.
"""

from __future__ import annotations

from typing import Iterable

from bs4 import BeautifulSoup  # type: ignore


def _iter_attrs(tag) -> Iterable[str]:
    # BeautifulSoup tag.attrs is a dict; return attribute names copy
    return list(tag.attrs.keys())


def sanitize_html(html: str) -> str:
    """Return a sanitized HTML string suitable for lightweight preview.

    The sanitizer removes:
      - <script> and <style> elements entirely
      - attributes that start with 'on' (event handlers)
      - inline 'style' attributes
      - href/src attributes that start with 'javascript:' (removed)

    This is intentionally conservative and aims to protect the GUI when
    rendering scraped HTML. It is not a substitute for server-side
    sanitization in hostile environments.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style tags
    for tag_name in ("script", "style"):
        for t in soup.find_all(tag_name):
            t.decompose()

    # Clean attributes
    for tag in soup.find_all(True):
        for attr in _iter_attrs(tag):
            low = attr.lower()
            if low.startswith("on"):
                # event handler like onclick
                tag.attrs.pop(attr, None)
                continue
            if low == "style":
                # remove inline styles to enforce token-driven styling
                tag.attrs.pop(attr, None)
                continue
            if low in {"href", "src"}:
                val = tag.attrs.get(attr, "")
                if isinstance(val, list):
                    val = val[0] if val else ""
                if isinstance(val, str) and val.strip().lower().startswith("javascript:"):
                    # remove unsafe javascript: links
                    tag.attrs.pop(attr, None)
                    continue

    return str(soup)
