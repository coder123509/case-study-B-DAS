# The Monsoon Last-Mile Trap - Bengaluru

**Data and Storytelling · Module 1 · Case Study B**

> **Our question:** Where and when does monsoon weather make the last mile to Bengaluru's BMTC bus stops most
> vulnerable - where pedestrian-network gaps, known waterlogging spots and high nearby air pollution overlap?

We joined a year of 15-minute air-quality readings from 5 government monitoring stations with hourly weather,
the BMTC bus network, OpenStreetMap footpaths, BBMP's list of flood-prone spots, a hand-built holiday calendar
and news headlines. Everything is from public sources and every number below can be rebuilt by running the code.

GitHub repo: https://github.com/coder123509/case-study-B-DAS.git

---

## What we found

| | Finding | Evidence |
|---|---|---|
| **When** | Monsoon rain hits the **evening** commute, not the morning one. In Jul-Oct, 14-19% of hours between 17:00 and 20:00 are rainy versus about 4-6% between 08:00 and 10:00. About half of all May-Oct rain falls between 14:00 and 20:00. | `fig03`, `outputs/tables/when_windows.csv`, SQL Q5 |
| **Air** | Rain and dirty air mostly do **not** overlap. Compared at the same station, month and hour, rainy hours have **~27% less PM2.5** (81% of comparisons lower). NO2 barely changes. The worst air is on dry **winter / post-monsoon evenings, 20:00-22:00**. | `fig05`, `fig02`, `rain_effect_summary.csv` |
| **Where** | Stops around **Silk Board** and **Bapuji Nagar (Mysore Road)** score highest: busy stops, almost no mapped footpath or crossings within 300 m, and a BBMP flood point a short walk away. Central Silk Board (6 bays, ~6,200 bus calls on a Wednesday) is #1. | `fig06`, `location_priority_ranking.csv`, SQL Q6/Q7 |
| **Robust?** | The top-10 busy stops stay the same when we change the score weights (10/10, 10/10, 8/10 with pollution removed). | `score_sensitivity.csv` |
| **Text** | 847 unique news headlines: waterlogging headlines move with monthly rain (r = 0.63 over the 8 months the API answered); May 2025 had the most and still hit the 250-article cap. | `fig07`, `news_monthly.csv`, `news_coverage.csv` |

What this supports for the commissioner: footpath + drain work first at Silk Board and Mysore Road stops;
rain alerts timed for **15:00-17:00** on monsoon days (before the evening rush); and pollution alerts for
**dry winter evenings**, which is a different problem from the monsoon one.

