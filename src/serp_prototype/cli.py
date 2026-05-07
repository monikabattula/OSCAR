from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import typer
from dotenv import load_dotenv

from serp_prototype.collect_service import build_engine, ensure_env_loaded
from serp_prototype.csv_export import ExportContext, write_hits_csv
from serp_prototype.models import SearchEngine, TimePeriod

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _parse_iso_date(label: str, value: str | None) -> date | None:
    if value is None or value.strip() == "":
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as e:
        raise typer.BadParameter(f"{label} must be YYYY-MM-DD") from e


def _parse_period(
    period: str,
    start: date | None,
    end: date | None,
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
        raise typer.BadParameter(
            f"period must be one of {', '.join(sorted(mapping))}; got {period!r}"
        )
    tp = mapping[p]
    if tp is TimePeriod.CUSTOM:
        if not start or not end:
            raise typer.BadParameter("custom period requires --start-date and --end-date (YYYY-MM-DD)")
        if start > end:
            raise typer.BadParameter("start-date must be on or before end-date")
    return tp, start, end


def _engine(
    engine: SearchEngine,
    *,
    ddg_http_backend: str,
    ddg_max_attempts: int,
    ddg_retry_base_seconds: float,
):
    ensure_env_loaded()
    if engine is SearchEngine.DUCKDUCKGO:
        b = ddg_http_backend.lower().strip()
        if b not in ("lite", "html", "auto"):
            raise typer.BadParameter("--ddg-backend must be one of: lite, html, auto")
        return build_engine(
            engine,
            ddg_http_backend=b,  # type: ignore[arg-type]
            ddg_max_attempts=ddg_max_attempts,
            ddg_retry_base_seconds=ddg_retry_base_seconds,
        )
    try:
        return build_engine(
            engine,
            ddg_http_backend="lite",
            ddg_max_attempts=ddg_max_attempts,
            ddg_retry_base_seconds=ddg_retry_base_seconds,
        )
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2) from e


@app.command()
def collect(
    query: str = typer.Option(..., "--query", "-q", help="Search query, e.g. 'site:.gov maryland disability'"),
    engine: SearchEngine = typer.Option(
        SearchEngine.DUCKDUCKGO,
        "--engine",
        "-e",
        help="Search backend: google (Custom Search API), duckduckgo, reddit (OAuth2 /search).",
    ),
    period: str = typer.Option(
        "week",
        "--period",
        "-p",
        help="Time window: 24h | week | month | year | custom",
    ),
    start_date: str | None = typer.Option(
        None,
        "--start-date",
        help="For period=custom: start date (YYYY-MM-DD)",
    ),
    end_date: str | None = typer.Option(
        None,
        "--end-date",
        help="For period=custom: end date (YYYY-MM-DD)",
    ),
    max_results: int = typer.Option(
        50,
        "--max-results",
        "-n",
        help="Max SERP rows to collect (capped at 100 for this prototype)",
        min=1,
        max=100,
    ),
    output: Path = typer.Option(
        Path("out/serp_results.csv"),
        "--output",
        "-o",
        help="Output CSV path",
    ),
    ddg_backend: str = typer.Option(
        "lite",
        "--ddg-backend",
        help="DuckDuckGo only: HTTP backend (lite | html | auto).",
    ),
    ddg_retries: int = typer.Option(
        7,
        "--ddg-retries",
        help="DuckDuckGo only: max attempts on 202/ratelimit (each wait is capped at 45s).",
        min=1,
        max=12,
    ),
    ddg_retry_wait: float = typer.Option(
        6.0,
        "--ddg-retry-wait",
        help="DuckDuckGo only: backoff base seconds.",
        min=1.0,
        max=120.0,
    ),
    append: bool = typer.Option(
        False,
        "--append",
        help="Append new rows to the CSV instead of overwriting.",
    ),
    dedupe: bool = typer.Option(
        True,
        "--dedupe/--no-dedupe",
        help="When appending, skip rows whose URL already exists in the file.",
    ),
    minimal: bool = typer.Option(
        False,
        "--minimal",
        help="Export only the four SERP columns (no metadata / dates / scrape columns).",
    ),
) -> None:
    """Collect search-engine result snippets into a CSV. Does not fetch underlying webpages."""
    load_dotenv()
    sd = _parse_iso_date("start-date", start_date)
    ed = _parse_iso_date("end-date", end_date)
    tp, ds, de = _parse_period(period, sd, ed)
    serp = _engine(
        engine,
        ddg_http_backend=ddg_backend,
        ddg_max_attempts=ddg_retries,
        ddg_retry_base_seconds=ddg_retry_wait,
    )
    extra = ""
    if engine is SearchEngine.DUCKDUCKGO:
        extra = f" | ddg_backend={ddg_backend} | ddg_retries={ddg_retries}"
    typer.echo(f"Engine: {engine.value} | period: {tp.value} | max_results: {max_results}{extra}")
    hits = serp.search(query, tp, date_start=ds, date_end=de, max_results=max_results)
    ctx = ExportContext(
        query=query,
        engine=engine.value,
        period_key=tp.value,
        date_start=ds,
        date_end=de,
    )
    try:
        written, skipped = write_hits_csv(
            output,
            hits,
            ctx,
            minimal=minimal,
            append=append,
            dedupe_by_url=dedupe,
        )
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2) from e
    msg = f"Wrote {written} rows to {output.resolve()}"
    if skipped:
        msg += f" ({skipped} duplicate URLs skipped)"
    typer.echo(msg)


if __name__ == "__main__":
    app()
