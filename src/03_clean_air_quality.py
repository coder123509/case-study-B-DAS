"""
Step 3 - Clean the 15-minute air-quality readings and build an hourly table.

Input : data/raw/openaq/openaq_location_<id>_*.csv.gz   (OpenAQ archive, long format)
Output: data/processed/aq_15min_clean.csv.gz   (long: one row per reading, with a flag)
        data/processed/aq_hourly.csv           (wide: one row per station-hour)
        data/processed/stations.csv
        outputs/tables/gap_summary.csv, outputs/figures/fig01_sensor_gaps.png

Every rule below writes a row to docs/cleaning_log.csv with the number of
rows it touched. The order matters: we cast types first, then remove
impossible values, then look for sensor faults, and only then aggregate.
"""
import glob
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
import plot_style as S
from utils import CleaningLog, hour_slot

log = CleaningLog("03_air_quality")
DS = "aq_readings_15min"

# ------------------------------------------------------------------ 1. load
files = sorted(glob.glob(str(C.RAW / "openaq" / "openaq_location_*.csv.gz")))
raw = pd.concat([pd.read_csv(f, dtype=str) for f in files], ignore_index=True)
n_raw = len(raw)
print(f"loaded {n_raw:,} raw rows from {len(files)} files")

# ------------------------------------------------------------------ 2. station ids
# The 'location' text carries an OpenAQ suffix, e.g.
# "Silk Board, Bengaluru - KSPCB-3379537". We split it into a clean name and
# the operator, and keep the numeric location_id as the key.
raw["location_id"] = raw["location_id"].astype(int)
raw["station_name"] = raw["location_id"].map(C.STATIONS)
raw["operator"] = raw["location"].str.extract(r"- (KSPCB|CPCB)")[0]
log.add(DS, "station label has an extra system suffix (e.g. 'Silk Board, Bengaluru - KSPCB-3379537')",
        n_raw, "kept numeric location_id as key; clean name + operator in a stations table",
        "a text label with a changing suffix is not a safe join key")
n_sensor = raw.groupby(["location_id", "parameter"])["sensors_id"].nunique()
log.add(DS, "checked for sensor-ID changes inside the year (one parameter, many sensor ids)",
        int((n_sensor > 1).sum()), "none found, nothing to merge",
        "a mid-year ID change would split one station's series in two")

stations = (raw.groupby("location_id")
            .agg(station_name=("station_name", "first"), operator=("operator", "first"),
                 lat=("lat", "first"), lon=("lon", "first"))
            .reset_index())
stations[["lat", "lon"]] = stations[["lat", "lon"]].astype(float)
stations.to_csv(C.PROCESSED / "stations.csv", index=False)

# ------------------------------------------------------------------ 3. keep pollutants
keep = raw["parameter"].isin(C.POLLUTANTS)
log.add(DS, "parameters not used in this study (so2, o3, no, nox, temperature, RH, wind)",
        int((~keep).sum()), "dropped",
        "the question is about traffic-linked pollution (PM2.5, PM10, NO2, CO); weather comes "
        "from Open-Meteo so every station shares one consistent weather series")
df = raw[keep].copy()

# ------------------------------------------------------------------ 4. type casting
# value is stored as quoted text ("45.0"); datetime is text with an offset.
df["value"] = pd.to_numeric(df["value"], errors="coerce")
log.add(DS, "numbers stored as text in 'value'", len(df),
        f"converted to float ({int(df['value'].isna().sum())} could not be parsed)",
        "text cannot be averaged or compared")
df["ts_ist"] = pd.to_datetime(df["datetime"], format="%Y-%m-%dT%H:%M:%S%z").dt.tz_convert(C.TZ)
log.add(DS, "timestamps are ISO text with a +05:30 offset", len(df),
        "parsed to timezone-aware datetime in Asia/Kolkata",
        "needed for resampling and for joining with UTC weather data")

# CO: OpenAQ labels it 'ppb' but the median is ~0.4 and the max 10. Urban CO in
# ppb is in the hundreds, so these numbers can only be mg/m3 - the unit CPCB
# publishes on its portal. We relabel, we do not convert.
co_median = df.loc[df["parameter"] == "co", "value"].median()
df["unit"] = df["units"].replace({"µg/m³": "ug/m3"})
df.loc[df["parameter"] == "co", "unit"] = "mg/m3"
log.add(DS, f"CO unit label says 'ppb' but values are tiny (median {co_median:.2f})",
        int((df["parameter"] == "co").sum()), "relabelled as mg/m3 (values unchanged)",
        "ambient CO of 0.4 ppb is impossible; 0.4 mg/m3 matches CPCB reports. NO2 keeps the "
        "OpenAQ label (ppb) - we only compare NO2 in z-scores, so its unit does not affect results")

