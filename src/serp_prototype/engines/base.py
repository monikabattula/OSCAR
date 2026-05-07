from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from serp_prototype.models import SerpHit, TimePeriod


class SerpEngine(ABC):
    """Pluggable search backend. Implementations only use official APIs or documented SDKs."""

    name: str

    @abstractmethod
    def search(
        self,
        query: str,
        period: TimePeriod,
        *,
        date_start: date | None = None,
        date_end: date | None = None,
        max_results: int = 50,
    ) -> list[SerpHit]:
        """Return SERP rows (title, optional author, url, snippet)."""
