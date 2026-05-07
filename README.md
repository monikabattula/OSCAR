# OSCAR — Open Source Corpus Analysis & Research

SERP prototype (search results → CSV), presented in the **OSCAR** web console.

Collects **search engine result page (SERP)** metadata only: title, URL, snippet, and author when the engine exposes it. **Does not download target webpages.**

Full requirements, research context, and CSV schema: **`SERP_COLLECTION_SPEC.md`**.

## Setup

```bash
cd serp-prototype
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Run without installing the script: `python -m serp_prototype -q "your query" ...` (from the repo root with `PYTHONPATH=src` or after `pip install -e .`).

Copy `.env.example` to `.env` and fill in:

- **Google** (`--engine google`): `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`
- **Reddit** (`--engine reddit`): `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`  
  Create a Reddit app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (script or web app). Follow [Reddit API rules](https://github.com/reddit/reddit/wiki/API) for `User-Agent`.

## Automatic run every 24 hours (macOS)

1. **Configure** what to collect (query, engine, output path):

   ```bash
   cp schedule.env.example schedule.env
   # Edit schedule.env — set SERP_QUERY, SERP_OUTPUT, etc.
   ```

2. **Install the LaunchAgent** (runs **`scripts/serp_collect_scheduled.sh`** every **86400 seconds** and once at load):

   ```bash
   chmod +x scripts/serp_collect_scheduled.sh scripts/install_launchagent_macos.sh
   bash scripts/install_launchagent_macos.sh
   ```

   - **Stop:** `launchctl unload ~/Library/LaunchAgents/com.serpprototype.serp-collect.plist`  
   - **Logs:** `out/logs/serp_scheduled.log`, plus `out/logs/launchd.out.log` / `launchd.err.log`

The script uses **`--append`** so `SERP_OUTPUT` grows over time; URL **dedupe** avoids duplicate rows when the same link appears again.

**Alternative — same time every calendar day** (not exactly 24h from last run): use **cron** with `scripts/crontab.example`.

**Note:** The machine must be **awake** for the job to run. For a server or always-on Mac, use the same pattern on that host.

## Dashboard (optional)

After you have a CSV from `serp-collect`, open the **OSCAR** web console:

```bash
serp-dashboard
```

From the repo (editable install not required if `PYTHONPATH=src`): `streamlit run src/serp_prototype/dashboard.py`

The OSCAR console has **three tabs**:

- **Search:** query box, **toggles** for Google / DuckDuckGo / Reddit, **time period**, **max results**, output path, **Run search now**.
- **Corpus:** load the CSV, **filter**, optional **scrape** of underlying pages (saved under `out/scraped/`), **save CSV**, and **in-app auto-repeat** (checked every ~60s while the app stays open) plus a **cron example** for always-on machines.
- **Insights:** summary metrics (rows/URLs/engines/date coverage), engine/domain breakdowns, a filterable results browser, and optional **Google AI Studio (Gemini)** corpus analysis.

Older single-file CSVs without the new columns can still be opened; missing fields are padded with blanks.

### Google AI Studio (Gemini) in OSCAR

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Add to `.env` (see `.env.example`):

   ```env
   GOOGLE_AI_API_KEY=your_key_here
   ```

3. Install dependencies (includes `google-generativeai`):

   ```bash
   pip install -e .
   ```

4. Run the dashboard, load a CSV in **Corpus**, open **Insights**, and click **Analyze corpus with Gemini**.

This is **separate** from Google **Custom Search** (`GOOGLE_API_KEY` + `GOOGLE_CSE_ID` on the Search tab). Optional: set `GEMINI_MODEL=gemini-2.0-flash` in `.env` to change the default model shown in the UI.

## Google (recommended for policy clarity)

1. Create a key in [Google Cloud Console](https://console.cloud.google.com/) and enable **Custom Search API**.
2. Create a [Programmable Search Engine](https://programmablesearchengine.google.com/) (can search the entire web or restricted sites).
3. Set `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` (`cx` from the control panel).

Free tier: **100 queries/day**; each query returns up to 10 hits (this tool paginates up to 100 total rows).

## DuckDuckGo

No API key. Uses the `duckduckgo-search` package. Review [DuckDuckGo terms](https://duckduckgo.com/terms) for your use case.

DuckDuckGo often returns **HTTP 202 (rate limit)** for automated requests, especially when `-n` is large (many paginated requests). This tool defaults to the **`lite`** endpoint and **retries with backoff**. If you still hit limits:

- Use **`--ddg-backend html`** or **`auto`** to try the other endpoint order.
- Increase patience: **`--ddg-retries 10 --ddg-retry-wait 15`**.
- Prefer **`--engine google`** for demos and larger `-n` (official API quotas).

## Reddit

Uses Reddit’s **OAuth2** `client_credentials` token, then **`GET https://oauth.reddit.com/search`** (global post search). Rows map to the same CSV shape: **post title**, **author**, **permalink URL**, **snippet** (selftext or link target when short).

