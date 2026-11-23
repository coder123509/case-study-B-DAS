"""
Step 9 - Load the processed CSVs into MySQL (schema in sql/schema.sql).

MySQL:   set your login in a .env-style way (environment variables), then run
             set MYSQL_USER=root            (Windows)   |  export MYSQL_USER=root   (Mac/Linux)
             set MYSQL_PASSWORD=yourpass
             set MYSQL_DB=monsoon_last_mile           (create it first: CREATE DATABASE monsoon_last_mile;)
             python src/09_load_mysql.py --run-queries
Quick test without MySQL (uses a local SQLite file, same schema + queries):
             python src/09_load_mysql.py --sqlite --run-queries

The loader prints row counts per table and, with --run-queries, runs every
query in sql/queries.sql and saves the results to outputs/tables/sql_results.txt
"""
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

USE_SQLITE = "--sqlite" in sys.argv
RUN_QUERIES = "--run-queries" in sys.argv


def connect():
    if USE_SQLITE:
        path = C.DATA / "monsoon_last_mile.sqlite"
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn, "?"
    import pymysql                       # pip install pymysql
    conn = pymysql.connect(host=os.getenv("MYSQL_HOST", "localhost"),
                           port=int(os.getenv("MYSQL_PORT", 3306)),
                           user=os.getenv("MYSQL_USER", "root"),
                           password=os.getenv("MYSQL_PASSWORD", ""),
                           database=os.getenv("MYSQL_DB", "monsoon_last_mile"),
                           local_infile=True, autocommit=False)
    return conn, "%s"


def ist_text(s):
    """'2025-07-01 18:00:00+05:30' -> '2025-07-01 18:00:00' (MySQL DATETIME has no offset)."""
    return pd.to_datetime(s).dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S") \
        if pd.to_datetime(s).dt.tz is not None else pd.to_datetime(s).dt.strftime("%Y-%m-%d %H:%M:%S")


def tables():
    P = C.PROCESSED
    st = pd.read_csv(P / "stations.csv").rename(columns={"location_id": "station_id"})
    cal = pd.read_csv(P / "calendar.csv").rename(columns={"date": "cal_date"})
    cal = cal[["cal_date", "weekday", "weekday_num", "month", "season", "is_weekend", "holiday_name",
               "is_general_holiday", "govt_offices_closed", "is_working_day", "is_long_weekend"]]

    rd = pd.read_csv(P / "aq_15min_clean.csv.gz").rename(columns={"location_id": "station_id"})
    rd["ts_ist"] = ist_text(rd["ts_ist"])
    rd["slot_ist"] = ist_text(rd["slot_ist"])
    rd = rd[["station_id", "parameter", "unit", "ts_ist", "slot_ist", "value", "flag"]]

    hr = pd.read_csv(P / "aq_hourly.csv").rename(columns={"location_id": "station_id", "date_ist": "cal_date"})
    hr["slot_ist"] = ist_text(hr["slot_ist"])
    hr = hr[["station_id", "slot_ist", "cal_date", "hour_ist", "weekday", "pm25", "pm10", "no2", "co", "pm25_filled"]]

    wx = pd.read_csv(P / "weather_hourly.csv").rename(columns={"date_ist": "cal_date"})
    wx["slot_ist"] = ist_text(wx["slot_ist"])
    wx = wx[["slot_ist", "cal_date", "hour_ist", "rain_mm", "precip_mm", "temp_c", "rh_pct", "wind_kmh",
             "weather_code", "is_rainy_hour", "is_heavy_rain"]]

    wl = pd.read_csv(P / "waterlogging_locations.csv")[["wl_id", "zone", "severity", "name", "lat", "lon", "buffer_m"]]
    bs = pd.read_csv(P / "bus_stops.csv", dtype={"stop_id": str, "stop_code": str}) \
        .rename(columns={"nearest_station_id": "nearest_station_id"})
    pf = pd.read_csv(P / "pedestrian_features.csv", dtype={"stop_id": str})

    out = {"stations": st, "calendar": cal, "readings": rd, "readings_hourly": hr,
           "weather_hourly": wx, "waterlogging_locations": wl, "bus_stops": bs, "pedestrian_features": pf}
    if (P / "news_articles.csv").exists():
        na = pd.read_csv(P / "news_articles.csv").rename(columns={"date_ist": "cal_date"})
        na["seen_ist"] = ist_text(na["seen_ist"])
        out["news_articles"] = na.drop(columns=["sourcecountry"], errors="ignore")
    return out


def main():
    conn, ph = connect()
    cur = conn.cursor()
    schema = (C.ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    for stmt in [s.strip() for s in schema.split(";")]:
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            cur.execute(body)
    conn.commit()

    for name, df in tables().items():             # order matters: parents before children
        df = df.astype(object).where(pd.notna(df), None)
        cols = ", ".join(df.columns)
        sql = f"INSERT INTO {name} ({cols}) VALUES ({', '.join([ph] * len(df.columns))})"
        rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
        for i in range(0, len(rows), 20_000):
            cur.executemany(sql, rows[i:i + 20_000])
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        print(f"{name:<24} {cur.fetchone()[0]:>9,} rows")

    if RUN_QUERIES:
        text = (C.ROOT / "sql" / "queries.sql").read_text(encoding="utf-8")
        import re
        blocks = re.split(r"(?m)^-- Q", text)[1:]          # every block starts at a line "-- Qn"
        sql_dir = C.TABLES / "sql"
        sql_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "Q1": "q1_station_completeness.csv",
            "Q2": "q2_cleaning_flags.csv",
            "Q3": "q3_pm25_hour_weekday_top10.csv",
            "Q4": "q4_evening_rain_vs_dry.csv",
            "Q5": "q5_rain_timing_by_month.csv",
            "Q6": "q6_stops_footpath_and_flood.csv",
            "Q7": "q7_busiest_stops_no_footpath.csv",
            "Q8": "q8_headlines_vs_rain.csv",
        }
        report = []
        for b in blocks:
            title = "Q" + b.splitlines()[0].strip()
            qid = title.split()[0]
            sql = "\n".join(l for l in b.splitlines()[1:] if not l.strip().startswith("--")).strip().rstrip(";")
            try:
                res = pd.read_sql_query(sql, conn) if USE_SQLITE else _mysql_query(cur, sql)
            except Exception as err:                       # e.g. news table not loaded yet
                res = pd.DataFrame({"error": [str(err)]})
            path = sql_dir / files.get(qid, f"{qid.lower()}.csv")
            res.to_csv(path, index=False)
            report.append(f"{title}\n{res.to_string(index=False, max_rows=None)}\n({len(res)} rows)\nstored: outputs/tables/sql/{path.name}\n")
            print(f"\n{title}\n{res.head(12).to_string(index=False)}\n({len(res)} rows) -> outputs/tables/sql/{path.name}")
        full = "\n".join(report)
        (C.TABLES / "sql_results.txt").write_text(full, encoding="utf-8")
        (sql_dir / "query_results.txt").write_text(full, encoding="utf-8")
    conn.close()


def _mysql_query(cur, sql):
    cur.execute(sql)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])


if __name__ == "__main__":
    main()
