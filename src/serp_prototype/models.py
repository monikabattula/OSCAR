from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SearchEngine(str, Enum):
    """Supported backends. Add new engines by implementing SerpEngine."""

    GOOGLE_CSE = "google"
    DUCKDUCKGO = "duckduckgo"
    REDDIT = "reddit"


class TimePeriod(str, Enum):
    """Preset windows. Custom ranges use query hints / engine-specific params."""

    PAST_24_HOURS = "24h"
    PAST_WEEK = "week"
    PAST_MONTH = "month"
    PAST_YEAR = "year"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class SerpHit:
    """One line in the output CSV — SERP fields; optional source creation time when the engine exposes it."""

    title: str
    author: str
    url: str
    excerpt: str
    source_created_at: str = ""  # ISO-8601 UTC when known (e.g. Reddit post time); else ""
