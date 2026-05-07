from __future__ import annotations

import base64
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from serp_prototype.engines.base import SerpEngine
from serp_prototype.models import SerpHit, TimePeriod

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"


def _reddit_time_filter(period: TimePeriod) -> str:
    """Reddit `t` param: hour, day, week, month, year, all."""
    return {
        TimePeriod.PAST_24_HOURS: "day",
        TimePeriod.PAST_WEEK: "week",
        TimePeriod.PAST_MONTH: "month",
        TimePeriod.PAST_YEAR: "year",
        TimePeriod.CUSTOM: "all",
    }[period]


def _excerpt(data: dict[str, Any], max_len: int = 800) -> str:
    text = (data.get("selftext") or "").strip()
    if text:
        return text[:max_len] + ("…" if len(text) > max_len else "")
    url = (data.get("url_overridden_by_dest") or data.get("url") or "").strip()
    if url and url != data.get("permalink"):
        return url[:max_len]
    return ""


def _post_url(data: dict[str, Any]) -> str:
    perm = (data.get("permalink") or "").strip()
    if perm.startswith("/"):
        return f"https://www.reddit.com{perm}"
    if perm.startswith("http"):
        return perm
    return (data.get("url") or "").strip()


class RedditSearchEngine(SerpEngine):
    """
    Reddit global post search via official OAuth2 (application-only) + /search.

    Register an app at https://www.reddit.com/prefs/apps (type: "script" or "web app"),
    then set in `.env`:

      REDDIT_CLIENT_ID=...
      REDDIT_CLIENT_SECRET=...
      REDDIT_USER_AGENT=research_bot/0.1 by u/YourRedditUsername

    Reddit requires a descriptive User-Agent string. See https://github.com/reddit/reddit/wiki/API.

    Time filters use Reddit's `t` parameter; `custom` uses `t=all` (no native date-range filter).
    """

    name = "reddit"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        timeout: float = 30.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _fetch_token(self, client: httpx.Client) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token

        basic = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        r = client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "User-Agent": self._user_agent,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        r.raise_for_status()
        payload = r.json()
        self._token = payload["access_token"]
        # Reddit typically returns expires_in ~3600
        self._token_expires_at = now + float(payload.get("expires_in", 3500))
        return self._token

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

        t_filter = _reddit_time_filter(period)
        cap = min(max(1, max_results), 100)
        hits: list[SerpHit] = []
        after: str | None = None

        headers_base = {"User-Agent": self._user_agent}

        with httpx.Client(timeout=self._timeout, headers=headers_base) as client:
            while len(hits) < cap:
                token = self._fetch_token(client)
                limit = min(100, cap - len(hits))
                params: dict[str, str] = {
                    "q": q,
                    "limit": str(limit),
                    "sort": "relevance",
                    "t": t_filter,
                    "raw_json": "1",
                }
                if after:
                    params["after"] = after

                r = client.get(
                    SEARCH_URL,
                    headers={
                        **headers_base,
                        "Authorization": f"bearer {token}",
                    },
                    params=params,
                )
                if r.status_code == 401:
                    self._token = None
                    token = self._fetch_token(client)
                    r = client.get(
                        SEARCH_URL,
                        headers={**headers_base, "Authorization": f"bearer {token}"},
                        params=params,
                    )
                r.raise_for_status()
                data = r.json()
                root = data.get("data") or {}
                children = root.get("children") or []
                if not children:
                    break

                for ch in children:
                    if not isinstance(ch, dict) or ch.get("kind") != "t3":
                        continue
                    d = ch.get("data") or {}
                    if not isinstance(d, dict):
                        continue
                    title = (d.get("title") or "").strip()
                    author = (d.get("author") or "").strip()
                    if author in ("[deleted]", "AutoModerator"):
                        author = ""
                    url = _post_url(d)
                    excerpt = _excerpt(d)
                    created = ""
                    cu = d.get("created_utc")
                    if isinstance(cu, (int, float)):
                        created = (
                            datetime.fromtimestamp(float(cu), tz=timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ")
                        )
                    hits.append(
                        SerpHit(
                            title=title,
                            author=author,
                            url=url,
                            excerpt=excerpt,
                            source_created_at=created,
                        )
                    )
                    if len(hits) >= cap:
                        break

                after = root.get("after")
                if not after or len(children) < limit:
                    break

        return hits[:cap]
