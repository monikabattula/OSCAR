"""Console entry: `serp-dashboard` → `streamlit run .../dashboard.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import serp_prototype


def main() -> None:
    dash = Path(serp_prototype.__file__).resolve().parent / "dashboard.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(dash), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))
