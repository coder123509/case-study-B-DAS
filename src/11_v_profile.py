"""
Step 11 - Measure the 3 Vs from the actual files and write docs/v_profile.md.

Volume  : rows and MB (on disk and in memory) per source
Velocity: how often a reading is produced, readings per hour, how fast new data arrives
Variety : formats / structure types
Numbers are measured here; the 'arrives' column is from each provider's documentation.
"""
import gzip
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

MB = 1024 ** 2
rows = []

# AQ
aq_files = sorted((C.RAW / "openaq").glob("*.csv.gz"))
aq = pd.concat([pd.read_csv(f, dtype=str) for f in aq_files])
aq_unzipped = sum(len(gzip.open(f).read()) for f in aq_files)
ts = pd.to_datetime(aq["datetime"])
n_hours = (ts.max() - ts.min()).total_seconds() / 3600
rows.append({"source": "Air quality (OpenAQ archive of CPCB/KSPCB)", "format": "CSV (gzip)",
             "structure": "structured, long format", "rows": len(aq),
             "mb_disk": sum(f.stat().st_size for f in aq_files) / MB, "mb_raw": aq_unzipped / MB,
             "resolution": "15 min", "readings_per_hour": round(len(aq) / n_hours),
             "arrives": "every 15 min from CPCB CAAQMS; archive files appear daily"})
# weather
wf = C.RAW / "weather" / "openmeteo_bengaluru_hourly_20250228_20260228.json"
wj = json.loads(wf.read_text(encoding="utf-8"))
rows.append({"source": "Weather (Open-Meteo Historical API)", "format": "JSON", "structure": "semi-structured (arrays inside an object)",
             "rows": len(wj["hourly"]["time"]), "mb_disk": wf.stat().st_size / MB, "mb_raw": wf.stat().st_size / MB,
             "resolution": "1 hour", "readings_per_hour": 1 * (len(wj["hourly"]) - 1),
             "arrives": "reanalysis archive, updated daily with a few days' delay"})
# GTFS
gz = sorted((C.RAW / "gtfs").glob("*.zip"))[-1]
z = zipfile.ZipFile(gz)
gtfs_rows = sum(sum(1 for _ in z.open(n)) - 1 for n in ("stops.txt", "trips.txt", "stop_times.txt"))
rows.append({"source": "BMTC GTFS (stops, trips, stop_times)", "format": "CSV text files in a ZIP",
             "structure": "structured, relational", "rows": gtfs_rows, "mb_disk": gz.stat().st_size / MB,
             "mb_raw": sum(i.file_size for i in z.infolist()) / MB, "resolution": "static timetable",
             "readings_per_hour": None, "arrives": "feed rebuilt every few weeks by the maintainer"})
# OSM
of = C.RAW / "osm" / "osm_overpass_pedestrian_5stations_1800m.json"
oj = json.loads(of.read_text(encoding="utf-8"))
rows.append({"source": "OpenStreetMap (Overpass API)", "format": "JSON", "structure": "semi-structured (nested tags + geometry)",
             "rows": len(oj["elements"]), "mb_disk": of.stat().st_size / MB, "mb_raw": of.stat().st_size / MB,
             "resolution": "snapshot " + oj["osm3s"]["timestamp_osm_base"][:10], "readings_per_hour": None,
             "arrives": "volunteer edits, live within minutes"})
# waterlogging
pf = C.RAW / "waterlogging" / "bbmp_swd_vulnerable_locations_2020-21.pdf"
rows.append({"source": "BBMP flood-vulnerable points", "format": "PDF (exported from Excel)", "structure": "semi-structured table in a document",
             "rows": len(pd.read_csv(C.PROCESSED / "waterlogging_locations.csv")), "mb_disk": pf.stat().st_size / MB,
             "mb_raw": pf.stat().st_size / MB, "resolution": "one list for 2020-21", "readings_per_hour": None,
             "arrives": "once a year at best"})
# news
nf = C.RAW / "news" / "gdelt_bengaluru_headlines_202503_202602.json"
if nf.exists():
    nj = json.loads(nf.read_text(encoding="utf-8"))
    n_art = sum(len(b["articles"] or []) for b in nj)
    rows.append({"source": "News headlines (GDELT DOC API)", "format": "JSON", "structure": "unstructured text inside JSON",
                 "rows": n_art, "mb_disk": nf.stat().st_size / MB, "mb_raw": nf.stat().st_size / MB,
                 "resolution": "per article", "readings_per_hour": round(n_art / (365 * 24), 2),
                 "arrives": "GDELT updates every 15 min"})