# ------------------------------------------------------------------ 5. duplicates
dup = df.duplicated(["location_id", "parameter", "ts_ist"])
log.add(DS, "duplicate station-parameter-timestamp rows", int(dup.sum()),
        "dropped (keep first)" if dup.sum() else "none found", "a reading must be counted once")
df = df[~dup].sort_values(["location_id", "parameter", "ts_ist"]).reset_index(drop=True)

# ------------------------------------------------------------------ 6. study window
df["slot_ist"] = hour_slot(df["ts_ist"])
in_win = (df["slot_ist"] >= pd.Timestamp(C.STUDY_START_IST, tz=C.TZ)) & \
         (df["slot_ist"] <= pd.Timestamp(C.STUDY_END_IST, tz=C.TZ))
log.add(DS, "readings outside the 12-month study window (buffer days)", int((~in_win).sum()),
        "dropped", "we downloaded one extra day on each side")
df = df[in_win].copy()
n_window = len(df)

# From here on we never delete a row: a bad reading gets value = NaN and a flag,
# so every decision stays visible in the cleaned file.
df["flag"] = "ok"


def set_invalid(mask, flag):
    mask = mask & (df["flag"] == "ok")
    df.loc[mask, "flag"] = flag
    return int(mask.sum())


# ------------------------------------------------------------------ 7. impossible values
n = set_invalid(df["value"] < 0, "negative")
log.add(DS, "negative concentrations (all CO at Bapuji Nagar)", n, "set to NaN, flag=negative",
        "a concentration cannot be below zero; this is an instrument offset error")

# error codes: the same extreme value repeated many times, far above the station's
# normal range (Jayanagar PM2.5 = 794.0 appears again and again while neighbouring
# readings are ~15).
# Rule: a value that is > 10x the station's median for that pollutant AND shows up
# >= 20 times on >= 3 different days is treated as an error code.
okv = df[df["flag"] == "ok"].assign(day=df["ts_ist"].dt.date)
medians = okv.groupby(["location_id", "parameter"])["value"].median().rename("median")
counts = (okv.groupby(["location_id", "parameter", "value"])
          .agg(n=("day", "size"), days=("day", "nunique")).reset_index()
          .merge(medians.reset_index(), on=["location_id", "parameter"]))
codes = counts[(counts["value"] > 10 * counts["median"]) & (counts["n"] >= 20) & (counts["days"] >= 3)]
print("error-code values found:\n", codes.to_string(index=False))
code_mask = df.set_index(["location_id", "parameter", "value"]).index.isin(
    codes.set_index(["location_id", "parameter", "value"]).index)
n = set_invalid(pd.Series(code_mask, index=df.index), "error_code")
log.add(DS, "repeated identical extreme value used as an error code ("
        + "; ".join(f"{C.STATIONS[r.location_id]} {r.parameter}={r.value:g} x{r.n}" for r in codes.itertuples())
        + ")", n, "set to NaN, flag=error_code",
        "a real pollution peak never hits the exact same decimal value dozens of times on different days")

n = set_invalid(df["value"] >= 999, "sentinel_999")
log.add(DS, "values >= 999 (classic sensor-failure sentinel)", n, "set to NaN, flag=sentinel_999",
        "999 / 1000+ readings are fill values, not measurements")

# PM2.5 is a subset of PM10, so PM2.5 > PM10 at the same time is impossible.
w = df[df["parameter"].isin(["pm25", "pm10"]) & (df["flag"] == "ok")] \
    .pivot_table(index=["location_id", "ts_ist"], columns="parameter", values="value")
bad_keys = w[w["pm25"] > w["pm10"]].index
pm_mask = (df["parameter"] == "pm25") & \
    df.set_index(["location_id", "ts_ist"]).index.isin(bad_keys)
