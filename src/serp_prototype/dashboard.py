"""
OSCAR — Open Source Corpus Analysis & Research (Streamlit console).

Run: streamlit run src/serp_prototype/dashboard.py
  or: serp-dashboard
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from serp_prototype.dash_actions import (
    normalize_df_columns,
    repo_root,
    run_search_job,
    save_dataframe_csv,
    scrape_dataframe_urls,
)
from serp_prototype.gemini_analysis import (
    analyze_corpus_locally,
    analyze_corpus_with_model_fallback,
    analyze_uploaded_csv_with_model_fallback,
)
from serp_prototype.schedule_store import (
    bump_next_run,
    is_due,
    load_schedule,
    save_schedule,
    utc_now_iso,
)

OSCAR_CSS = """
<style>
    .stApp {
        background: radial-gradient(circle at 20% 0%, #f3f4f6 0%, #eef2ff 42%, #f8fafc 100%);
        color: #111827;
    }
    .block-container { padding-top: 1.15rem; padding-bottom: 2.5rem; max-width: 1100px; }
    [data-testid="stHeader"] { background: rgba(0,0,0,0); }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e5e7eb; }
    .oscar-hero {
        background: transparent;
        color: #111827;
        padding: 0.4rem 0.8rem 0.8rem 0.8rem;
        border-radius: 0;
        margin: 0 auto 0.35rem auto;
        max-width: 740px;
        text-align: center;
        border: 0;
        box-shadow: none;
    }
    .oscar-hero h1 {
        font-size: 3.8rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0.45rem 0 0.25rem 0;
        color: #0b0f19;
        text-transform: none;
    }
    .oscar-hero .acronym {
        color: #6b7280;
        font-size: 1.02rem;
        font-weight: 400;
        letter-spacing: 0.01em;
        margin: 0;
        line-height: 1.3;
    }
    .oscar-hero .acronym strong { color: #374151; font-weight: 600; }
    .oscar-badge {
        display: inline-block;
        border: 1px solid #d1d5db;
        color: #6b7280;
        font-size: 0.72rem;
        border-radius: 999px;
        padding: 0.28rem 0.65rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        font-weight: 700;
        background: #ffffff;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.3rem;
        background: rgba(255, 255, 255, 0.8);
        padding: 0.3rem 0.4rem;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        border-radius: 10px;
        color: #374151;
        font-weight: 500;
    }
    div[data-testid="stTabs"] [aria-selected="true"] {
        background: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #d1d5db;
    }
    .oscar-section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #111827;
        margin: 0 0 0.25rem 0;
    }
    .oscar-muted {
        font-size: 0.82rem;
        color: #6b7280;
        margin-bottom: 0.8rem;
    }
    label, .stCaption, .stMarkdown, .stText, .stSelectbox label, .stNumberInput label,
    .stTextInput label, .stToggle label, .stCheckbox label {
        color: #374151 !important;
    }
    [data-baseweb="input"] input, [data-baseweb="select"] div, textarea {
        background: rgba(255, 255, 255, 0.96) !important;
        color: #111827 !important;
    }
    [data-baseweb="input"] input::placeholder, textarea::placeholder {
        color: #6b7280 !important;
    }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        background: #ffffff;
    }
    [data-testid="stMetric"] { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 0.7rem 0.85rem; }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: #111827; }
    [data-testid="stVerticalBlock"] div[role="group"] { border-radius: 12px; }
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; }
    .stButton > button, .stDownloadButton > button {
        border-radius: 999px;
        border: 1px solid #d1d5db;
        background: #ffffff;
        color: #111827;
    }
    .stButton > button[kind="primary"] {
        background: #111827;
        border-color: #111827;
        color: #fff;
    }
    .st-key-oscar_about_open button {
        white-space: nowrap !important;
        min-width: 92px !important;
        text-align: center !important;
    }
    .oscar-search-shell {
        max-width: 760px;
        margin: 0 auto;
        text-align: center;
    }
    .oscar-engines-note { font-size: 0.8rem; color: #6b7280; margin-top: 0.3rem; }
    .st-key-engine_google label,
    .st-key-engine_reddit label,
    .st-key-engine_ddg label,
    .st-key-engine_google label p,
    .st-key-engine_reddit label p,
    .st-key-engine_ddg label p {
        color: #374151 !important;
        font-weight: 500 !important;
    }
    .st-key-engine_google label[data-baseweb="checkbox"] > div:first-child,
    .st-key-engine_reddit label[data-baseweb="checkbox"] > div:first-child,
    .st-key-engine_ddg label[data-baseweb="checkbox"] > div:first-child {
        background-color: #d1d5db !important;
    }
    .st-key-engine_google label[data-baseweb="checkbox"]:has(input:checked) > div:first-child,
    .st-key-engine_reddit label[data-baseweb="checkbox"]:has(input:checked) > div:first-child,
    .st-key-engine_ddg label[data-baseweb="checkbox"]:has(input:checked) > div:first-child {
        background-color: #6b7280 !important;
    }
    .st-key-search_query [data-baseweb="input"] {
        border-radius: 16px !important;
        border: 1px solid #e5e7eb !important;
        box-shadow: 0 2px 8px rgba(17, 24, 39, 0.08);
        background: #ffffff !important;
        overflow: hidden;
    }
    .st-key-search_query [data-baseweb="input"] input {
        font-size: 1.45rem !important;
        line-height: 1.5 !important;
        padding: 20px 56px 20px 20px !important;
        color: #111827 !important;
        background: #ffffff !important;
    }
    .st-key-search_query [data-baseweb="input"] input::placeholder {
        color: #9ca3af !important;
        font-weight: 500;
    }
    .oscar-search-icon {
        position: relative;
        margin-top: -46px;
        margin-right: 16px;
        text-align: right;
        color: #c4c8d1;
        font-size: 22px;
        pointer-events: none;
    }
</style>
"""


def _inject_oscar_styles() -> None:
    st.markdown(OSCAR_CSS, unsafe_allow_html=True)


def _oscar_hero() -> None:
    st.markdown(
        """
<div class="oscar-hero">
    <span class="oscar-badge">Search Assistant</span>
    <h1>OSCAR</h1>
    <p class="acronym">Multi-engine search made simple.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="OSCAR",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOT = repo_root()


def _interval_hours(label: str) -> float:
    return {"Hourly": 1.0, "Daily": 24.0, "Weekly": 168.0, "Monthly": 720.0}[label]


def _cron_snippet(root: Path, interval_label: str) -> str:
    """Example cron line invoking the scheduled shell script (daily at 06:00)."""
    hrs = _interval_hours(interval_label)
    if hrs <= 1:
        return f"0 * * * * {root}/scripts/serp_collect_scheduled.sh"
    if hrs <= 24:
        return f"0 6 * * * {root}/scripts/serp_collect_scheduled.sh"
    return f"0 6 * * 0 {root}/scripts/serp_collect_scheduled.sh"


@st.fragment(run_every=timedelta(seconds=60))
def _scheduled_tick() -> None:
    """Background-style tick: runs saved schedule when due (app must stay running)."""
    sch = load_schedule(ROOT)
    if not is_due(sch):
        return
    per = sch.period
    s1, s2 = None, None
    if per == "custom":
        # Stored schedule has no custom date range yet — fall back to week for auto-runs.
        per = "week"
    try:
        logs, n = run_search_job(
            ROOT,
            query=sch.query,
            engines=list(sch.engines or []),
            period=per,
            start_s=s1,
            end_s=s2,
            max_results=int(sch.max_results),
            output_csv=sch.output_csv,
            append=True,
            dedupe=sch.dedupe_urls,
            ddg_reddit_site_boost=sch.ddg_reddit_site_boost,
        )
    except Exception as e:
        st.session_state["_sched_last"] = f"Schedule error: {e}"
        return
    sch2 = bump_next_run(sch)
    save_schedule(ROOT, sch2)
    st.session_state["_sched_last"] = (
        f"Auto-run wrote **{n}** row(s). Logs:\n" + "\n".join(logs[-6:])
    )


def main() -> None:
    _inject_oscar_styles()

    if "oscar_show_about" not in st.session_state:
        st.session_state.oscar_show_about = False

    # Avoid stale URL (?about=1) without Streamlit rerun — sync once into session.
    about_qp = str(st.query_params.get("about", "")).strip().lower()
    if about_qp in {"1", "true", "yes"}:
        st.session_state.oscar_show_about = True
        try:
            del st.query_params["about"]
        except Exception:
            pass

    if st.session_state.oscar_show_about:
        st.markdown("## About OSCAR")
        with st.container(border=True):
            st.markdown(
                """
OSCAR (**Open Source Corpus Analysis & Research**) is a research collection app that helps you discover, organize, and review web-source evidence around a topic.

- Collects SERP results from **Google**, **DuckDuckGo**, and **Reddit** for your query  
- Saves structured output to CSV (title, URL, excerpt, source date, engine, query metadata)  
- Lets you review/filter the corpus, scrape page text, and export updated files  
- Supports scheduled repeat collection for ongoing monitoring  
- Provides Insights summaries and optional **Gemini analysis** on loaded corpus data
"""
            )
            st.markdown("### Main workflow")
            st.markdown(
                """
1. Go to **Search** and enter your topic query.  
2. Collect results from one or more engines.  
3. Open **Corpus** to filter, scrape, and export results.  
4. Open **Insights** for summary metrics and optional AI analysis.
"""
            )
        if st.button("← Back to app", key="oscar_about_close"):
            st.session_state.oscar_show_about = False
            st.rerun()
        _scheduled_tick()
        return

    nav_left, _ = st.columns([3, 12])
    with nav_left:
        if st.button("About", key="oscar_about_open"):
            st.session_state.oscar_show_about = True
            st.rerun()

    _oscar_hero()

    tab_search, tab_data, tab_results = st.tabs(["Search", "Corpus", "Insights"])

    with tab_search:
        st.markdown('<div class="oscar-search-shell">', unsafe_allow_html=True)
        q = st.text_input(
            "Search terms",
            value=st.session_state.get("_q", ""),
            key="search_query",
            placeholder="Start your hunt...",
            label_visibility="collapsed",
        )
        st.markdown('<div class="oscar-search-icon">⌕</div>', unsafe_allow_html=True)
        st.session_state["_q"] = q

        c1, c2, c3 = st.columns(3)
        with c1:
            use_google = st.toggle("Google", value=st.session_state.get("tg", False), key="engine_google")
        with c2:
            use_reddit = st.toggle("Reddit", value=st.session_state.get("tr", False), key="engine_reddit")
        with c3:
            use_ddg = st.toggle("DuckDuckGo", value=st.session_state.get("td", True), key="engine_ddg")
        st.session_state.update(tg=use_google, td=use_ddg, tr=use_reddit)
        st.markdown('<div class="oscar-engines-note">Select one or more engines</div>', unsafe_allow_html=True)

        engines: list[str] = []
        if use_google:
            engines.append("google")
        if use_ddg:
            engines.append("duckduckgo")
        if use_reddit:
            engines.append("reddit")

        with st.expander("Advanced search options", expanded=False):
            row_a, row_b = st.columns([1, 1])
            with row_a:
                period = st.selectbox(
                    "Time period",
                    ["24h", "week", "month", "year", "custom"],
                    index=1,
                )
            with row_b:
                max_n = st.number_input(
                    "Max results per engine",
                    min_value=1,
                    max_value=100,
                    value=25,
                    step=1,
                )

            csd, ced = None, None
            if period == "custom":
                c1, c2 = st.columns(2)
                with c1:
                    csd = st.text_input("Start date (YYYY-MM-DD)", "")
                with c2:
                    ced = st.text_input("End date (YYYY-MM-DD)", "")

            out_csv = st.text_input(
                "Output CSV (relative to project)",
                "out/dashboard_results.csv",
            )
            c_opt1, c_opt2 = st.columns(2)
            with c_opt1:
                strict_rel = st.toggle("Hard/strict relevance filter", value=False)
            with c_opt2:
                fast_ret = st.toggle("Fast retrieval mode", value=False)
            st.caption("Turn OFF hard filter to maximize returned rows.")
            ddg_reddit_boost = st.checkbox(
                "Add `site:reddit.com` pass (DuckDuckGo)",
                value=st.session_state.get("_ddg_reddit_boost", False),
                help=(
                    "Runs DuckDuckGo twice for DDG: once for the open web and once with "
                    "`site:reddit.com`. Without this, Reddit thread URLs rarely appear."
                ),
                key="ddg_reddit_boost_cb",
            )
            st.session_state["_ddg_reddit_boost"] = ddg_reddit_boost

        if st.button("Run search", type="primary", use_container_width=True):
            if not engines:
                st.error("Select at least one search engine.")
            elif not (q or "").strip():
                st.error("Enter search terms.")
            else:
                with st.spinner("Collecting…"):
                    try:
                        logs, total = run_search_job(
                            ROOT,
                            query=q.strip(),
                            engines=engines,
                            period=period,
                            start_s=csd or None,
                            end_s=ced or None,
                            max_results=int(max_n),
                            output_csv=out_csv,
                            append=False,
                            dedupe=False,
                            strict_relevance=bool(strict_rel),
                            fast_retrieval=bool(fast_ret),
                            ddg_reddit_site_boost=bool(ddg_reddit_boost),
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.session_state["_last_query"] = q.strip()
                        st.session_state["_last_output_csv"] = out_csv
                        st.session_state["_last_max_results"] = int(max_n)
                        outp = Path(out_csv)
                        if not outp.is_absolute():
                            outp = (ROOT / outp).resolve()
                        if outp.is_file():
                            df_new = pd.read_csv(outp, encoding="utf-8")
                            st.session_state["loaded_df"] = normalize_df_columns(df_new)
                            st.session_state["loaded_csv_path"] = str(outp)
                        st.success(f"Done — wrote **{total}** new row(s) total.")
                        with st.expander("Run log", expanded=False):
                            st.code("\n".join(logs))
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_data:
        st.markdown('<p class="oscar-section-title">Corpus & automation</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="oscar-muted">Load CSVs, filter, scrape pages, export, and schedule repeat collection.</p>',
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            data_path = st.text_input(
                "CSV file path",
                value=st.session_state.get("_csv_path", str(ROOT / "out" / "dashboard_results.csv")),
                key="csv_path_input",
            )
            st.session_state["_csv_path"] = data_path

            p = Path(data_path)
            if not p.is_absolute():
                p = (ROOT / data_path).resolve()

            auto_load = st.toggle("Auto-load file when path is valid", value=True, key="corpus_auto_load")
            load_now = st.button("Load / refresh CSV", use_container_width=False)
            if load_now or (auto_load and p.is_file()):
                if not p.is_file():
                    st.warning(f"File not found: {p}")
                else:
                    df_load = pd.read_csv(p, encoding="utf-8")
                    st.session_state["loaded_df"] = normalize_df_columns(df_load)
                    st.session_state["loaded_csv_path"] = str(p)
                    st.session_state["loaded_csv_mtime"] = p.stat().st_mtime

        df: pd.DataFrame | None = st.session_state.get("loaded_df")  # type: ignore[assignment]
        if df is None:
            st.info("Load a CSV above to preview, scrape, and schedule.")
        else:
            with st.container(border=True):
                csv_path = st.session_state.get("loaded_csv_path", "")
                mtime = st.session_state.get("loaded_csv_mtime")
                if mtime:
                    dt = datetime.fromtimestamp(float(mtime)).strftime("%Y-%m-%d %H:%M:%S")
                    st.caption(f"{len(df)} rows · `{csv_path}` · last loaded {dt}")
                else:
                    st.caption(f"{len(df)} rows · `{csv_path}`")

                c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                c_m1.metric("Rows", int(len(df)))
                c_m2.metric("Unique URLs", int(df["url"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()) if "url" in df.columns else 0)
                c_m3.metric("Scraped pages", int(df["scraped_text_relative_path"].astype(str).str.strip().ne("").sum()) if "scraped_text_relative_path" in df.columns else 0)
                c_m4.metric("Errors", int(df["scrape_error"].astype(str).str.strip().ne("").sum()) if "scrape_error" in df.columns else 0)

                filt = st.text_input("Search corpus text", "", placeholder="Type keyword to filter all columns")
                view = df.copy()
                if "search_engine" in view.columns:
                    present = {x for x in view["search_engine"].astype(str).str.strip().tolist() if x}
                    canonical = {"google", "duckduckgo", "reddit", "reddit_via_duckduckgo"}
                    eng_vals = sorted(canonical.union(present))
                    default_vals = sorted(present) if present else ["google", "duckduckgo"]
                    eng_pick = st.multiselect("Engines", eng_vals, default=default_vals)
                    if eng_vals and eng_pick:
                        view = view.loc[view["search_engine"].astype(str).str.strip().isin(eng_pick)]
                show_unscraped = st.checkbox("Show only rows not scraped yet", value=False)
                if show_unscraped and "scraped_text_relative_path" in view.columns:
                    view = view.loc[view["scraped_text_relative_path"].astype(str).str.strip() == ""]
                if filt.strip():
                    mask = (
                        view.astype(str)
                        .apply(lambda s: s.str.contains(filt, case=False, na=False))
                        .any(axis=1)
                    )
                    view = view.loc[mask]
                # Streamlit data_editor validates column config against dtype; ensure text columns are strings.
                for c in ("page_excerpt", "search_query", "scrape_error"):
                    if c in view.columns:
                        view[c] = view[c].fillna("").astype(str)

                col_cfg = {}
                if "url" in view.columns:
                    col_cfg["url"] = st.column_config.LinkColumn("URL", display_text="open")
                for c in ("page_excerpt", "search_query", "scrape_error"):
                    if c in view.columns:
                        col_cfg[c] = st.column_config.TextColumn(c, width="large")

                st.data_editor(
                    view,
                    column_config=col_cfg or None,
                    use_container_width=True,
                    height=420,
                    disabled=True,
                    hide_index=True,
                )

            with st.container(border=True):
                st.markdown("**Scrape underlying pages**")
                st.caption(
                    "HTTP fetch + **trafilatura** extraction → `out/scraped/`; scrape columns updated in memory."
                )
                latest_q = str(st.session_state.get("_last_query", "")).strip()
                scrape_scope_df = df
                if latest_q and "search_query" in df.columns:
                    qmask = df["search_query"].astype(str).str.strip() == latest_q
                    scrape_scope_df = df.loc[qmask]
                eligible_unscraped = 0
                if "url" in scrape_scope_df.columns and "scraped_text_relative_path" in scrape_scope_df.columns:
                    eligible_unscraped = int(
                        (
                            scrape_scope_df["url"].astype(str).str.startswith("http")
                            & scrape_scope_df["scraped_text_relative_path"].astype(str).str.strip().eq("")
                        ).sum()
                    )
                preferred_scrape_n = int(st.session_state.get("_last_max_results", 25))
                if eligible_unscraped <= 0:
                    default_scrape_n = 0
                else:
                    default_scrape_n = min(max(1, preferred_scrape_n), eligible_unscraped, 100)
                max_scrape = st.number_input(
                    "Max pages to scrape (unscraped rows, top-down)",
                    min_value=0,
                    max_value=100,
                    value=default_scrape_n,
                    step=1,
                )
                if latest_q:
                    st.caption(
                        f"Scraping is locked to current query: `{latest_q}` "
                        f"(unscraped rows available: {eligible_unscraped})."
                    )
                else:
                    st.caption("Run a search first to lock scraping to that query.")
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("Run scrape", disabled=int(max_scrape) <= 0, use_container_width=True):
                        with st.spinner("Scraping…"):
                            scrape_df = df
                            if latest_q and "search_query" in df.columns:
                                qmask = df["search_query"].astype(str).str.strip() == latest_q
                                scrape_df = df.loc[qmask].copy()
                            df2, slog = scrape_dataframe_urls(ROOT, scrape_df, int(max_scrape))
                            if len(df2) != len(df):
                                merged = df.copy()
                                cols = [
                                    "scraped_text_relative_path",
                                    "scraped_at_utc",
                                    "scrape_error",
                                ]
                                for col in cols:
                                    if col in df2.columns:
                                        merged.loc[df2.index, col] = df2[col]
                                st.session_state["loaded_df"] = merged
                                df = merged
                            else:
                                st.session_state["loaded_df"] = df2
                                df = df2
                            st.session_state["_scrape_log"] = slog
                with col_s2:
                    save_p = Path(st.session_state.get("loaded_csv_path", str(p)))
                    if st.button("Save CSV", use_container_width=True):
                        save_dataframe_csv(save_p, st.session_state["loaded_df"])
                        st.success(f"Saved `{save_p}`")

                if st.session_state.get("_scrape_log"):
                    with st.expander("Scrape log", expanded=False):
                        st.code(
                            "\n".join(st.session_state["_scrape_log"])
                            if st.session_state["_scrape_log"]
                            else "(no rows)"
                        )

                st.download_button(
                    label="Download filtered view (CSV)",
                    data=view.to_csv(index=False).encode("utf-8"),
                    file_name="oscar_filtered_export.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with st.container(border=True):
                st.markdown("**Automatic repeat searches**")
                st.caption(
                    "In-app schedule is checked about every **60s** while OSCAR stays open. "
                    "Use **cron** or **LaunchAgent** (`scripts/`) when the machine should run unattended."
                )

                sch = load_schedule(ROOT)
                en = st.checkbox("Enable in-app auto-repeat", value=sch.enabled, key="sch_en")
                _iv_labels = ["Hourly", "Daily", "Weekly", "Monthly"]
                _iv_map = {1.0: "Hourly", 24.0: "Daily", 168.0: "Weekly", 720.0: "Monthly"}
                _iv_pick = _iv_map.get(float(sch.interval_hours), "Daily")
                iv = st.selectbox("Repeat interval", _iv_labels, index=_iv_labels.index(_iv_pick))
                sq_default = sch.query or st.session_state.get("search_query") or st.session_state.get("_q") or ""
                sch_query = st.text_input("Scheduled query", value=sq_default, key="sch_q")
                sch_eng = st.multiselect(
                    "Scheduled engines",
                    ["google", "duckduckgo", "reddit"],
                    default=list(sch.engines or ["duckduckgo"]),
                )
                sch_period = st.selectbox(
                    "Scheduled period",
                    ["24h", "week", "month", "year", "custom"],
                    index=1,
                    key="sch_p",
                )
                sch_max = st.number_input("Scheduled max results / engine", 1, 100, int(sch.max_results), key="sch_n")
                sch_out = st.text_input("Scheduled output CSV", sch.output_csv, key="sch_o")
                sch_dedupe = st.checkbox("Dedupe URLs on scheduled runs", value=sch.dedupe_urls, key="sch_d")
                sch_ddg_rb = st.checkbox(
                    "Scheduled: add `site:reddit.com` pass",
                    value=sch.ddg_reddit_site_boost,
                    key="sch_rb",
                )

                if st.button("Save schedule"):
                    nxt = sch.next_run_utc
                    if bool(en) and not nxt:
                        nxt = utc_now_iso()
                    ns = replace(
                        sch,
                        enabled=bool(en),
                        interval_hours=_interval_hours(iv),
                        query=sch_query.strip(),
                        engines=list(sch_eng) if sch_eng else ["duckduckgo"],
                        period=sch_period,
                        max_results=int(sch_max),
                        output_csv=sch_out.strip() or "out/dashboard_results.csv",
                        dedupe_urls=bool(sch_dedupe),
                        ddg_reddit_site_boost=bool(sch_ddg_rb),
                        next_run_utc=nxt,
                    )
                    save_schedule(ROOT, ns)
                    st.success("Schedule saved to `out/dashboard_schedule.json`.")

                st.code(_cron_snippet(ROOT, iv), language="bash")

                if st.session_state.get("_sched_last"):
                    st.info(str(st.session_state["_sched_last"]))

    with tab_results:
        st.markdown('<p class="oscar-section-title">Corpus insights</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="oscar-muted">Summaries from the CSV loaded in Corpus (metrics, breakdowns, quick browser).</p>',
            unsafe_allow_html=True,
        )

        df_r: pd.DataFrame | None = st.session_state.get("loaded_df")  # type: ignore[assignment]
        if df_r is None:
            st.info("Load a CSV in **Corpus** to see insights here.")
        else:
            dfr = normalize_df_columns(df_r)
            total_rows = len(dfr)
            unique_urls = dfr["url"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
            unique_engines = (
                dfr["search_engine"].astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                if "search_engine" in dfr.columns
                else 0
            )
            with_source_date = (
                dfr["source_created_at"].astype(str).str.strip().ne("").sum()
                if "source_created_at" in dfr.columns
                else 0
            )
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rows", int(total_rows))
            m2.metric("Unique URLs", int(unique_urls))
            m3.metric("Engines", int(unique_engines))
            m4.metric("With source date", int(with_source_date))

            with st.container(border=True):
                st.markdown("**Google AI Studio (Gemini)**")
                st.caption(
                    "Uses your [Google AI Studio](https://aistudio.google.com/) API key — "
                    "separate from Google Custom Search. Set `GOOGLE_AI_API_KEY` in `.env`."
                )
                _models = (
                    "gemini-2.5-flash",
                    "gemini-2.0-flash",
                    "gemini-2.0-flash-lite",
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                )
                _default_model = (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()
                _idx = _models.index(_default_model) if _default_model in _models else 0
                gm1, gm2 = st.columns(2)
                with gm1:
                    gem_model = st.selectbox("Model", _models, index=_idx, key="gem_model")
                with gm2:
                    gem_rows = st.number_input("Rows to send", min_value=5, max_value=80, value=40, step=5, key="gem_rows")
                gem_extra = st.text_input(
                    "Optional focus (e.g. “emphasize policy vs personal stories”)",
                    "",
                    key="gem_extra",
                )
                if st.button("Analyze corpus with Gemini", key="gem_run", use_container_width=True):
                    with st.spinner("Calling Gemini…"):
                        try:
                            out, used_model = analyze_corpus_with_model_fallback(
                                dfr,
                                preferred_model=gem_model,
                                max_rows=int(gem_rows),
                                extra_instructions=gem_extra.strip(),
                            )
                        except Exception as e:
                            st.warning(f"Gemini unavailable ({e}). Showing local fallback analysis.")
                            out = analyze_corpus_locally(dfr)
                            used_model = "local_fallback"
                        else:
                            st.session_state["_gemini_last"] = out
                        st.session_state["_gemini_last"] = out
                        st.session_state["_gemini_used_model"] = used_model
                upload_csv_default = st.session_state.get("loaded_csv_path", "")
                upload_csv_path = st.text_input(
                    "CSV path to upload to Google AI Studio",
                    value=str(upload_csv_default),
                    key="gem_upload_csv_path",
                )
                if st.button("Upload CSV to Gemini and analyze", key="gem_upload_run", use_container_width=True):
                    with st.spinner("Uploading CSV and analyzing…"):
                        try:
                            out2, used_model2 = analyze_uploaded_csv_with_model_fallback(
                                upload_csv_path,
                                preferred_model=gem_model,
                                extra_instructions=gem_extra.strip(),
                            )
                        except Exception as e:
                            st.warning(f"Gemini upload analysis unavailable ({e}). Showing local fallback analysis.")
                            out2 = analyze_corpus_locally(dfr)
                            used_model2 = "local_fallback"
                        else:
                            st.session_state["_gemini_uploaded_last"] = out2
                            out_md = ROOT / "out" / "ai_analysis_from_uploaded_csv.md"
                            out_md.parent.mkdir(parents=True, exist_ok=True)
                            out_md.write_text(out2, encoding="utf-8")
                            st.success(f"Saved uploaded-file analysis to `{out_md}`")
                        st.session_state["_gemini_uploaded_last"] = out2
                        st.session_state["_gemini_uploaded_used_model"] = used_model2
                if st.session_state.get("_gemini_last"):
                    if st.session_state.get("_gemini_used_model"):
                        st.caption(f"Analysis source: `{st.session_state['_gemini_used_model']}`")
                    st.markdown(st.session_state["_gemini_last"])
                if st.session_state.get("_gemini_uploaded_last"):
                    st.markdown("---")
                    st.markdown("#### Uploaded CSV analysis")
                    if st.session_state.get("_gemini_uploaded_used_model"):
                        st.caption(f"Analysis source: `{st.session_state['_gemini_uploaded_used_model']}`")
                    st.markdown(st.session_state["_gemini_uploaded_last"])

            with st.container(border=True):
                st.markdown("**By search engine**")
                if "search_engine" in dfr.columns:
                    eng = (
                        dfr["search_engine"]
                        .astype(str)
                        .str.strip()
                        .replace("", "(blank)")
                        .value_counts()
                        .rename_axis("search_engine")
                        .reset_index(name="count")
                    )
                    st.dataframe(eng, use_container_width=True, hide_index=True)
                else:
                    st.info("No `search_engine` column in this file.")

            with st.container(border=True):
                st.markdown("**Top domains**")
                if "url" in dfr.columns:
                    domains = (
                        dfr["url"]
                        .astype(str)
                        .str.extract(r"https?://([^/]+)", expand=False)
                        .fillna("")
                        .str.lower()
                        .str.replace(r"^www\.", "", regex=True)
                    )
                    top_domains = (
                        domains[domains != ""]
                        .value_counts()
                        .head(20)
                        .rename_axis("domain")
                        .reset_index(name="count")
                    )
                    if top_domains.empty:
                        st.info("No valid URLs for a domain summary.")
                    else:
                        st.dataframe(top_domains, use_container_width=True, hide_index=True)
                else:
                    st.info("No `url` column in this file.")

            with st.container(border=True):
                st.markdown("**Browse rows**")
                engine_opts = ["All"]
                if "search_engine" in dfr.columns:
                    engine_vals = sorted(
                        {
                            x
                            for x in dfr["search_engine"].astype(str).str.strip().tolist()
                            if x
                        }
                    )
                    engine_opts.extend(engine_vals)
                c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
                with c_f1:
                    engine_pick = st.selectbox("Engine", engine_opts, index=0, key="res_engine")
                with c_f2:
                    keyword = st.text_input("Contains text", "", key="res_kw")
                with c_f3:
                    show_n = st.number_input("Show up to", 5, 200, 50, 5, key="res_limit")

                vr = dfr
                if engine_pick != "All" and "search_engine" in vr.columns:
                    vr = vr.loc[vr["search_engine"].astype(str).str.strip() == engine_pick]
                if keyword.strip():
                    mask = (
                        vr.astype(str)
                        .apply(lambda s: s.str.contains(keyword, case=False, na=False))
                        .any(axis=1)
                    )
                    vr = vr.loc[mask]
                vr = vr.head(int(show_n))

                col_cfg = {}
                if "url" in vr.columns:
                    col_cfg["url"] = st.column_config.LinkColumn("URL", display_text="open")
                for c in ("page_excerpt", "search_query", "scrape_error"):
                    if c in vr.columns:
                        col_cfg[c] = st.column_config.TextColumn(c, width="large")
                st.dataframe(vr, column_config=col_cfg or None, use_container_width=True, height=380)

    _scheduled_tick()


main()
