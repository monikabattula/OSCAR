#!/usr/bin/env bash
# Scheduled runner: loads schedule.env and appends SERP rows to CSV.
# Intended for cron or macOS launchd (every 24h).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/out/logs"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/serp_scheduled.log"

if [[ ! -f .venv/bin/activate ]]; then
  echo "serp_collect_scheduled: missing .venv in $ROOT — run: python3 -m venv .venv && pip install -e ." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [[ ! -f schedule.env ]]; then
  echo "serp_collect_scheduled: create schedule.env from schedule.env.example in $ROOT" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source schedule.env
set +a

: "${SERP_QUERY:?Set SERP_QUERY in schedule.env}"

ENGINE="${SERP_ENGINE:-duckduckgo}"
PERIOD="${SERP_PERIOD:-week}"
MAXN="${SERP_MAX_RESULTS:-50}"
OUT="${SERP_OUTPUT:-out/scheduled_serp.csv}"

ARGS=(
  -q "$SERP_QUERY"
  -e "$ENGINE"
  -p "$PERIOD"
  -n "$MAXN"
  -o "$OUT"
  --append
)

if [[ "$PERIOD" == "custom" ]]; then
  : "${SERP_START_DATE:?Set SERP_START_DATE for custom period}"
  : "${SERP_END_DATE:?Set SERP_END_DATE for custom period}"
  ARGS+=(--start-date "$SERP_START_DATE" --end-date "$SERP_END_DATE")
fi

{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC | serp-collect ==="
  set +e
  serp-collect "${ARGS[@]}"
  code=$?
  set -e
  echo "--- exit $code"
} >>"$RUN_LOG" 2>&1
exit "$code"
