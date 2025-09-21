"""HTML helper utilities (currently regex-light, placeholder for future BeautifulSoup migration)."""

from __future__ import annotations

import re
from typing import Iterable

TAG_RE = re.compile(r"<[^>]+>")
NBSP_RE = re.compile(r"&nbsp;?")
WS_RE = re.compile(r"\s+")


def strip_tags(html: str) -> str:
    return TAG_RE.sub("", html)


def clean_cell(text: str) -> str:
    text = strip_tags(text)
    text = NBSP_RE.sub(" ", text)
    text = WS_RE.sub(" ", text).strip()
    return text


def extract_last_number(text: str) -> str | None:
    nums = re.findall(r"\d+", text)
    return nums[-1] if nums else None


def dedupe(seq: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