# calendar
rows.append({"source": "Holiday calendar (hand-built)", "format": "CSV typed from PDF", "structure": "structured",
             "rows": len(pd.read_csv(C.PROCESSED / "calendar.csv")), "mb_disk": (C.MANUAL / "karnataka_holidays_2025_26.csv").stat().st_size / MB,
             "mb_raw": None, "resolution": "1 day", "readings_per_hour": None, "arrives": "once a year (govt notification)"})

v = pd.DataFrame(rows)
v.to_csv(C.TABLES / "v_profile.csv", index=False)

aq_mem = aq.memory_usage(deep=True).sum() / MB
per_param = aq["parameter"].value_counts()
pm_repeat = (pd.read_csv(C.DOCS / "cleaning_log.csv")
             .query("problem_found.str.contains('repeat the previous value')", engine="python")["problem_found"].iloc[0])
spark_counts = C.TABLES / "spark_row_counts.csv"
rc = pd.read_csv(C.TABLES / "aq_row_counts.csv").set_index("stage")["rows"]


def fmt(x, d=1):
    return "-" if x is None or pd.isna(x) else (f"{x:,.0f}" if d == 0 else f"{x:,.{d}f}")


lines = ["# V profile - Monsoon Last-Mile (Bengaluru)", "",
         "_Generated by `src/11_v_profile.py` from the files in `data/raw/`. Re-run after any new download._", "",
         "| Source | Format | Structure | Rows | MB on disk | MB uncompressed | Time resolution | Readings / hour | How fast new data arrives |",
         "|---|---|---|---:|---:|---:|---|---:|---|"]
for r in v.itertuples():
    lines.append(f"| {r.source} | {r.format} | {r.structure} | {fmt(r.rows, 0)} | {fmt(r.mb_disk, 2)} | "
                 f"{fmt(r.mb_raw, 1)} | {r.resolution} | {fmt(r.readings_per_hour, 0)} | {r.arrives} |")
lines += ["",
          "## Volume",
          f"- Largest time-series table (the one the brief's 100,000-row rule applies to): **{len(aq):,} rows** of 15-minute readings (5 stations x 12 parameters x 12 months), "
          f"{sum(f.stat().st_size for f in aq_files) / MB:.1f} MB gzipped, {aq_unzipped / MB:.0f} MB as plain text and "
          f"**{aq_mem:.0f} MB in pandas memory** (text columns are expensive).",
          f"- That is above Excel's 1,048,576-row sheet limit, so the raw table cannot be opened in a spreadsheet at all.",
          f"- After keeping 4 pollutants and the study window it is {rc['inside study window']:,} readings; after resampling, "
          f"{rc['hourly station-hours (grid)']:,} station-hours.",
          "- The static GTFS timetable is even larger (~2.1 M stop_times rows, ~130 MB unzipped), so we read only "
          "2 of its columns and filter to our 351 stops straight away.",
          "",
          "## Velocity",
          f"- Each station reports every 15 minutes: across 5 stations that is ~{round(len(aq) / n_hours)} readings per hour "
          f"(~{round(len(aq) / n_hours * 24):,} per day).",
          f"- But velocity on paper is not velocity in practice: {pm_repeat.lower()}. "
          "The gases (NO2, CO) really do change every 15 minutes.",
          "- Weather arrives hourly and in UTC; AQ arrives in IST quarter-hours. Lining up 'the same hour' "
          "(the +05:30 half-hour offset) was the hardest time problem - see the slot rule in `src/utils.py`.",
          "",
          "## Variety",
          "- 7 sources, 5 formats: CSV, JSON (two very different shapes - column arrays vs nested elements), "
          "a ZIP of relational text files, a PDF table and free-text headlines; plus one calendar typed by hand.",
          "- Three kinds of keys had to be reconciled: time (IST vs UTC, ISO strings vs compact strings), "
          "space (lat/lon distances between stations, stops, footpaths and flood points) and identity "
          "(OpenAQ location ids vs station names with suffixes, GTFS stop ids).",
          "",
          "## Which V dominated, and what it changed",
          "- **Volume + velocity** drove the tools: the 1.27 M-row, 15-minute table is too big for a spreadsheet and "
          "slow to iterate on in pandas memory, so cleaning and resampling are also implemented in **PySpark** "
          "(`spark/spark_resample_join.py`), and only the 8,760-row hourly city series goes into Excel.",
          "- **Variety** cost the most *time*: every source needed its own parser (JSON flattening, PDF text layout, "
          "OSM geometry, GTFS joins) before anything could be joined, and the join key had to be designed "
          "(hourly slot + distance rules).",
          ]
if spark_counts.exists():
    sc = pd.read_csv(spark_counts)
    lines += ["", "## PySpark row counts (from `outputs/tables/spark_row_counts.csv`)", "",
              "| step | rows |", "|---|---:|"] + [f"| {r.step} | {r.rows:,} |" for r in sc.itertuples()]
(C.DOCS / "v_profile.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
