from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import trafilatura

DEFAULT_UA = (
    "serp-prototype/0.1 (+https://github.com/) research-fetch; respects robots.txt where applicable"
)


def _safe_slug(url: str) -> str:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return h


def fetch_and_extract_text(
    url: str,
    *,
    timeout: float = 25.0,
    max_chars: int = 200_000,
) -> tuple[str, str]:
    """
    Download URL and extract main text with trafilatura.

    Returns (text, error_message). On success error_message is "".
    """
    u = (url or "").strip()
    if not u or not u.startswith(("http://", "https://")):
        return "", "invalid_or_non_http_url"
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": DEFAULT_UA},
            follow_redirects=True,
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        return "", f"download:{type(e).__name__}:{e}"

    try:
        text = trafilatura.extract(html, url=u, include_comments=False, include_tables=False)
    except Exception as e:
        return "", f"extract:{type(e).__name__}:{e}"

    if not text or not str(text).strip():
        return "", "empty_extract"

    text = str(text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…[truncated]"
    return text, ""


def save_scraped_text(project_root: Path, url: str, text: str) -> str:
    """Write text under project_root/out/scraped/. Returns relative path from project_root."""
    out_dir = project_root / "out" / "scraped"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{_safe_slug(url)}.txt"
    path = out_dir / fname
    path.write_text(text, encoding="utf-8")
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def sanitize_filename_part(s: str, max_len: int = 40) -> str:
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return (s[:max_len] or "row") if s else "row"
