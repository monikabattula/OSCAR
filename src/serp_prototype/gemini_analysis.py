"""
Optional corpus analysis using Google AI Studio (Gemini API).

Create a key: https://aistudio.google.com/apikey
Set in .env: GOOGLE_AI_API_KEY=...
"""

from __future__ import annotations

import os
from io import StringIO
from pathlib import Path
from typing import Sequence

import pandas as pd
from dotenv import load_dotenv

DEFAULT_FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
)


def gemini_api_key() -> str:
    load_dotenv()
    key = (os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "Missing API key. Add GOOGLE_AI_API_KEY to .env (from Google AI Studio: "
            "https://aistudio.google.com/apikey )."
        )
    return key


def _compact_corpus_table(df: pd.DataFrame, *, max_rows: int, excerpt_max: int) -> str:
    """Turn dataframe into a compact text table for the model."""
    cols = [c for c in ("webpage_title", "url", "page_excerpt", "search_engine", "search_query") if c in df.columns]
    if not cols:
        cols = list(df.columns)[:8]
    sub = df[cols].head(max_rows).copy()
    if "page_excerpt" in sub.columns:
        sub["page_excerpt"] = (
            sub["page_excerpt"].astype(str).str.slice(0, excerpt_max).replace("nan", "")
        )
    buf = StringIO()
    sub.to_csv(buf, index=False)
    return buf.getvalue()


def analyze_corpus_with_gemini(
    df: pd.DataFrame,
    *,
    model_name: str,
    max_rows: int = 40,
    excerpt_max: int = 280,
    extra_instructions: str = "",
) -> str:
    """
    Send a slice of the corpus to Gemini and return markdown analysis.

    Requires: pip install google-generativeai
    """
    try:
        import google.generativeai as genai
    except ImportError as e:
        raise ImportError(
            "Install the Gemini client: pip install google-generativeai"
        ) from e

    genai.configure(api_key=gemini_api_key())
    table = _compact_corpus_table(df, max_rows=max_rows, excerpt_max=excerpt_max)
    prompt = f"""You are analyzing rows from a search-result corpus (titles, URLs, snippets, metadata).

Below is a CSV excerpt (up to {max_rows} rows). Write a concise analysis in **Markdown** with these sections:
## Executive summary
3–5 bullets on what this corpus is about.

## Themes
Bullet list of recurring themes (policy, geography, institutions, etc.) with brief evidence.

## Sources & quality
Notable domains or engines if visible; any gaps, duplicates, or missing fields you infer from the text.

## Suggested follow-up queries
3–6 concrete search queries the researcher could run next (include site: or quoted phrases where helpful).

{extra_instructions}

--- CSV excerpt ---
{table}
"""
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": 0.35, "max_output_tokens": 4096},
    )
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response. Try another model or fewer rows.")
    return text


def analyze_uploaded_csv_with_gemini(
    csv_path: str | Path,
    *,
    model_name: str,
    extra_instructions: str = "",
) -> str:
    """
    Upload a CSV file to Gemini Files API and analyze that uploaded file.
    """
    try:
        import google.generativeai as genai
    except ImportError as e:
        raise ImportError(
            "Install the Gemini client: pip install google-generativeai"
        ) from e

    p = Path(csv_path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"CSV not found: {p}")

    genai.configure(api_key=gemini_api_key())
    uploaded = genai.upload_file(path=str(p), display_name=p.name)
    prompt = (
        "You are a research analyst. Analyze the uploaded CSV file and return markdown with:\n"
        "## Executive summary (5-8 bullets)\n"
        "## Main themes/topics\n"
        "## Notable sources/domains\n"
        "## Data quality issues (duplicates, irrelevance, missing fields)\n"
        "## Recommended next search queries (10-15)\n"
        f"{extra_instructions}"
    )
    model = genai.GenerativeModel(model_name)
    try:
        resp = model.generate_content([uploaded, prompt])
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text
    finally:
        try:
            genai.delete_file(uploaded.name)
        except Exception:
            pass


