"""Simple filesystem cache for HTTP GET responses."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Optional

from config import settings

CACHE_DIR = os.path.join(settings.DATA_DIR, "_cache")
DEFAULT_TTL = 3600  # 1 hour


def _key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _path(url: str) -> str:
    return os.path.join(CACHE_DIR, _key(url) + ".cache")


def get(url: str, ttl: int = DEFAULT_TTL) -> Optional[str]:
    p = _path(url)
    if not os.path.exists(p):
        return None
    try:
        stat = os.stat(p)
        if time.time() - stat.st_mtime > ttl:
            return None
        with open(p, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def set(url: str, content: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_path(url), "w", encoding="utf-8") as fh:
        fh.write(content)
