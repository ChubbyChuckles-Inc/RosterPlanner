"""Async HTTP utilities using httpx with optional caching."""

from __future__ import annotations

import asyncio
import httpx
from typing import Optional
from config import settings
from . import cache


class AsyncHttpError(RuntimeError):
    pass


async def fetch(
    url: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
    retries: int | None = None,
    backoff: float = 0.5,
    use_cache: bool = True,
    cache_ttl: int = 3600,
) -> str:
    retries = retries if retries is not None else settings.DEFAULT_RETRIES
    # Cache lookup
    if use_cache:
        cached = cache.get(url, ttl=cache_ttl)
        if cached is not None:
            return cached
    close_client = False
    if client is None:
        headers = {"User-Agent": settings.DEFAULT_USER_AGENT}
        client = httpx.AsyncClient(headers=headers, timeout=settings.DEFAULT_TIMEOUT)
        close_client = True
    try:
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
                if use_cache:
                    cache.set(url, text)
                return text
            except (httpx.TimeoutException, httpx.HTTPError) as e:
                if attempt > retries:
                    raise AsyncHttpError(f"Failed after {retries} attempts: {e}") from e
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
    finally:
        if close_client:
            await client.aclose()
