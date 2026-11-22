"""
Run the whole pipeline from raw files to final charts, in order.

    python run_all.py              # everything except downloading (raw data is already in data/raw)
    python run_all.py --download   # download the raw data first (needs internet, ~10 min)

PySpark and MySQL are separate because they need extra installs:
    python spark/spark_resample_join.py
    python src/09_load_mysql.py --run-queries          (or --sqlite for a quick test)
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
PY = sys.executable

STEPS = [
    ("src/02_flatten_weather.py", []),
    ("src/03_clean_air_quality.py", []),
    ("src/04_build_calendar.py", []),
    ("src/05_parse_waterlogging.py", []),
    ("src/06_build_spatial.py", []),
    ("src/07_process_news.py", []),
    ("src/08_analysis.py", []),
    ("src/10_spreadsheet_pivot.py", ["build"]),
    ("src/11_v_profile.py", []),
]
if "--download" in sys.argv:
    STEPS.insert(0, ("src/01_download.py", []))

for script, args in STEPS:
    print(f"\n{'=' * 70}\n>>> {script} {' '.join(args)}\n{'=' * 70}")
    subprocess.run([PY, str(ROOT / script), *args], check=True, cwd=ROOT)

# human-readable copy of the cleaning log
log = pd.read_csv(ROOT / "docs" / "cleaning_log.csv")
lines = ["# Cleaning log", "",
         "_One row per decision. Generated from `docs/cleaning_log.csv`, which every script in `src/` "
         "writes to. Example rows for each outlier type: `outputs/tables/outlier_examples.csv`._", "",
         "| # | Step | Dataset | Problem found | Rows affected | Action taken | Why |", "|---|---|---|---|---:|---|---|"]
for i, r in enumerate(log.itertuples(), 1):
    rows = f"{int(r.rows_affected):,}" if str(r.rows_affected).isdigit() else r.rows_affected
    lines.append(f"| {i} | {r.step} | {r.dataset} | {r.problem_found} | {rows} | {r.action_taken} | {r.why} |")
(ROOT / "docs" / "cleaning_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nAll steps finished. Open the xlsx, save it, then run: python src/10_spreadsheet_pivot.py compare")
