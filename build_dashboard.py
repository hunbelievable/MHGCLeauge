#!/usr/bin/env python3
"""Build the final Tuesday Night League Dashboard.html from:
  - dashboard-template.html  (HTML/CSS/JS with /*__DATA__*/ and /*__CHARTJS__*/ placeholders)
  - league-data.json         (the actual season data — team standings, player detail, etc.)
  - Chart.js (fetched from node_modules if present, else downloaded)

Usage:
    pip install requests   # only needed if node_modules/chart.js isn't already present
    python3 build_dashboard.py

Produces "Tuesday Night League Dashboard.html" in the same directory.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "dashboard-template.html"
DATA = ROOT / "league-data.json"
OUT = ROOT / "Tuesday Night League Dashboard.html"
CHARTJS_PATH = ROOT / "node_modules" / "chart.js" / "dist" / "chart.umd.js"


def ensure_chartjs() -> str:
    if CHARTJS_PATH.exists():
        return CHARTJS_PATH.read_text(encoding="utf-8")
    print("chart.js not found locally, running `npm install chart.js@4.4.1`...")
    subprocess.run(["npm", "install", "chart.js@4.4.1", "--no-audit", "--no-fund"],
                    cwd=ROOT, check=True)
    if not CHARTJS_PATH.exists():
        sys.exit("npm install ran but chart.umd.js still wasn't found — check node_modules/chart.js/dist/")
    return CHARTJS_PATH.read_text(encoding="utf-8")


def main():
    template = TEMPLATE.read_text(encoding="utf-8")
    data_text = DATA.read_text(encoding="utf-8")
    json.loads(data_text)  # fail loudly on malformed JSON before building anything

    chartjs = ensure_chartjs()

    out = template.replace("/*__CHARTJS__*/", chartjs, 1).replace("/*__DATA__*/", data_text, 1)
    assert "/*__CHARTJS__*/" not in out, "template had more than one CHARTJS placeholder"
    assert "/*__DATA__*/" not in out, "template had more than one DATA placeholder"

    OUT.write_text(out, encoding="utf-8")
    print(f"Built {OUT} ({len(out):,} bytes)")


if __name__ == "__main__":
    main()
