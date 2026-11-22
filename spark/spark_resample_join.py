"""
PySpark job - load, clean, resample and join the largest table (1.27 M rows).

What it does (mirrors src/03 + src/02, but in Spark):
  1. load the 5 raw OpenAQ csv.gz files                     -> count
  2. keep 4 pollutants, cast text -> double / timestamp      -> count
  3. same cleaning rules as pandas (negative, >=999, error code,
     PM2.5>PM10, 6-hour flat-line, isolated spikes)          -> count of valid readings
  4. resample 15-min -> hourly slot per station + completeness rule -> count
  5. flatten the Open-Meteo JSON inside Spark (arrays_zip + explode), UTC -> IST slot
  6. join hourly AQ with hourly weather                       -> count
  7. group by hour-of-day and weekday; rainy vs dry hours
Row counts before/after each step are printed and saved to
outputs/tables/spark_row_counts.csv.

Run from the project root:   python spark/spark_resample_join.py
Needs: pip install pyspark   + Java 11/17 (JAVA_HOME set).
On Windows we only READ with Spark and save the small results with pandas
(.toPandas()), so you do NOT need winutils.exe / HADOOP_HOME.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import config as C                                     # noqa: E402

from pyspark.sql import SparkSession, Window           # noqa: E402
from pyspark.sql import functions as F                 # noqa: E402

t0 = time.time()
spark = (SparkSession.builder
         .appName("monsoon-last-mile")
         .master("local[*]")
         .config("spark.sql.session.timeZone", C.TZ)   # show/compute times in IST
         .config("spark.sql.shuffle.partitions", "16")  # small data -> few partitions
         .config("spark.driver.memory", "4g")
         .getOrCreate())
spark.sparkContext.setLogLevel("WARN")
counts = []


def note(step, df):
    n = df.count()
    counts.append({"step": step, "rows": n})
    print(f"{step:<55} {n:>10,}")
    return n


# ------------------------------------------------------------------ 1. load raw
# explicit file list (posix paths) - Spark's own wildcard handling is unreliable on Windows
files = [f.as_posix() for f in sorted((C.RAW / "openaq").glob("openaq_location_*.csv.gz"))]
print("input files:", [Path(f).name for f in files])
raw = spark.read.option("header", True).option("inferSchema", False).csv(files)
note("1 raw rows (all parameters, 5 stations)", raw)

# ------------------------------------------------------------------ 2. select + cast
df = (raw.filter(F.col("parameter").isin(C.POLLUTANTS))
      .select(F.col("location_id").cast("int").alias("station_id"),
              "parameter",
              F.to_timestamp("datetime", "yyyy-MM-dd'T'HH:mm:ssXXX").alias("ts"),
              F.col("value").cast("double").alias("value")))
# slot = floor_to_hour(ts - 1 min + 30 min)  (same rule as utils.hour_slot)
df = df.withColumn("slot", F.date_trunc("hour", F.col("ts") + F.expr("INTERVAL 29 MINUTES")))
df = df.filter((F.col("slot") >= F.lit(C.STUDY_START_IST).cast("timestamp")) &
               (F.col("slot") <= F.lit(C.STUDY_END_IST).cast("timestamp")))
df = df.dropDuplicates(["station_id", "parameter", "ts"])
note("2 pollutant readings inside the study window", df)

# ------------------------------------------------------------------ 3. cleaning rules
df = df.withColumn("flag", F.when(F.col("value").isNull(), "unparsable")
                            .when(F.col("value") < 0, "negative")
                            .otherwise("ok"))

# error codes: > 10x the station median, seen >= 20 times on >= 3 days
ok = df.filter(F.col("flag") == "ok")
med = ok.groupBy("station_id", "parameter").agg(F.percentile_approx("value", 0.5, 10000).alias("median"))
codes = (ok.groupBy("station_id", "parameter", "value")
         .agg(F.count("*").alias("n"), F.countDistinct(F.to_date("ts")).alias("days"))
         .join(med, ["station_id", "parameter"])
         .filter((F.col("value") > 10 * F.col("median")) & (F.col("n") >= 20) & (F.col("days") >= 3))
         .select("station_id", "parameter", "value", F.lit(1).alias("is_code")))
print("error-code values:", [tuple(r) for r in codes.collect()])
df = (df.join(codes, ["station_id", "parameter", "value"], "left")
        .withColumn("flag", F.when((F.col("flag") == "ok") & (F.col("is_code") == 1), "error_code")
                             .otherwise(F.col("flag")))
        .drop("is_code"))
df = df.withColumn("flag", F.when((F.col("flag") == "ok") & (F.col("value") >= 999), "sentinel_999")
                            .otherwise(F.col("flag")))

# PM2.5 > PM10 at the same timestamp
pm = (df.filter((F.col("flag") == "ok") & F.col("parameter").isin("pm25", "pm10"))
        .groupBy("station_id", "ts").pivot("parameter", ["pm25", "pm10"]).agg(F.first("value"))
        .filter(F.col("pm25") > F.col("pm10"))
        .select("station_id", "ts", F.lit("pm25").alias("parameter"), F.lit(1).alias("bad_pm")))
df = (df.join(pm, ["station_id", "ts", "parameter"], "left")
        .withColumn("flag", F.when((F.col("flag") == "ok") & (F.col("bad_pm") == 1), "pm25_gt_pm10")
                             .otherwise(F.col("flag")))
        .drop("bad_pm"))

# flat-line: >= 24 identical readings in a row
w_ord = Window.partitionBy("station_id", "parameter").orderBy("ts")
df = (df.withColumn("new_run", F.when(F.col("value") == F.lag("value").over(w_ord), 0).otherwise(1))
        .withColumn("run_id", F.sum("new_run").over(w_ord.rowsBetween(Window.unboundedPreceding, 0)))
        .withColumn("run_len", F.count("*").over(Window.partitionBy("station_id", "parameter", "run_id")))
        .withColumn("flag", F.when((F.col("flag") == "ok") & (F.col("run_len") >= 24), "flatline_6h")
                             .otherwise(F.col("flag")))
        .drop("new_run", "run_id", "run_len"))

# spikes: > 4x rolling median of 13 readings AND above it by a margin; protect Deepavali / New Year.
# (pandas takes the rolling median over valid rows only; here the 13-row window may include
#  already-flagged rows as NULLs, so a handful of borderline spikes can differ.)
margin = F.create_map(*[x for k, v in {"pm25": 80.0, "pm10": 150.0, "no2": 60.0, "co": 2.0}.items()
                        for x in (F.lit(k), F.lit(v))])
w_roll = w_ord.rowsBetween(-6, 6)
ok_val = F.when(F.col("flag") == "ok", F.col("value"))
df = df.withColumn("roll_med", F.percentile_approx(ok_val, 0.5, 1000).over(w_roll))
protected = (F.col("ts").between(F.lit("2025-10-19 18:00").cast("timestamp"), F.lit("2025-10-23 06:00").cast("timestamp")) |
             F.col("ts").between(F.lit("2025-12-31 20:00").cast("timestamp"), F.lit("2026-01-01 04:00").cast("timestamp")))
is_spike = ((F.col("flag") == "ok") & (F.col("value") > 4 * F.col("roll_med")) &
            (F.col("value") - F.col("roll_med") > margin[F.col("parameter")]) & ~protected)
df = df.withColumn("flag", F.when(is_spike, "spike").otherwise(F.col("flag"))).drop("roll_med")
df = df.withColumn("value", F.when(F.col("flag") == "ok", F.col("value")))
df.cache()
note("3a readings after cleaning (flagged rows kept as NULL)", df)
note("3b valid readings", df.filter(F.col("flag") == "ok"))
flags = df.groupBy("flag").count().orderBy(F.desc("count"))
flags.show()
flags.toPandas().to_csv(C.TABLES / "spark_cleaning_flags.csv", index=False)

# ------------------------------------------------------------------ 4. resample to hourly
hourly_long = (df.groupBy("station_id", "parameter", "slot")
               .agg(F.avg("value").alias("mean"), F.count("value").alias("n")))
min_n = F.when(F.col("parameter").isin("pm25", "pm10"), 1).otherwise(2)
hourly_long = hourly_long.withColumn("mean", F.when(F.col("n") >= min_n, F.col("mean")))
hourly = (hourly_long.groupBy("station_id", "slot")
          .pivot("parameter", C.POLLUTANTS).agg(F.first("mean")))
note("4 hourly station-slots with at least one reading", hourly)

# ------------------------------------------------------------------ 5. weather JSON -> rows
wj = spark.read.option("multiLine", True).json(
    (C.RAW / "weather" / "openmeteo_bengaluru_hourly_20250228_20260228.json").as_posix())
wx = (wj.select(F.explode(F.arrays_zip("hourly.time", "hourly.rain", "hourly.temperature_2m",
                                       "hourly.relative_humidity_2m")).alias("h"))
        .select(F.col("h.time").alias("time_utc_text"),
                F.col("h.rain").alias("rain_mm"),
                F.col("h.temperature_2m").alias("temp_c"),
                F.col("h.relative_humidity_2m").alias("rh_pct")))
note("5a weather rows after exploding the JSON arrays", wx)
# the text is UTC without an offset -> treat as UTC, then shift into the session time zone (IST)
wx = (wx.withColumn("ts_ist", F.from_utc_timestamp(F.to_timestamp("time_utc_text", "yyyy-MM-dd'T'HH:mm"), C.TZ))
        .withColumn("slot", F.date_trunc("hour", F.col("ts_ist") + F.expr("INTERVAL 29 MINUTES")))
        .withColumn("is_rainy_hour", (F.col("rain_mm") >= C.RAINY_HOUR_MM).cast("int")))
# NOTE: from_utc_timestamp gives the IST wall-clock time; because the session time zone is
# also IST, Spark displays it unchanged. Sanity check: UTC 13:00 must become slot 18:00.
check = wx.filter(F.col("time_utc_text") == "2025-07-01T13:00").select(F.date_format("slot", "HH:mm")).first()[0]
print("sanity check, UTC 13:00 -> slot", check)
assert check == "18:00", "time-zone conversion is wrong - check spark.sql.session.timeZone"
wx = wx.filter((F.col("slot") >= F.lit(C.STUDY_START_IST).cast("timestamp")) &
               (F.col("slot") <= F.lit(C.STUDY_END_IST).cast("timestamp")))
note("5b weather hourly slots inside the study window", wx)

# ------------------------------------------------------------------ 6. join
joined = (hourly.join(wx.select("slot", "rain_mm", "is_rainy_hour", "temp_c"), "slot", "inner")
          .withColumn("hour_ist", F.hour("slot"))
          .withColumn("weekday", F.date_format("slot", "EEEE"))
          .withColumn("month", F.month("slot")))
joined.cache()
note("6 joined station-hours (AQ x weather)", joined)

# ------------------------------------------------------------------ 7. aggregates
# city mean per slot first (so a station with more hours does not dominate), then hour x weekday
city = joined.groupBy("slot", "hour_ist", "weekday").agg(F.avg("pm25").alias("pm25"))
hw = (city.groupBy("weekday", "hour_ist").agg(F.round(F.avg("pm25"), 2).alias("avg_pm25"))
      .orderBy("weekday", "hour_ist"))
note("7a hour x weekday cells", hw)
hw_pd = hw.toPandas().pivot(index="weekday", columns="hour_ist", values="avg_pm25")
hw_pd = hw_pd.reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
hw_pd.to_csv(C.TABLES / "spark_pm25_hour_weekday.csv")

rain = (joined.filter(F.col("hour_ist").between(17, 20))
        .groupBy("month", "is_rainy_hour")
        .agg(F.count("pm25").alias("station_hours"), F.round(F.avg("pm25"), 1).alias("avg_pm25"))
        .orderBy("month", "is_rainy_hour"))
rain.toPandas().to_csv(C.TABLES / "spark_evening_pm25_rain_vs_dry.csv", index=False)
rain.show(30)

import pandas as pd                                     # noqa: E402  (only for saving small results)
pd.DataFrame(counts).to_csv(C.TABLES / "spark_row_counts.csv", index=False)

# cross-check with the pandas pipeline (pandas fills <=3 h gaps, Spark does not,
# so small differences are expected)
pandas_pivot = C.TABLES / "pivot_pm25_hour_weekday_pandas.csv"
if pandas_pivot.exists():
    pp = pd.read_csv(pandas_pivot, index_col=0)
    pp.columns = pp.columns.astype(int)
    diff = (hw_pd - pp).abs()
    print(f"max |spark - pandas| in the hour x weekday pivot: {diff.max().max():.2f} ug/m3")
print(f"done in {time.time() - t0:.0f} s")
spark.stop()
