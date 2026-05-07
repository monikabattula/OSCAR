from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from serp_prototype.models import SerpHit

# Minimal CLI export (backwards compatible)
CSV_FIELDS_MINIMAL: tuple[str, ...] = (
    "webpage_title",
    "author_or_creator",
    "url",
    "page_excerpt",
)

# Rich result row: (a) title (b) author (c) URL (d) source creation time when known (e) excerpt
CSV_FIELDS_RESULT: tuple[str, ...] = (
    "webpage_title",
    "author_or_creator",
    "url",
    "source_created_at",
    "page_excerpt",
)

CSV_FIELDS_META: tuple[str, ...] = (
    "collected_at_utc",
    "search_engine",
    "search_period",
    "search_query",
    "custom_date_start",
    "custom_date_end",
)

# After full-page scrape from dashboard / tooling
CSV_FIELDS_SCRAPE: tuple[str, ...] = (
    "scraped_text_relative_path",
    "scraped_at_utc",
    "scrape_error",
)

CSV_FIELDS_FULL: tuple[str, ...] = CSV_FIELDS_RESULT + CSV_FIELDS_META + CSV_FIELDS_SCRAPE

# Backwards compatibility name used by older imports
CSV_FIELDS_CORE = CSV_FIELDS_MINIMAL
CSV_FIELDS = CSV_FIELDS_MINIMAL


@dataclass(frozen=True, slots=True)
class ExportContext:
    """One collection run — written on every row when using full schema."""

    query: str
    engine: str
    period_key: str  # e.g. 24h, week, month, year, custom
    date_start: date | None = None
    date_end: date | None = None


def _row_dict(hit: SerpHit, ctx: ExportContext, *, include_meta: bool, include_scrape: bool) -> dict[str, str]:
    if not include_meta:
        return {
            "webpage_title": hit.title,
            "author_or_creator": hit.author,
            "url": hit.url,
            "page_excerpt": hit.excerpt,
        }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "collected_at_utc": now,
        "search_engine": ctx.engine,
        "search_period": ctx.period_key,
        "search_query": ctx.query,
        "custom_date_start": ctx.date_start.isoformat() if ctx.date_start else "",
        "custom_date_end": ctx.date_end.isoformat() if ctx.date_end else "",
    }
    scrape = {
        "scraped_text_relative_path": "",
        "scraped_at_utc": "",
        "scrape_error": "",
    }
    out: dict[str, str] = {
        "webpage_title": hit.title,
        "author_or_creator": hit.author,
        "url": hit.url,
        "source_created_at": hit.source_created_at or "",
        "page_excerpt": hit.excerpt,
        **meta,
    }
    if include_scrape:
        out.update(scrape)
    return out


def _read_existing_urls(path: Path) -> set[str]:
    if not path.is_file() or path.stat().st_size == 0:
        return set()
    out: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or "url" not in r.fieldnames:
            return out
        for row in r:
            u = (row.get("url") or "").strip()
            if u:
                out.add(u)
    return out


def _header_matches(path: Path, expected: tuple[str, ...]) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return True
    with path.open(encoding="utf-8") as f:
        first = f.readline().strip()
    if not first:
        return True
    got = next(csv.reader([first]))
    return tuple(got) == expected


def write_hits_csv(
    path: Path,
    hits: list[SerpHit],
    ctx: ExportContext,
    *,
    minimal: bool = False,
    append: bool = False,
    dedupe_by_url: bool = True,
) -> tuple[int, int]:
    """
    Write SERP rows to CSV.

    Returns (rows_written, rows_skipped_duplicate).
    """
    if minimal:
        fields: tuple[str, ...] = CSV_FIELDS_MINIMAL
        include_meta = False
        include_scrape = False
    else:
        fields = CSV_FIELDS_FULL
        include_meta = True
        include_scrape = True

    path.parent.mkdir(parents=True, exist_ok=True)

    existing_urls: set[str] = set()
    if append and dedupe_by_url and path.is_file():
        existing_urls = _read_existing_urls(path)

    to_write: list[SerpHit] = []
    skipped = 0
    for h in hits:
        u = (h.url or "").strip()
        if append and dedupe_by_url and u and u in existing_urls:
            skipped += 1
            continue
        to_write.append(h)
        if u:
            existing_urls.add(u)

    if append and path.is_file() and path.stat().st_size > 0 and not _header_matches(path, fields):
        raise ValueError(
            f"Cannot append: existing CSV header does not match expected columns. "
            f"Expected {list(fields)}. Use a new --output path, or match --minimal with the file."
        )

    mode = "a" if append and path.is_file() and path.stat().st_size > 0 else "w"
    write_header = mode == "w"

    with path.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            w.writeheader()
        for h in to_write:
            w.writerow(_row_dict(h, ctx, include_meta=include_meta, include_scrape=include_scrape))

    return len(to_write), skipped
