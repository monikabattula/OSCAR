"""
Upload CSV to Google AI Studio (Gemini Files API) and analyze it.

Usage:
  ./ .venv/bin/python upload_csv_to_ai_studio.py --csv out/dashboard_results.csv

Requires in environment (.env supported):
  GOOGLE_AI_API_KEY=...
Optional:
  GEMINI_MODEL=gemini-2.0-flash
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: google-generativeai. Install with: pip install -e ."
    ) from exc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Upload a CSV to Gemini Files API and run analysis."
    )
    p.add_argument(
        "--csv",
        default="out/dashboard_results.csv",
        help="Path to CSV file to upload.",
    )
    p.add_argument(
        "--out",
        default="out/ai_analysis_from_uploaded_csv.md",
        help="Path to save analysis markdown.",
    )
    p.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        help="Gemini model name.",
    )
    return p


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    api_key = (os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Set GOOGLE_AI_API_KEY (or GEMINI_API_KEY) in .env first.")

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV file not found: {csv_path}")

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    genai.configure(api_key=api_key)

    print(f"Uploading CSV: {csv_path}")
    uploaded = genai.upload_file(path=str(csv_path), display_name=csv_path.name)

    prompt = (
        "You are a research analyst. Analyze the uploaded CSV and return markdown with:\n"
        "1) Executive summary (5-8 bullets)\n"
        "2) Main themes/topics\n"
        "3) Notable sources/domains\n"
        "4) Data quality issues (duplicates, irrelevant rows, missing fields)\n"
        "5) 12 recommended next search queries\n"
        "Keep it concise and actionable."
    )

    model = genai.GenerativeModel(args.model)
    print(f"Running analysis with model: {args.model}")
    resp = model.generate_content([uploaded, prompt])
    text = (resp.text or "").strip()
    if not text:
        text = "No text response returned by model."

    out_path.write_text(text, encoding="utf-8")
    print(f"Saved analysis: {out_path}")

    # Best effort cleanup from Files API
    try:
        genai.delete_file(uploaded.name)
    except Exception:
        pass


if __name__ == "__main__":
    main()

