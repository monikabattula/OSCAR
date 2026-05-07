from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

from serp_prototype.engines.duckduckgo import DuckDuckGoEngine
from serp_prototype.engines.google_cse import GoogleCustomSearchEngine
from serp_prototype.engines.reddit import RedditSearchEngine
from serp_prototype.models import SearchEngine

DdgBackend = Literal["lite", "html", "auto"]


def build_engine(
    engine: SearchEngine,
    *,
    ddg_http_backend: DdgBackend = "lite",
    ddg_max_attempts: int = 7,
    ddg_retry_base_seconds: float = 6.0,
) -> DuckDuckGoEngine | GoogleCustomSearchEngine | RedditSearchEngine:
    """Construct a search engine from environment (call after load_dotenv in CLI)."""
    if engine is SearchEngine.REDDIT:
        cid = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        csec = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        ua = os.environ.get("REDDIT_USER_AGENT", "").strip()
        if not cid or not csec or not ua:
            raise ValueError(
                "Reddit requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT."
            )
        return RedditSearchEngine(client_id=cid, client_secret=csec, user_agent=ua)
    if engine is SearchEngine.DUCKDUCKGO:
        return DuckDuckGoEngine(
            http_backend=ddg_http_backend,
            max_attempts=ddg_max_attempts,
            retry_base_seconds=ddg_retry_base_seconds,
        )
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = os.environ.get("GOOGLE_CSE_ID", "").strip()
    if not api_key or not cx:
        raise ValueError("Google requires GOOGLE_API_KEY and GOOGLE_CSE_ID.")
    return GoogleCustomSearchEngine(api_key=api_key, cx=cx)


def ensure_env_loaded() -> None:
    load_dotenv()