**What it does not show:** cause and effect, or anyone's personal pollution exposure. A missing footpath in
OpenStreetMap does not prove the footpath is missing on the ground. See [Limitations](#limitations).

---

## Repository layout

```
monsoon-last-mile/
├── README.md                 <- you are here
├── config.py                 <- study window, station ids, distances, thresholds (change things HERE)
├── run_all.py                <- runs every step in order
├── requirements.txt
├── src/                      <- the pipeline, numbered in the order it runs
│   ├── 01_download.py            download all raw data (needs internet)
│   ├── 02_flatten_weather.py     JSON -> hourly table, UTC -> IST
│   ├── 03_clean_air_quality.py   type casting, outliers, gaps, 15-min -> hourly  (+ gap chart)
│   ├── 04_build_calendar.py      hand-typed holidays -> daily calendar
│   ├── 05_parse_waterlogging.py  BBMP PDF -> table of flood points
│   ├── 06_build_spatial.py       bus stops, footpaths within 300 m, distance to flood points
│   ├── 07_process_news.py        news headlines -> tagged, de-duplicated table
│   ├── 08_analysis.py            joins, normalisation, priority score, charts
│   ├── 09_load_mysql.py          load MySQL + run the SQL queries
│   ├── 10_spreadsheet_pivot.py   build the Excel pivot and compare it with pandas
│   ├── 11_v_profile.py           measure volume / velocity / variety
│   ├── utils.py                  cleaning-log writer, hourly-slot rule, distance maths
│   └── plot_style.py             one colour scheme for all charts
├── spark/spark_resample_join.py  <- PySpark version of load -> clean -> hourly -> join -> group
├── sql/schema.sql, sql/queries.sql
├── spreadsheet/pm25_hour_weekday_pivot.xlsx
├── data/
│   ├── raw/          exactly what the sources sent (GTFS zip is git-ignored, 93 MB)
│   ├── manual/       the holiday list we typed from the government PDF
│   ├── processed/    cleaned, analysis-ready tables
│   └── raw_checksums_sha256.txt
├── outputs/figures/  fig01 ... fig07 (PNG)
├── outputs/tables/   every number used in the report
└── docs/             source register, data inventory, V profile, cleaning log, ER diagram,
                      pivot comparison, team contribution, AI disclosure
```

---

## Setup

1. **Python 3.10+** (we used Anaconda). In the project folder:
   ```bash
   pip install -r requirements.txt
   ```
2. **pdftotext** (only for step 05): `conda install -c conda-forge poppler`
3. **Java 11 or 17** for PySpark. Check with `java -version`; set `JAVA_HOME` if Spark complains.
4. **MySQL 8** (for step 09), plus MySQL Workbench if you want the ER view.

## Run it

```bash
# 0. (optional) re-download the raw data - only needed for the GTFS zip, the rest is already in data/raw
python src/01_download.py gtfs          # or with no argument to re-download everything

# 1. the whole pandas pipeline: raw -> cleaned -> charts (about 1-2 minutes)
python run_all.py

# 2. spreadsheet check: open spreadsheet/pm25_hour_weekday_pivot.xlsx in Excel, let it calculate, SAVE, then
python src/10_spreadsheet_pivot.py compare      # writes docs/pivot_comparison.md

# 3. PySpark job on the largest table (prints row counts before/after every step)
python spark/spark_resample_join.py

# 4. MySQL: create the database once, then load + run the 8 queries
#    mysql> CREATE DATABASE monsoon_last_mile;
set MYSQL_USER=root
set MYSQL_PASSWORD=your_password
python src/09_load_mysql.py --run-queries       # results -> outputs/tables/sql_results.txt
# no MySQL handy? same schema and queries on SQLite:
python src/09_load_mysql.py --sqlite --run-queries
```
(On Mac/Linux use `export` instead of `set`.)

## Raw data - how to get it again
All URLs, dates and licences are in [`docs/source_register.md`](docs/source_register.md). In short:

| Source | Command | Size |
|---|---|---|
| OpenAQ archive (CPCB/KSPCB, 5 stations, 15-min) | `python src/01_download.py openaq` | 5 x ~1.4 MB gz |
| Open-Meteo hourly weather (JSON API, no key) | `python src/01_download.py weather` | 0.4 MB |
| OpenStreetMap via Overpass | `python src/01_download.py osm` | 6 MB |
| BMTC GTFS (pinned commit) | `python src/01_download.py gtfs` | 93 MB (not in git) |
| BBMP flood points PDF + Karnataka holiday PDFs | `python src/01_download.py docs` | < 2 MB |
| GDELT news headlines | `python src/01_download.py news` | < 1 MB |

GDELT and Overpass return today's data, so a fresh download can differ slightly from ours - the files we
analysed are the ones committed in `data/raw/` (checksums in `data/raw_checksums_sha256.txt`).

---

## How each Module 1 requirement is covered

| Requirement | Where |
|---|---|
| Data types (nominal / ordinal / discrete / continuous; structured / semi / unstructured) | [`docs/data_inventory.md`](docs/data_inventory.md) - AQI category is built as an ordered category in `08_analysis.py` |
| 3 Vs | [`docs/v_profile.md`](docs/v_profile.md) (measured by `11_v_profile.py`) |
| 3+ sources, JSON API, calendar we built | [`docs/source_register.md`](docs/source_register.md), `data/manual/karnataka_holidays_2025_26.csv` |
| Flatten JSON | Open-Meteo in `02_flatten_weather.py` (and in Spark with `arrays_zip` + `explode`); OSM in `06`; GDELT in `07` |
| MySQL, 3+ related tables, ER diagram, 5+ queries with JOIN and GROUP BY | `sql/schema.sql` (9 tables), [`docs/er_diagram.md`](docs/er_diagram.md) + `er_diagram.png`, `sql/queries.sql` (8 queries) |
| Spreadsheet pivot rebuilt in pandas | `spreadsheet/pm25_hour_weekday_pivot.xlsx`, [`docs/pivot_comparison.md`](docs/pivot_comparison.md) |
| Missing values: gaps counted per station, rule chosen | `outputs/tables/gap_summary.csv`, `fig01_sensor_gaps.png`, cleaning log |
| Type casting (timestamps, UTC -> IST, text -> float) | `02`, `03`, `07`, cleaning log |
| Outliers: sensor faults vs real events | `03` rules + `outputs/tables/outlier_examples.csv` (794.0 error code, 999 sentinel, negatives, flat-lines, spikes, PM2.5 > PM10, Deepavali kept) |
| Normalisation | z-scores per station (`fig04`), min-max for the priority score (`08`) |
| PySpark: load, clean, resample hourly, group by hour & weekday, join weather, row counts | `spark/spark_resample_join.py` -> `outputs/tables/spark_row_counts.csv` |
| Reproducible pipeline | `run_all.py`, this README, commits from every member |
| Cleaning log | [`docs/cleaning_log.md`](docs/cleaning_log.md) (also `.csv`) |

## Key decisions (short version - full reasons in the cleaning log)

- **Study year:** 1 Mar 2025 - 28 Feb 2026 (IST). It covers the pre-monsoon storms, the whole south-west
  monsoon (Jun-Sep), the north-east monsoon (Oct-Dec) and winter.
- **"Same hour" across sources:** weather is hourly in UTC, which ends at :30 in IST. We define slot 18:00 as
  17:30-18:30 IST and put every reading into its slot (`utils.hour_slot`).
- **Gaps:** an hour needs at least 1 valid PM reading (PM values repeat every 15 min) or 2 valid gas readings.
  Gaps of up to 3 h are interpolated; longer gaps stay empty and are never filled.
- **Faults vs real events:** negatives, the 999 sentinel, a repeated error code (PM2.5 = 794.0 at Jayanagar),
  PM2.5 > PM10, 6-hour flat-lines and isolated spikes are removed. Deepavali and New Year's Eve nights are
  protected, because those peaks are real.
- **Bus stops:** BMTC stops within 1.5 km of a monitoring station (351 stops); "last mile" = a 300 m walk.
- **Priority score:** average of 3 parts scaled 0-1 - mapped-footpath/crossing gap, closeness to a BBMP flood
  point, and evening PM2.5 at the nearest station. It is a screening tool to decide where to look first.

## Limitations

- **Sensor coverage:** 5 stations for a city of well over 10 million people. Large parts of the east (Whitefield,
  Mahadevapura) and the north have no station in our set, so those stops are not in the study at all.
- **Station readings are not personal exposure.** A station up to 1.5 km away stands in for the air at the stop.
- **Weather is one grid cell** for the whole city; local cloudbursts can be missed or smoothed.
- **OpenStreetMap is volunteer-mapped.** Areas with few mappers (Bapuji Nagar shows almost no mapped
  footpaths) may look worse than they are.
- **BBMP flood points are from 2020-21;** some have been fixed since and new ones have appeared.
- **GTFS is unofficial** and a 2026-27 snapshot; only routes with live tracking are included.
- **News:** headlines only, keyword tags in English only. GDELT rate-limited us: the waterlogging query has no data for
  Jul, Sep 2025 and Jan, Feb 2026, and the footpath query for 6 months (`outputs/tables/news_coverage.csv`). These show as
  "no data", never as zero. Re-running `python src/01_download.py news` later (it waits 30 s between calls) can fill them.
- **Correlation, not cause:** we compare rainy and dry hours inside the same station-month-hour, which removes
  season and time-of-day effects, but other things (traffic falling during rain, wind) can still explain part of it.

## Final Results

Everything below comes from the files in `outputs/tables/` and `outputs/figures/`, and can be rebuilt with
`python run_all.py`. These are descriptive results for 5 stations over 1 Mar 2025 - 28 Feb 2026, not causal claims.

**Answer to our question.** Monsoon rain mostly hits the evening commute, not the morning one, and it does not
coincide with the worst air. The stops where thin footpaths, nearby flood points and polluted air overlap most are
around **Silk Board** and **Bapuji Nagar (Mysore Road)**.

### When: rain follows the evening commute
- In Jul-Oct, **14-19% of hours between 17:00 and 20:00 are rainy**, against about 4-6% between 08:00 and 10:00
  (`when_windows.csv`, `fig03`). July evenings are the peak (18.5% of hours rainy).
- About half of all May-Oct rain falls between 14:00 and 20:00.
- Rain barely reaches the morning commute, so a rain alert is needed in the afternoon, not at dawn.

### Air: rain and dirty air mostly do not overlap
- Comparing like with like (same station, month and hour of day), rainy hours have **about 27% less PM2.5**
  (median difference -3.7 ug/m3; 81% of the 501 comparisons are lower). NO2 barely changes (-0.25%, 51% lower),
  so we do not claim an effect for it (`rain_effect_summary.csv`, `fig05`).
- The highest average PM2.5 is on dry winter and post-monsoon evenings, around **20:00-22:00**
  (peak cell: Saturday 20:00, 32.4 ug/m3; lowest: Sunday 15:00, 20.5 ug/m3) (`fig02`, pivot table).
- The south-west monsoon is the cleanest season: 511 of 535 station-days fall in the CPCB "Good" band. Days in the
  "Moderate" band or worse appear mainly in the north-east monsoon and winter (`pm25_daily_category_by_season.csv`).
- Plain reading: monsoon walking risk is about water and missing footpaths. Pollution is a separate winter-evening problem.

### Where: the stops that need attention first
| Area (nearest station) | Stops | Mean priority score | Median footpath ratio within 300 m | Stops within 500 m of a flood point |
|---|---:|---:|---:|---:|
| Silk Board | 85 | 79.7 | 0.17 | 47 |
| Bapuji Nagar | 62 | 72.5 | 0.00 | 22 |
| Jayanagar 5th Block | 105 | 56.7 | 0.55 | 21 |
| Hebbal | 39 | 48.9 | 0.43 | 17 |
| Hombegowda Nagar | 60 | 35.3 | 0.57 | 21 |

- Top busy stops: **Central Silk Board** (score 96, 6 bays, about 6,200 bus calls on a Wednesday), **Nayandahalli
  Junction** (92), **Mysore Road Bus Station** (91) and **Mysore Road Metro Station** (90)
  (`location_priority_ranking.csv`, `fig06`).
- The ranking holds when we change the weights: the same 10 busy stops stay in the top 10 under two re-weightings,
  and 8 of 10 when pollution is removed (`score_sensitivity.csv`).
- Caution: Bapuji Nagar's footpath ratio is 0 partly because few footpaths are mapped there in OpenStreetMap. Check on the ground before spending money.

### Text data: news follows the rain
- 847 unique headlines. Waterlogging headlines move with monthly rain (**r = 0.63** over the 8 months the API
  answered); May 2025 had the most (`fig07`, `news_vs_rain_monthly.csv`). Missing months are "no data", not zero.

### Method checks
- **SQL:** 8 queries over 9 related tables, each with JOIN and GROUP BY (`sql/queries.sql`, `outputs/tables/sql_results.txt`).
- **Spreadsheet vs pandas:** all 168 cells of the hour-by-weekday pivot match, largest difference 0.0000 ug/m3 (`docs/pivot_comparison.md`).
- **Cleaning:** every decision is logged in `docs/cleaning_log.md`. Faults were set to NULL, and real events (Deepavali, New Year's Eve) were kept.
- **PySpark:** the same load, clean, hourly resample and join is in `spark/spark_resample_join.py`; row counts go to `outputs/tables/spark_row_counts.csv` once it is run.

### What we recommend
1. Footpath and drain work first at the Silk Board and Mysore Road stops listed above.
2. Rain alerts for commuters at **15:00-17:00** on monsoon days, before the evening rush.
3. Pollution alerts for **dry winter evenings**, as a separate programme from monsoon planning.

### What these results do not show
Cause and effect, personal exposure, or areas without a station (such as Whitefield and the north). The score is a screening tool for deciding where to look first, not a measure of danger. See [Limitations](#limitations).

## Team

See [`docs/team_contribution.md`](docs/team_contribution.md). Use of generative AI is disclosed in
[`docs/ai_disclosure.md`](docs/ai_disclosure.md).