def _is_quota_or_rate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "quota" in msg or "rate" in msg or "429" in msg or "resource_exhausted" in msg


def analyze_corpus_with_model_fallback(
    df: pd.DataFrame,
    *,
    preferred_model: str,
    model_fallbacks: Sequence[str] = DEFAULT_FALLBACK_MODELS,
    max_rows: int = 40,
    excerpt_max: int = 280,
    extra_instructions: str = "",
) -> tuple[str, str]:
    """Try preferred model first, then fallback models."""
    tried: list[str] = []
    models: list[str] = [preferred_model] + [m for m in model_fallbacks if m != preferred_model]
    last_error: Exception | None = None
    for model in models:
        tried.append(model)
        try:
            out = analyze_corpus_with_gemini(
                df,
                model_name=model,
                max_rows=max_rows,
                excerpt_max=excerpt_max,
                extra_instructions=extra_instructions,
            )
            return out, model
        except Exception as e:  # pragma: no cover
            last_error = e
            if not _is_quota_or_rate_error(e):
                raise
    raise RuntimeError(f"All Gemini models failed ({', '.join(tried)}): {last_error}")


def analyze_uploaded_csv_with_model_fallback(
    csv_path: str | Path,
    *,
    preferred_model: str,
    model_fallbacks: Sequence[str] = DEFAULT_FALLBACK_MODELS,
    extra_instructions: str = "",
) -> tuple[str, str]:
    """Try preferred model first, then fallback models for uploaded-file analysis."""
    tried: list[str] = []
    models: list[str] = [preferred_model] + [m for m in model_fallbacks if m != preferred_model]
    last_error: Exception | None = None
    for model in models:
        tried.append(model)
        try:
            out = analyze_uploaded_csv_with_gemini(
                csv_path,
                model_name=model,
                extra_instructions=extra_instructions,
            )
            return out, model
        except Exception as e:  # pragma: no cover
            last_error = e
            if not _is_quota_or_rate_error(e):
                raise
    raise RuntimeError(f"All Gemini models failed ({', '.join(tried)}): {last_error}")


def analyze_corpus_locally(df: pd.DataFrame, *, max_queries: int = 10) -> str:
    """No-API fallback: simple local summary from CSV."""
    d = df.copy()
    total = len(d)
    unique_urls = d["url"].astype(str).str.strip().replace("", pd.NA).dropna().nunique() if "url" in d.columns else 0
    by_engine = (
        d["search_engine"].astype(str).str.strip().replace("", "(blank)").value_counts().head(6)
        if "search_engine" in d.columns
        else pd.Series(dtype=int)
    )
    domains = (
        d["url"].astype(str).str.extract(r"https?://([^/]+)", expand=False).fillna("").str.lower().str.replace(r"^www\.", "", regex=True)
        if "url" in d.columns
        else pd.Series(dtype=str)
    )
    top_domains = domains[domains != ""].value_counts().head(8)
    queries = (
        d["search_query"].astype(str).str.strip().replace("", pd.NA).dropna().value_counts().head(max_queries)
        if "search_query" in d.columns
        else pd.Series(dtype=int)
    )
    lines = [
        "## Local fallback analysis",
        f"- Rows: **{int(total)}**",
        f"- Unique URLs: **{int(unique_urls)}**",
        "",
        "### By search engine",
    ]
    if by_engine.empty:
        lines.append("- No engine metadata found.")
    else:
        lines.extend([f"- {idx}: {int(val)}" for idx, val in by_engine.items()])
    lines += ["", "### Top domains"]
    if top_domains.empty:
        lines.append("- No valid domains found.")
    else:
        lines.extend([f"- {idx}: {int(val)}" for idx, val in top_domains.items()])
    lines += ["", "### Observed queries"]
    if queries.empty:
        lines.append("- No query metadata found.")
    else:
        lines.extend([f"- {idx} ({int(val)})" for idx, val in queries.items()])
    return "\n".join(lines)
