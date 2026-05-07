# OSCAR Development Documentation

## 1) Project Overview

**OSCAR (Open Source Corpus Analysis & Research)** is a Streamlit-based research workflow application that collects, organizes, enriches, and analyzes search-result data from multiple engines.

It was developed iteratively from a basic SERP collector into a full workflow system:

**collect -> organize -> scrape -> analyze -> monitor**

---

## 2) Main Objective

The app helps a researcher:

- run topic-based searches across multiple engines
- store results in a standardized CSV format
- filter and manage a corpus
- scrape page-level text from selected URLs
- generate insights and AI-assisted analysis from collected data

---

## 3) System Architecture

OSCAR is organized into layers:

- **UI Layer**: `src/serp_prototype/dashboard.py`
- **Action/Service Layer**: `src/serp_prototype/dash_actions.py`
- **Search Engine Adapters**: `src/serp_prototype/engines/`
- **CSV Schema/Export Layer**: `src/serp_prototype/csv_export.py`
- **Scheduling Layer**: `src/serp_prototype/schedule_store.py`
- **AI Analysis Layer**: `src/serp_prototype/gemini_analysis.py`
- **CLI/Launcher**: `src/serp_prototype/cli.py`, `dashboard_launcher.py`

---

## 4) Search Collection Pipeline

When a user clicks **Run search**:

1. UI gathers:
   - query
   - selected engines
   - time period/date range
   - max result count
   - retrieval/relevance options
2. UI calls `run_search_job(...)` in `dash_actions.py`.
3. `run_search_job(...)`:
   - loads environment variables (`.env`)
   - parses period/date constraints
   - builds engine-specific clients via `build_engine(...)`
   - fetches SERP hits from selected engines
   - optionally filters/ranks relevance
   - writes normalized rows to CSV
4. UI reloads latest output CSV into session state for immediate visibility.

---

## 5) Engines Integrated

- **Google Custom Search API**
- **DuckDuckGo**
- **Reddit OAuth search**

All engine outputs are converted into a shared record format so downstream workflow stays consistent.

---

## 6) CSV Data Model

Core result fields:

- `webpage_title`
- `author_or_creator`
- `url`
- `source_created_at`
- `page_excerpt`

Run metadata:

- `search_engine`
- `search_query`
- `search_period`
- `collected_at_utc`
- date-range metadata fields

Scrape metadata:

- `scraped_text_relative_path`
- `scraped_at_utc`
- `scrape_error`

This schema enables reproducibility and easy analysis.

---

## 7) Corpus Management Features

In the **Corpus** tab, OSCAR provides:

- CSV load/refresh with optional auto-load
- dataset metrics (rows, unique URLs, scraped count, errors)
- full-text filtering
- engine filtering
- "unscraped only" filtering
- data table preview
- save and CSV download

This turns raw search output into a manageable research corpus.

---

## 8) Scraping Layer

Scraping workflow:

1. User chooses max pages to scrape.
2. Scrape is locked to latest query rows (to avoid irrelevant scraping).
3. URLs are fetched and cleaned text is extracted.
4. Text files are saved under `out/scraped/`.
5. Scrape columns are merged back into in-memory dataframe.
6. User can persist updates to CSV.

---

## 9) Insights Layer

In the **Insights** tab, OSCAR includes:

- summary cards (rows, unique URLs, engines, date coverage)
- engine distribution
- top domain aggregation
- row browser with filtering

This supports quick exploratory analysis before deep AI analysis.

---

## 10) Google AI Studio / Gemini Integration

Two analysis modes are implemented:

1. **Direct corpus analysis**
   - sends a selected dataframe slice to Gemini.

2. **Uploaded CSV analysis**
   - uploads CSV to Gemini Files API.
   - prompts Gemini to analyze uploaded file content.
   - saves markdown output locally.

Additional reliability features:

- model selection (including `gemini-2.5-flash`)
- model fallback chain
- local non-API fallback when quota/rate limits fail
- clear indication of analysis source used

---

## 11) Reliability and Error-Handling Improvements

The app was hardened through multiple fixes:

- `.env` formatting and key-loading corrections
- Google CSE ID (`cx`) format validation guidance
- detailed Google API error surfacing (403/accessNotConfigured reasoning)
- DuckDuckGo rate-limit handling with non-crashing behavior
- Streamlit data editor dtype compatibility fixes
- safer scrape-index merge logic
- stale/mixed data prevention through latest-run loading behavior

---

## 12) Advanced Source Layering

A custom enhancement was added for DuckDuckGo:

- Reddit thread links found via DuckDuckGo are tagged separately as:
  - `reddit_via_duckduckgo`

This enables dedicated filtering/scraping of Reddit-thread context discovered through DDG.

---

## 13) UI/UX Development Evolution

Frontend evolved from a basic utility UI into a cleaner branded interface:

- OSCAR branding/theme
- About-page flow with navigation
- alignment and readability fixes
- minimal search-landing style improvements
- refined search bar layout and styling

The current UI prioritizes research workflow usability while retaining all operational controls.

---

## 14) End-to-End Workflow

1. Enter query in **Search**.
2. Collect results into CSV.
3. Auto-load latest output in **Corpus**.
4. Filter and scrape selected rows.
5. Save/export enriched corpus.
6. Review metrics in **Insights**.
7. Run Gemini analysis (or local fallback).
8. Repeat manually or via schedule.

---

## 15) Technology Stack

- Python 3.x
- Streamlit (frontend)
- Pandas (data processing)
- python-dotenv (config)
- Typer (CLI)
- Trafilatura (text extraction)
- Google Generative AI SDK (Gemini)
- engine-specific HTTP/search libraries

---

## 16) Conclusion

OSCAR now functions as a practical, modular research system for multi-engine collection and analysis.  
It supports reproducible CSV-based workflows, optional page scraping, scheduled updates, and AI-assisted interpretation with resilient fallbacks.

