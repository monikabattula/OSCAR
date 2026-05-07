from __future__ import annotations

import random
import time
from datetime import date
from typing import Literal

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException, RatelimitException

from serp_prototype.engines.base import SerpEngine
from serp_prototype.models import SerpHit, TimePeriod

DdgHttpBackend = Literal["lite", "html", "auto"]


def _timelimit(period: TimePeriod) -> str | None:
    """Map to duckduckgo_search timelimit: d, w, m, y."""
    return {
        TimePeriod.PAST_24_HOURS: "d",
        TimePeriod.PAST_WEEK: "w",
        TimePeriod.PAST_MONTH: "m",
        TimePeriod.PAST_YEAR: "y",
    }.get(period)


def _is_ratelimit_error(exc: BaseException) -> bool:
    if isinstance(exc, RatelimitException):
        return True
    msg = str(exc).lower()
    return "ratelimit" in msg or " 202 " in msg or " 429 " in msg or " 403 " in msg


class DuckDuckGoEngine(SerpEngine):
    """
    DuckDuckGo text search via the `duckduckgo-search` package (unofficial HTML endpoints).

    DuckDuckGo aggressively rate-limits automated traffic. This engine:
    - defaults to the **lite** HTML endpoint (often more stable than `html.duckduckgo.com`);
    - retries with exponential backoff + jitter on HTTP 202 / rate limits.

    For large `-n` or production use, prefer `--engine google` (Custom Search API).

    Review https://duckduckgo.com/terms before production use.
    """

    name = "duckduckgo"

    def __init__(
        self,
        region: str = "wt-wt",
        *,
        http_backend: DdgHttpBackend = "lite",
        max_attempts: int = 6,
        retry_base_seconds: float = 8.0,
        timeout: int = 30,
    ) -> None:
        self._region = region
        self._http_backend: DdgHttpBackend = http_backend
        self._max_attempts = max(1, max_attempts)
        self._retry_base_seconds = max(1.0, retry_base_seconds)
        self._timeout = timeout

    def search(
        self,
        query: str,
        period: TimePeriod,
        *,
        date_start: date | None = None,
        date_end: date | None = None,
        max_results: int = 50,
    ) -> list[SerpHit]:
        q = query.strip()
        if period is TimePeriod.CUSTOM and date_start and date_end:
            q = f"{q} after:{date_start.isoformat()} before:{date_end.isoformat()}"

        tl = _timelimit(period)
        cap = min(max(1, max_results), 100)

        for attempt in range(self._max_attempts):
            try:
                # Fresh client each attempt (new TLS fingerprint / impersonate rotation in library).
                with DDGS(timeout=self._timeout) as ddgs:
                    rows = ddgs.text(
                        keywords=q,
                        region=self._region,
                        safesearch="moderate",
                        timelimit=tl,
                        backend=self._http_backend,
                        max_results=cap,
                    )
                hits: list[SerpHit] = []
                for row in rows:
                    title = (row.get("title") or "").strip()
                    url = (row.get("href") or row.get("url") or "").strip()
                    excerpt = (row.get("body") or "").strip()
                    hits.append(
                        SerpHit(title=title, author="", url=url, excerpt=excerpt, source_created_at="")
                    )
                    if len(hits) >= cap:
                        break
                return hits[:cap]
            except (RatelimitException, DuckDuckGoSearchException) as e:
                if not _is_ratelimit_error(e) or attempt >= self._max_attempts - 1:
                    raise
                # Exponential backoff + jitter; cap each sleep so a run cannot stall many minutes.
                raw = self._retry_base_seconds * (2**attempt) + random.uniform(0.5, 2.5)
                wait = min(45.0, raw)
                time.sleep(wait)