- **`.env`:** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` (see `.env.example`).  
- **App:** [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) — use a **web app** / **script**–style app that exposes **client id** and **secret**.  
- **Time window:** `-p` maps to Reddit’s `t` filter (`day` for 24h, `week`, `month`, `year`; `custom` uses `t=all`—no native date range).  
- **Subreddit scope in the query:** e.g. `-q "subreddit:college international admissions"`.

## Usage

```bash
serp-collect -q "site:.gov maryland disability" -e duckduckgo -p week -o out/maryland.csv
serp-collect -q "university enrollment" -e google -p 24h -n 30 -o out/u.csv
serp-collect -q "international student visa" -e reddit -p week -n 25 -o out/reddit.csv
serp-collect -q "climate policy" -e duckduckgo -p custom --start-date 2025-01-01 --end-date 2025-03-01 -o out/range.csv

# Append a second run to the same CSV (skip URLs already stored)
serp-collect -q "site:.edu international admissions" -e duckduckgo -p week -o out/runs.csv --append
```

### Options

| Flag | Meaning |
|------|--------|
| `-q` / `--query` | Search string (supports `site:` operators, etc.) |
| `-e` / `--engine` | `google` \| `duckduckgo` \| `reddit` (Reddit needs `.env` — see below) |
| `-p` / `--period` | `24h` \| `week` \| `month` \| `year` \| `custom` |
| `--start-date` / `--end-date` | Required when `-p custom` (`YYYY-MM-DD`). Also appends `after:` / `before:` hints to the query. |
| `-n` / `--max-results` | 1–100 (default 50) |
| `-o` / `--output` | CSV path (default `out/serp_results.csv`) |
| `--append` | Append rows instead of overwriting (updatable log of runs). |
| `--dedupe` / `--no-dedupe` | On append, skip rows whose `url` already exists (default: dedupe on). |
| `--minimal` | Only the four SERP columns (no `collected_at_utc` / engine / query metadata). |

### CSV columns

**`--minimal` (four columns only):** `webpage_title`, `author_or_creator`, `url`, `page_excerpt`.

**Default “full” CSV (dashboard + non-`--minimal` CLI):**

1. `webpage_title`  
2. `author_or_creator`  
3. `url`  
4. `source_created_at` — post/publication time when the engine exposes it (e.g. Reddit); else empty  
5. `page_excerpt` — SERP snippet / selftext preview  

**Run metadata (same on every row from that engine pass):**

- `collected_at_utc`, `search_engine`, `search_period`, `search_query`, `custom_date_start`, `custom_date_end`

**Optional scrape columns** (filled from the **Data** tab or future tooling):

- `scraped_text_relative_path` — path to extracted text under `out/scraped/`  
- `scraped_at_utc` — when the page was fetched  
- `scrape_error` — short error string if fetch/extract failed  

Appending with a **different** column layout than the existing file is rejected; use a new `--output` or match `--minimal` to the file.

## Architecture

- `serp_prototype/engines/` — one module per backend implementing `SerpEngine`.
- `serp_prototype/cli.py` — Typer CLI.
- Add **Bing Web Search** or others later by implementing `SerpEngine` and extending `SearchEngine`.

## Limitations (prototype)

- **Custom date ranges** depend on engine support; Google CSE uses `dateRestrict` for presets and query operators for custom. DuckDuckGo uses `timelimit` for presets and query hints for custom.
- **Author** is rarely present in SERPs; field is reserved for when metadata exists.
- **Terms of use**: verify each engine’s ToS for automated queries before pitching or scaling.
