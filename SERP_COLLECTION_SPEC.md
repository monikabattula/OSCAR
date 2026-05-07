# SERP collection prototype — requirements & research context

## Functional requirements (prototype)

1. **Search engine choice**  
   Select backend via `--engine`: **Google** (Custom Search JSON API), **DuckDuckGo** (`duckduckgo-search`), or **Reddit** (official OAuth2 client-credentials + `/search`). **Respect each provider’s terms of use** and Reddit’s [API rules](https://github.com/reddit/reddit/wiki/API) before production or scaled use.

2. **Search query**  
   User-supplied string (e.g. `site:.gov maryland disability` for health-policy OSINT, or university / recruitment queries). Passed as `-q` / `--query`.

3. **Time period**  
   Presets: past **24 hours**, **week**, **month**, **year**; or **custom** range with `--start-date` and `--end-date` (`YYYY-MM-DD`). Passed as `-p` / `--period`.

4. **Output file**  
   **CSV** with fields derived **only from the search engine results page (SERP)** — not from fetching destination webpages:
   - **(1)** `webpage_title`
   - **(2)** `author_or_creator` (when the engine exposes it; often empty)
   - **(3)** `url`
   - **(4)** `page_excerpt` (snippet from the SERP)

5. **No full-page scraping**  
   The tool does **not** download or parse target HTML pages in this phase.

6. **Updatable CSV (runs over time)**  
   Default export adds **metadata columns** on every row so files stay **mergeable and auditable**:
   - `collected_at_utc`, `search_engine`, `search_period`, `search_query`, `custom_date_start`, `custom_date_end`  
   Use **`--append`** to add new rows without overwriting prior runs; **`--dedupe`** (default on append) skips URLs already present. Use **`--minimal`** only if you need strictly four columns and no metadata.

7. **Automatic scheduling (every 24 hours)**  
   On macOS, use **`scripts/install_launchagent_macos.sh`** with **`schedule.env`** (from `schedule.env.example`) to run **`scripts/serp_collect_scheduled.sh`** on a **86400-second** interval via **launchd**. For “same clock time daily” instead, use **cron** (`scripts/crontab.example`). See the project **README**.

---

## Research focus (narrative analysis / OSINT)

I conduct **open-source research**: the systematic collection, evaluation, and analysis of **publicly available** information (not classified or proprietary) to produce actionable insights. That includes data from websites, social media, and public records to inform decision-making, detect threats, or assist with investigations.

I am developing an **AI-assisted narrative analysis** tool that processes open sources to determine **how messaging evolves** across **state-affiliated**, **commercial**, and **social media** ecosystems. Engineering support is especially useful for **responsible collection** (APIs and compliant scraping patterns) and **AI-assisted analysis** of structured outputs such as SERP-derived corpora.

---

## Problem this line of work can address (universities)

Universities need to understand **who their current and prospective students are** to promote the institution and improve enrollment. A downstream system can track **student sentiment** regarding the university and surface signals relevant to **international** interest in applying—always with **privacy- and policy-aligned** aggregation.

---

## Commercial / social impact

The broader tool can help universities **focus advertising and recruitment**, identify demographic and geographic patterns (including international audiences) for further outreach, and support **diversity goals** in line with **evolving admissions policies** and compliance constraints.

---

## Short description (50–100 words)

My AI-assisted narrative analysis tool tracks online student sentiment and application-related discussions to help universities better understand their current and prospective student populations. By analyzing digital forums, social media, and international platforms, the tool identifies emerging patterns of student interest and demographic trends. This insight enables universities to focus recruitment and advertising more effectively, optimize enrollment strategies, and pursue student diversity goals in ways that remain aligned with evolving admissions policies.

---

## CSV schema reference (default export)

| Column | Description |
|--------|-------------|
| `webpage_title` | Title from SERP |
| `author_or_creator` | Author if provided by engine metadata |
| `url` | Result URL |
| `page_excerpt` | Snippet from SERP |
| `collected_at_utc` | ISO time (UTC) when the row was written |
| `search_engine` | e.g. `google`, `duckduckgo` |
| `search_period` | `24h`, `week`, `month`, `year`, `custom` |
| `search_query` | Query string for this run |
| `custom_date_start` | Set for `custom` period; else empty |
| `custom_date_end` | Set for `custom` period; else empty |

---

## Commands (summary)

```bash
# Full schema (default), new file
serp-collect -q "site:.gov maryland disability" -e duckduckgo -p week -o data/policy.csv

# Append another run; skip URLs already in the file
serp-collect -q "site:.gov maryland health" -e google -p month -o data/policy.csv --append

# Four columns only
serp-collect -q "..." -e duckduckgo -p week -o out/min.csv --minimal
```