n = set_invalid(pd.Series(pm_mask, index=df.index), "pm25_gt_pm10")
log.add(DS, "PM2.5 greater than PM10 at the same timestamp", n,
        "PM2.5 set to NaN, flag=pm25_gt_pm10 (PM10 kept)",
        "physically impossible; usually one of the two monitors is drifting. e.g. Bapuji Nagar "
        "26 Jan 2026 08:45 PM2.5=813 vs PM10=63")

# ------------------------------------------------------------------ 8. flat-lines (stuck sensor)
# NOTE: PM values legitimately repeat 4 times in a row (the 15-min feed repeats the
# hourly value), so a run of 4 is normal. We only call it 'stuck' at >= 24
# identical readings in a row = 6 hours with zero change.
df = df.sort_values(["location_id", "parameter", "ts_ist"])
same = df.groupby(["location_id", "parameter"])["value"].diff().eq(0)
run_id = (~same).cumsum()
run_len = df.groupby(run_id)["value"].transform("size")
share_repeat = same[df["parameter"].isin(["pm25", "pm10"])].mean()
log.add(DS, f"PM readings repeat the previous value {share_repeat:.0%} of the time (runs of 4)",
        int(same.sum()), "kept; noted in V profile",
        "the 15-min PM feed is really an hourly value copied 4 times, so true PM velocity is hourly")
n = set_invalid(run_len >= 24, "flatline_6h")
log.add(DS, "flat-line: same value for >= 24 consecutive readings (6 h)", n,
        "set to NaN, flag=flatline_6h", "real air never stays exactly constant for 6 hours; the "
        "instrument is frozen")

# ------------------------------------------------------------------ 9. spikes vs real events
# A spike = a reading more than 4x the rolling median of the surrounding ~3 hours
# AND above it by a large absolute margin. These are isolated jumps
# (e.g. Jayanagar NO2 1270.7 at 15:45 on 11 Mar 2025, neighbours ~9).
# BUT Diwali nights and New Year's Eve fireworks produce real, sharp peaks. We protect
# those windows so a genuine extreme event is not cleaned away.
MARGIN = {"pm25": 80, "pm10": 150, "no2": 60, "co": 2.0}
GENUINE_EVENTS = [("Deepavali 2025", "2025-10-19 18:00", "2025-10-23 06:00"),
                  ("New Year's Eve", "2025-12-31 20:00", "2026-01-01 04:00")]
ok = df["flag"] == "ok"
med = (df[ok].groupby(["location_id", "parameter"])["value"]
       .transform(lambda s: s.rolling(13, center=True, min_periods=5).median()))
df["roll_med"] = med
margin = df["parameter"].map(MARGIN)
is_spike = ok & (df["value"] > 4 * df["roll_med"]) & (df["value"] - df["roll_med"] > margin)

protected = pd.Series(False, index=df.index)
for name, a, b in GENUINE_EVENTS:
    protected |= df["ts_ist"].between(pd.Timestamp(a, tz=C.TZ), pd.Timestamp(b, tz=C.TZ))
n_protected = int((is_spike & protected).sum())
# how many genuinely extreme readings (above the station's 99th percentile) sit in those windows
p99 = df[ok].groupby(["location_id", "parameter"])["value"].transform(lambda s: s.quantile(0.99)).reindex(df.index)
n_extreme_kept = int((ok & protected & (df["value"] > p99)).sum())
n = set_invalid(is_spike & ~protected, "spike")
log.add(DS, "isolated spikes (> 4x the 3-hour rolling median and far above it)", n,
        "set to NaN, flag=spike",
        "single-reading jumps that vanish 15 min later are electronic glitches; includes the "
        "Bapuji Nagar NO2 jumps at 04:30 on many May mornings (looks like an automatic calibration cycle)")
dw = df[(df["parameter"] == "pm25") & df["ts_ist"].between(
    pd.Timestamp("2025-10-20", tz=C.TZ), pd.Timestamp("2025-10-23", tz=C.TZ))]
log.add(DS, "Deepavali / New Year night peaks (PM2.5 up to "
        f"{dw['value'].max():.0f} ug/m3 on 20-22 Oct 2025): readings above the station's 99th percentile",
        n_extreme_kept,
        f"KEPT - windows protected from the spike rule ({n_protected} would otherwise have been flagged)",
        "fireworks pollution is a real extreme event that residents breathe; removing it would "
        "under-state exposure")
df = df.drop(columns="roll_med")

