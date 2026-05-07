from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from serp_prototype.collect_service import build_engine, ensure_env_loaded
from serp_prototype.csv_export import CSV_FIELDS_FULL, ExportContext, write_hits_csv
from serp_prototype.models import SearchEngine, TimePeriod
from serp_prototype.scraping import fetch_and_extract_text, save_scraped_text


def repo_root() -> Path:
    """Project root (directory containing `src/`)."""
    return Path(__file__).resolve().parents[2]


def _parse_iso_date(label: str, value: str | None) -> date | None:
    if value is None or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"{label} must be YYYY-MM-DD") from e


def parse_period_inputs(
    period: str,
    start_s: str | None,
    end_s: str | None,
) -> tuple[TimePeriod, date | None, date | None]:
    p = period.lower().strip()
    mapping = {
        "24h": TimePeriod.PAST_24_HOURS,
        "day": TimePeriod.PAST_24_HOURS,
        "week": TimePeriod.PAST_WEEK,
        "month": TimePeriod.PAST_MONTH,
        "year": TimePeriod.PAST_YEAR,
        "custom": TimePeriod.CUSTOM,
        
    }
    if p not in mapping:
        raise ValueError(f"Unknown period {period!r}")
    tp = mapping[p]
    sd = _parse_iso_date("start-date", start_s)
    ed = _parse_iso_date("end-date", end_s)
    if tp is TimePeriod.CUSTOM:
        if not sd or not ed:
            raise ValueError("custom period requires start and end dates (YYYY-MM-DD)")
        if sd > ed:
            raise ValueError("start-date must be on or before end-date")
    return tp, sd, ed


def resolve_output_path(project_root: Path, output_csv: str) -> Path:
    p = Path(output_csv)
    if p.is_absolute():
        return p
    return (project_root / output_csv).resolve()


def _query_terms(query: str) -> list[str]:
    """Extract meaningful query terms and ignore search operators."""
    phrase_or_word = re.findall(r'"([^"]+)"|(\S+)', query)
    terms: list[str] = []
    for quoted, word in phrase_or_word:
        token = (quoted or word).strip().lower()
        if not token:
            continue
        if ":" in token:
            op = token.split(":", 1)[0]
            if op in {"site", "after", "before", "subreddit"}:
                continue
        token = re.sub(r"^[^\w]+|[^\w]+$", "", token)
        if len(token) >= 2:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _filter_and_rank_relevance(hits: list, query: str) -> list:
    """Keep only hits related to query terms and rank best matches first."""
    terms = _query_terms(query)
    if not terms:
        return hits
    scored: list[tuple[int, object]] = []
    for h in hits:
        title = str(getattr(h, "title", "") or "").lower()
        excerpt = str(getattr(h, "excerpt", "") or "").lower()
        url = str(getattr(h, "url", "") or "").lower()
        hay = f"{title} {excerpt} {url}"
        present = [t for t in terms if t in hay]
        if not present:
            continue
        score = 0
        for t in present:
            score += 3 if t in title else 0
            score += 2 if t in excerpt else 0
            score += 1 if t in url else 0
        # Prefer rows that satisfy more query terms.
        score += 5 * len(present)
        scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored]


def _is_reddit_url(url: str) -> bool:
    u = (url or "").lower()
    return "reddit.com/r/" in u or "redd.it/" in u


