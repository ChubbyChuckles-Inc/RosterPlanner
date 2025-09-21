"""HTTP client utilities with simple retry logic.

Separated from parsing so it can be swapped (e.g., requests, httpx, asyncio) later.
"""

from __future__ import annotations

import time
import urllib.request
import urllib.error
from typing import Optional

from config import settings


class HttpError(RuntimeError):
    pass


def fetch(
    url: str,
    *,
    user_agent: Optional[str] = None,
    timeout: Optional[int] = None,
    retries: int | None = None,
    backoff_factor: float | None = None,
    verbose: bool = True,
) -> str:
    ua = user_agent or settings.DEFAULT_USER_AGENT
    timeout = timeout or settings.DEFAULT_TIMEOUT
    retries = retries if retries is not None else settings.DEFAULT_RETRIES
    backoff_factor = (
        backoff_factor if backoff_factor is not None else settings.DEFAULT_BACKOFF_FACTOR
    )

    headers = {"User-Agent": ua}
    attempt = 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_bytes = resp.read()
                return content_bytes.decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:  # type: ignore[union-attr]
            if attempt > retries:
                raise HttpError(f"Failed to fetch {url} after {retries} retries: {e}") from e
            sleep_for = backoff_factor * (2 ** (attempt - 1))
            if verbose:
                print(
                    f"[http] Attempt {attempt}/{retries} failed for {url}: {e}. Retrying in {sleep_for:.1f}s..."
                )
            time.sleep(sleep_for)
        except Exception as e:  # noqa: BLE001
            raise HttpError(f"Unexpected error for {url}: {e}") from e