# examples for the report: 3 real rows of every flag + the Deepavali peaks we kept
ex = df[df["flag"] != "ok"].groupby("flag").head(3)
kept = df[(df["parameter"] == "pm25") & (df["flag"] == "ok") &
          df["ts_ist"].between(pd.Timestamp("2025-10-20", tz=C.TZ), pd.Timestamp("2025-10-23", tz=C.TZ))] \
    .nlargest(3, "value").assign(flag="KEPT: Deepavali peak (genuine event)")
examples = pd.concat([ex, kept])[["location_id", "parameter", "ts_ist", "value", "unit", "flag"]]
examples.insert(1, "station", examples["location_id"].map(C.STATIONS))
examples.to_csv(C.TABLES / "outlier_examples.csv", index=False)

df.loc[df["flag"] != "ok", "value"] = np.nan
print(df["flag"].value_counts())

# save the cleaned long table (used for MySQL 'readings' and as PySpark cross-check)
long_cols = ["location_id", "parameter", "unit", "ts_ist", "slot_ist", "value", "flag"]
df[long_cols].to_csv(C.PROCESSED / "aq_15min_clean.csv.gz", index=False, compression="gzip")

# ------------------------------------------------------------------ 10. resample to hourly
# hourly mean of valid readings in each slot.
# Completeness rule depends on the pollutant:
#   NO2, CO : need >= 2 of 4 quarter-hours (they really change every 15 min)
#   PM2.5, PM10 : 1 reading is enough, because the PM quarter-hours are copies of
#                 one hourly value (see the 'repeat' entry in the cleaning log)
grp = df.groupby(["location_id", "parameter", "slot_ist"])["value"]
hourly = pd.DataFrame({"mean": grp.mean(), "n": grp.count()}).reset_index()
min_n = hourly["parameter"].map({"pm25": 1, "pm10": 1, "no2": 2, "co": 2})
weak = (hourly["n"] < min_n) & (hourly["n"] > 0)
log.add("aq_hourly", "NO2/CO hours with only 1 valid 15-min reading", int(weak.sum()),
        "hour set to missing", "one gas reading is not a reliable hourly average")
log.add("aq_hourly", "PM hours with only 1 valid 15-min reading",
        int(((hourly["n"] == 1) & hourly["parameter"].isin(["pm25", "pm10"])).sum()),
        "kept", "PM quarter-hours repeat one hourly value, so one reading = the hour's value")
hourly.loc[weak, "mean"] = np.nan

wide = hourly.pivot_table(index=["location_id", "slot_ist"], columns="parameter",
                          values="mean", dropna=False).reset_index()
n_read = hourly.pivot_table(index=["location_id", "slot_ist"], columns="parameter",
                            values="n", dropna=False).add_prefix("n_").reset_index()
wide = wide.merge(n_read, on=["location_id", "slot_ist"])

# complete hourly grid: every station x every hour of the year (so gaps become visible)
full_index = pd.MultiIndex.from_product(
    [list(C.STATIONS), pd.date_range(C.STUDY_START_IST, "2026-02-28 23:00", freq="h", tz=C.TZ)],
    names=["location_id", "slot_ist"])
wide = wide.set_index(["location_id", "slot_ist"]).reindex(full_index).reset_index()
print(f"hourly grid: {len(wide):,} station-hours")

# ------------------------------------------------------------------ 11. gaps
gap_rows = []
for (sid, par), _ in hourly.groupby(["location_id", "parameter"]):
    s = wide.loc[wide["location_id"] == sid, par]
    miss = s.isna()
    runs = miss.groupby((~miss).cumsum()).sum()
    runs = runs[runs > 0]
    gap_rows.append({"location_id": sid, "station": C.STATIONS[sid], "parameter": par,
                     "hours_total": len(s), "hours_missing": int(miss.sum()),
                     "pct_missing": round(100 * miss.mean(), 1), "n_gaps": len(runs),
                     "gaps_le_3h": int((runs <= 3).sum()), "gaps_gt_24h": int((runs > 24).sum()),
                     "longest_gap_h": int(runs.max()) if len(runs) else 0})
gaps = pd.DataFrame(gap_rows)
gaps.to_csv(C.TABLES / "gap_summary.csv", index=False)
print(gaps.to_string(index=False))

