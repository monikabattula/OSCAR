from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from serp_prototype.engines.base import SerpEngine
from serp_prototype.models import SerpHit, TimePeriod

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


def _date_restrict(period: TimePeriod) -> str | None:
    """Google Custom Search `dateRestrict` values (d|w|m|y)[n]."""
    mapping = {
        TimePeriod.PAST_24_HOURS: "d1",
        TimePeriod.PAST_WEEK: "w1",
        TimePeriod.PAST_MONTH: "m1",
        TimePeriod.PAST_YEAR: "y1",
    }
    return mapping.get(period)


def _extract_published_time(item: dict[str, Any]) -> str:
    """Best-effort article/publication time from CSE pagemap (ISO-ish string)."""
    pagemap = item.get("pagemap") or {}
    metas = pagemap.get("metatags") or []
    if isinstance(metas, list) and metas and isinstance(metas[0], dict):
        m0 = metas[0]
        lower_map = {str(k).lower(): v for k, v in m0.items()}
        for key in (
            "article:published_time",
            "og:updated_time",
            "datepublished",
            "pubdate",
            "dc.date",
            "dc:date",
        ):
            v = lower_map.get(key) or m0.get(key)
            if isinstance(v, list) and v and isinstance(v[0], str):
                v = v[0]
            if isinstance(v, str) and v.strip():
                s = v.strip()
                if len(s) >= 10:
                    return s[:32]
    return ""


def _extract_author(item: dict[str, Any]) -> str:
    pagemap = item.get("pagemap") or {}
    metas = pagemap.get("metatags") or []
    if isinstance(metas, list) and metas and isinstance(metas[0], dict):
        m0 = metas[0]
        for key in (
            "og:article:author",
            "article:author",
            "author",
            "twitter:creator",
            "dc.creator",
            "dc:creator",
        ):
            v = m0.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


class GoogleCustomSearchEngine(SerpEngine):
    """
    Official Google Programmable Search / Custom Search JSON API.

    Requires env GOOGLE_API_KEY and GOOGLE_CSE_ID (cx).
    Free tier: 100 queries/day; each request returns up to 10 items — we paginate `start`.
    """

    name = "google"

    def __init__(self, api_key: str, cx: str, timeout: float = 30.0) -> None:
        self._api_key = api_key
        self._cx = cx
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

        params_base: dict[str, str] = {
            "key": self._api_key,
            "cx": self._cx,
            "q": q,
        }
        dr = _date_restrict(period)
        if dr:
            params_base["dateRestrict"] = dr

        hits: list[SerpHit] = []
        # API max 10 per request; start is 1-based index in Google's API (1, 11, 21, ...)
        start = 1
        cap = min(max(1, max_results), 100)

        with httpx.Client(timeout=self._timeout) as client:
            while len(hits) < cap:
                num = min(10, cap - len(hits))
                params = {**params_base, "start": str(start), "num": str(num)}
                r = client.get(GOOGLE_CSE_URL, params=params)
                if r.is_error:
                    detail = ""
                    try:
                        payload = r.json()
                        err = payload.get("error") or {}
                        detail = str(err.get("message") or payload)
                        errs = err.get("errors") or []
                        if errs and isinstance(errs, list):
                            reasons = [str(e.get("reason", e)) for e in errs[:3] if e]
                            if reasons:
                                detail += f" | reasons: {', '.join(reasons)}"
                    except Exception:
                        detail = (r.text or "")[:800]
                    raise RuntimeError(
                        f"Google Custom Search API HTTP {r.status_code}: {detail}. "
                        "In Google Cloud: enable Custom Search API, ensure billing if required, "
                        "and set API key restrictions to allow Custom Search API. "
                        "Confirm GOOGLE_CSE_ID is the raw cx from Programmable Search Engine."
                    ) from None
                data = r.json()
                items = data.get("items") or []
                if not items:
                    break
                for item in items:
                    title = (item.get("title") or "").strip()
                    url = (item.get("link") or "").strip()
                    excerpt = (item.get("snippet") or "").strip()
                    author = _extract_author(item)
                    pub = _extract_published_time(item)
                    hits.append(
                        SerpHit(
                            title=title,
                            author=author,
                            url=url,
                            excerpt=excerpt,
                            source_created_at=pub,
                        )
                    )
                start += len(items)
                if len(items) < num:
                    break

        return hits[:cap]
