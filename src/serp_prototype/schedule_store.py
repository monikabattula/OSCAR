from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class DashboardSchedule:
    """Persisted preferences for repeating searches from the dashboard."""

    enabled: bool = False
    interval_hours: float = 24.0
    query: str = ""
    engines: list[str] | None = None
    period: str = "week"
    max_results: int = 25
    output_csv: str = "out/dashboard_results.csv"
    dedupe_urls: bool = True
    ddg_reddit_site_boost: bool = False
    last_run_utc: str | None = None
    next_run_utc: str | None = None

    def __post_init__(self) -> None:
        if self.engines is None:
            self.engines = ["duckduckgo"]


def schedule_path(project_root: Path) -> Path:
    return project_root / "out" / "dashboard_schedule.json"


def load_schedule(project_root: Path) -> DashboardSchedule:
    p = schedule_path(project_root)
    if not p.is_file():
        return DashboardSchedule()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DashboardSchedule()
    return DashboardSchedule(
        enabled=bool(raw.get("enabled", False)),
        interval_hours=float(raw.get("interval_hours", 24)),
        query=str(raw.get("query", "")),
        engines=list(raw.get("engines") or ["duckduckgo"]),
        period=str(raw.get("period", "week")),
        max_results=int(raw.get("max_results", 25)),
        output_csv=str(raw.get("output_csv", "out/dashboard_results.csv")),
        dedupe_urls=bool(raw.get("dedupe_urls", True)),
        ddg_reddit_site_boost=bool(raw.get("ddg_reddit_site_boost", False)),
        last_run_utc=raw.get("last_run_utc"),
        next_run_utc=raw.get("next_run_utc"),
    )


def save_schedule(project_root: Path, s: DashboardSchedule) -> None:
    p = schedule_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        t = s.strip()
        if t.endswith("Z"):
            t = t[:-1] + "+00:00"
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def bump_next_run(s: DashboardSchedule) -> DashboardSchedule:
    now = datetime.now(timezone.utc)
    delta = timedelta(hours=float(s.interval_hours))
    nxt = now + delta
    return DashboardSchedule(
        enabled=s.enabled,
        interval_hours=s.interval_hours,
        query=s.query,
        engines=list(s.engines or []),
        period=s.period,
        max_results=s.max_results,
        output_csv=s.output_csv,
        dedupe_urls=s.dedupe_urls,
        ddg_reddit_site_boost=s.ddg_reddit_site_boost,
        last_run_utc=utc_now_iso(),
        next_run_utc=nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def is_due(s: DashboardSchedule) -> bool:
    if not s.enabled or not (s.query or "").strip():
        return False
    nxt = parse_iso(s.next_run_utc)
    if nxt is None:
        return True
    return datetime.now(timezone.utc) >= nxt