# Rule: fill short gaps (<= 3 h) by time interpolation, leave long gaps empty.
# 3 h is short enough that PM2.5/NO2 change smoothly in between; anything longer
# (e.g. Bapuji Nagar's ~7-week outage in Nov-Dec 2025) would be invented data.
for par in C.POLLUTANTS:
    before = wide[par].isna()
    filled = (wide.groupby("location_id", group_keys=False)[par]
              .apply(lambda s: s.interpolate(method="linear", limit=3, limit_area="inside")))
    # interpolate(limit=3) would also partly fill long gaps - undo that
    miss_run = before.groupby([wide["location_id"], (~before).cumsum()]).transform("sum")
    filled[before & (miss_run > 3)] = np.nan
    wide[par] = filled
    wide[f"{par}_filled"] = (before & wide[par].notna()).astype(int)
    log.add("aq_hourly", f"{par}: missing hours in gaps of <= 3 h",
            int(wide[f'{par}_filled'].sum()), "linear interpolation (max 3 h)",
            "short outages; values change smoothly over 1-3 h")
    log.add("aq_hourly", f"{par}: missing hours in gaps longer than 3 h",
            int(wide[par].isna().sum()), "left missing (NaN), never filled",
            "filling multi-day outages would invent data; analyses use available hours only")

wide["date_ist"] = wide["slot_ist"].dt.date
wide["hour_ist"] = wide["slot_ist"].dt.hour
wide["weekday"] = wide["slot_ist"].dt.day_name()
wide["month"] = wide["slot_ist"].dt.month
cols = ["location_id", "slot_ist", "date_ist", "hour_ist", "weekday", "month"] + C.POLLUTANTS + \
       [f"{p}_filled" for p in C.POLLUTANTS] + [f"n_{p}" for p in C.POLLUTANTS]
wide[cols].to_csv(C.PROCESSED / "aq_hourly.csv", index=False)

summary = pd.DataFrame({"stage": ["raw rows (all parameters)", "after keeping 4 pollutants",
                                  "inside study window", "valid readings after cleaning",
                                  "hourly station-hours (grid)", "hourly PM2.5 values available"],
                        "rows": [n_raw, int(keep.sum()), n_window, int((df['flag'] == 'ok').sum()),
                                 len(wide), int(wide['pm25'].notna().sum())]})
summary.to_csv(C.TABLES / "aq_row_counts.csv", index=False)
print(summary.to_string(index=False))

# ------------------------------------------------------------------ 12. gap chart
miss_m = (wide.assign(m=wide["slot_ist"].dt.strftime("%Y-%m"))
          .groupby(["location_id", "m"])["pm25"].apply(lambda s: 100 * s.isna().mean())
          .unstack())
miss_m.index = [C.STATIONS[i] for i in miss_m.index]
S.apply()
fig, ax = plt.subplots(figsize=(11, 3.9))
im = ax.imshow(miss_m.values, cmap=S.BLUES, vmin=0, vmax=100, aspect="auto")
ax.set_xticks(range(miss_m.shape[1]), [pd.Timestamp(m).strftime("%b\n%y") for m in miss_m.columns])
ax.set_yticks(range(len(miss_m)), miss_m.index)
ax.grid(False)
for i in range(miss_m.shape[0]):
    for j in range(miss_m.shape[1]):
        v = miss_m.values[i, j]
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                color="white" if v > 50 else S.INK)
pm_gaps = gaps[gaps.parameter == "pm25"].set_index("station")
worst = pm_gaps["pct_missing"].idxmax()
others = pm_gaps.drop(worst)["pct_missing"]
jan_col = [c for c in miss_m.columns if c.endswith("-01")][0]
ax.set_title(f"{worst} lost {pm_gaps.loc[worst, 'pct_missing']:.0f}% of its PM2.5 hours (a Nov-Dec 2025 outage); "
             f"the others are {100 - others.max():.0f}-{100 - others.min():.0f}% complete,\n"
             f"and every station went dark together for ~10 days in {pd.Timestamp(jan_col).strftime('%B %Y')}",
             pad=22)
S.subtitle(ax, "% of hours with no valid PM2.5 reading, by station and month (after cleaning, before gap filling)")
fig.colorbar(im, ax=ax, label="% hours missing", shrink=0.8)
fig.tight_layout()
fig.savefig(C.FIGURES / "fig01_sensor_gaps.png", dpi=150)
log.save()
print("done.")