def run_search_job(
    project_root: Path,
    *,
    query: str,
    engines: list[str],
    period: str,
    start_s: str | None,
    end_s: str | None,
    max_results: int,
    output_csv: str,
    append: bool,
    dedupe: bool,
    strict_relevance: bool = True,
    fast_retrieval: bool = True,
) -> tuple[list[str], int]:
    """Run one or more engines and write CSV (full schema). Returns (log lines, total rows written)."""
    logs: list[str] = []
    total_written = 0
    if not engines:
        return ["No engines selected."], 0
    ensure_env_loaded()
    tp, ds, de = parse_period_inputs(period, start_s, end_s)
    outp = resolve_output_path(project_root, output_csv)
    # Honor the user's requested max results; fast mode affects retry behavior only.
    effective_max = max_results

    for i, eng in enumerate(engines):
        try:
            se = SearchEngine(eng)
        except ValueError:
            logs.append(f"Unknown engine skipped: {eng}")
            continue
        try:
            backend = build_engine(
                se,
                ddg_http_backend="auto",
                ddg_max_attempts=2 if fast_retrieval else 4,
                ddg_retry_base_seconds=1.5 if fast_retrieval else 4.0,
            )
        except ValueError as e:
            logs.append(f"{eng}: {e}")
            continue
        try:
            hits = backend.search(query, tp, date_start=ds, date_end=de, max_results=effective_max)
        except Exception as e:
            msg = str(e).strip()
            if "Ratelimit" in msg or "202" in msg:
                logs.append(
                    f"{eng}: rate-limited by provider; try fewer results, wait briefly, or use Google. ({msg})"
                )
            else:
                logs.append(f"{eng}: search failed ({msg})")
            continue
        before = len(hits)
        if strict_relevance:
            hits = _filter_and_rank_relevance(hits, query)
        filtered = before - len(hits)
        ctx = ExportContext(
            query=query,
            engine=se.value,
            period_key=tp.value,
            date_start=ds,
            date_end=de,
        )
        append_mode = append if i == 0 else True
        note = f"; filtered {filtered} low-relevance row(s)" if strict_relevance else ""

        # Additional layer: when using DuckDuckGo, tag Reddit threads separately
        # so they can be filtered/scraped as Reddit-derived context.
        if se is SearchEngine.DUCKDUCKGO:
            reddit_hits = [h for h in hits if _is_reddit_url(getattr(h, "url", ""))]
            non_reddit_hits = [h for h in hits if not _is_reddit_url(getattr(h, "url", ""))]

            w_total = 0
            sk_total = 0

            if non_reddit_hits:
                w1, sk1 = write_hits_csv(
                    outp,
                    non_reddit_hits,
                    ctx,
                    minimal=False,
                    append=append_mode,
                    dedupe_by_url=dedupe,
                )
                w_total += w1
                sk_total += sk1
                append_mode = True

            if reddit_hits:
                reddit_ctx = ExportContext(
                    query=query,
                    engine="reddit_via_duckduckgo",
                    period_key=tp.value,
                    date_start=ds,
                    date_end=de,
                )
                w2, sk2 = write_hits_csv(
                    outp,
                    reddit_hits,
                    reddit_ctx,
                    minimal=False,
                    append=append_mode,
                    dedupe_by_url=dedupe,
                )
                w_total += w2
                sk_total += sk2

            total_written += w_total
            logs.append(
                f"{eng}: wrote {w_total} row(s); skipped {sk_total} duplicate URL(s)"
                f"{note}; reddit-thread rows tagged as `reddit_via_duckduckgo` → {outp}"
            )
        else:
            w, sk = write_hits_csv(
                outp,
                hits,
                ctx,
                minimal=False,
                append=append_mode,
                dedupe_by_url=dedupe,
            )
            total_written += w
            logs.append(f"{eng}: wrote {w} row(s); skipped {sk} duplicate URL(s){note} → {outp}")
    return logs, total_written


def normalize_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in CSV_FIELDS_FULL:
        if c not in df.columns:
            df[c] = ""
    ordered = [c for c in CSV_FIELDS_FULL if c in df.columns]
    extra = [c for c in df.columns if c not in CSV_FIELDS_FULL]
    return df[ordered + extra]


def scrape_dataframe_urls(
    project_root: Path,
    df: pd.DataFrame,
    max_pages: int,
) -> tuple[pd.DataFrame, list[str]]:
    """Scrape up to max_pages rows that have a URL and no scraped file yet."""
    df = df.copy()
    df = normalize_df_columns(df)
    logs: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    done = 0
    for idx in df.index:
        if done >= max_pages:
            break
        url = str(df.at[idx, "url"] or "").strip()
        if not url.startswith("http"):
            continue
        existing = str(df.at[idx, "scraped_text_relative_path"] or "").strip()
        if existing:
            continue
        text, err = fetch_and_extract_text(url)
        if err:
            df.loc[idx, "scrape_error"] = err[:500]
            df.loc[idx, "scraped_at_utc"] = now
            logs.append(f"FAIL {url[:60]}… → {err}")
        else:
            rel = save_scraped_text(project_root, url, text)
            df.loc[idx, "scraped_text_relative_path"] = rel
            df.loc[idx, "scraped_at_utc"] = now
            df.loc[idx, "scrape_error"] = ""
            logs.append(f"OK {url[:60]}… → {rel}")
        done += 1
    return df, logs


def save_dataframe_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df_out = normalize_df_columns(df)
    df_out.to_csv(path, index=False, encoding="utf-8")
