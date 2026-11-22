"""
Step 8 - Analysis and charts (pandas).

Joins: AQ hourly  x  weather hourly  x  calendar   (on slot_ist / date)
       bus stops  x  pedestrian features  x  waterlogging  x  station AQ
       news monthly x weather monthly

Outputs (outputs/figures, outputs/tables):
  fig02 hour-by-weekday heatmap of PM2.5 (mandatory)
  fig03 when does monsoon rain fall? month x hour heatmap
  fig04 normalised (z-score) daily profiles per station
  fig05 rainy vs dry PM2.5, same station/month/hour   (joins 2 sources)
  fig06 last-mile priority ranking of bus stops
  fig07 waterlogging headlines vs rainfall per month   (joins text + weather)
  plus tables used in the report.

Titles are written as findings. The numbers inside them are computed below,
so if the data changes the title changes with it.
"""
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

S.apply()
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_ORDER = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2]
MONTH_LABEL = {m: pd.Timestamp(2025, m, 1).strftime("%b") for m in range(1, 13)}

# ------------------------------------------------------------------ load + join
aq = pd.read_csv(C.PROCESSED / "aq_hourly.csv")
wx = pd.read_csv(C.PROCESSED / "weather_hourly.csv")
cal = pd.read_csv(C.PROCESSED / "calendar.csv")
stations = pd.read_csv(C.PROCESSED / "stations.csv")

df = (aq.merge(wx[["slot_ist", "rain_mm", "is_rainy_hour", "is_heavy_rain", "season",
                   "temp_c", "rh_pct", "wind_kmh"]], on="slot_ist", how="left", validate="m:1")
        .merge(cal[["date", "is_working_day", "is_general_holiday", "is_long_weekend"]],
               left_on="date_ist", right_on="date", how="left", validate="m:1")
        .drop(columns="date"))
assert df["rain_mm"].notna().all(), "every AQ hour should find its weather hour"
df["station"] = df["location_id"].map(C.STATIONS)

# normalisation: z-score each pollutant within each station, so a station with
# generally cleaner air can be compared with a dirtier one on the same scale
for p in ["pm25", "no2"]:
    g = df.groupby("location_id")[p]
    df[f"{p}_z"] = (df[p] - g.transform("mean")) / g.transform("std")
df.to_csv(C.PROCESSED / "analysis_hourly.csv", index=False)
print(f"joined table: {len(df):,} station-hours")

# ------------------------------------------------------------------ AQI category (ordinal)
# CPCB PM2.5 breakpoints use the 24-hour mean; CPCB needs >= 16 valid hours for a 24-h value.
daily = df.groupby(["location_id", "date_ist"])["pm25"].agg(["mean", "count"]).reset_index()
daily = daily[daily["count"] >= 16]
CATS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
daily["pm25_category"] = pd.cut(daily["mean"], bins=[-0.1, 30, 60, 90, 120, 250, np.inf], labels=CATS)
daily["pm25_category"] = pd.Categorical(daily["pm25_category"], categories=CATS, ordered=True)   # ordinal
daily["season"] = pd.to_datetime(daily["date_ist"]).dt.month.map(C.SEASON_BY_MONTH)
cat_table = pd.crosstab(daily["season"], daily["pm25_category"]).reindex(
    ["pre_monsoon", "sw_monsoon", "ne_monsoon", "winter"]).reindex(columns=CATS, fill_value=0)
cat_table.to_csv(C.TABLES / "pm25_daily_category_by_season.csv")
daily.to_csv(C.PROCESSED / "aq_daily_pm25_category.csv", index=False)
print("station-days by CPCB PM2.5 category:\n", cat_table)

# ------------------------------------------------------------------ fig02 heatmap
city = df.groupby(["slot_ist", "weekday", "hour_ist"], as_index=False)["pm25"].mean()  # mean over stations
heat = city.pivot_table(index="weekday", columns="hour_ist", values="pm25", aggfunc="mean").reindex(DAYS)
heat.round(2).to_csv(C.TABLES / "pivot_pm25_hour_weekday_pandas.csv")
peak_day, peak_hour = heat.stack().idxmax()
low_day, low_hour = heat.stack().idxmin()
eve = heat.loc[:, 19:22].mean().mean()
aft = heat.loc[:, 13:17].mean().mean()

fig, ax = plt.subplots(figsize=(11, 3.9))
im = ax.imshow(heat.values, cmap=S.BLUES, aspect="auto")
ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)])
ax.set_yticks(range(7), [d[:3] for d in DAYS])
ax.grid(False)
for i in range(7):
    for j in range(24):
        v = heat.values[i, j]
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7.5,
                color="white" if v > np.nanpercentile(heat.values, 70) else S.INK)
ax.set_xlabel("hour of day (IST)")
ax.set_title(f"Bengaluru's PM2.5 peaks at {peak_hour:02d}:00 and stays high until after 22:00 - "
             f"evenings average {eve:.0f} ug/m3 vs {aft:.0f} in the afternoon", pad=22)
S.subtitle(ax, "Mean PM2.5 (ug/m3) across 5 CPCB/KSPCB stations, Mar 2025 - Feb 2026, by weekday and hour")
fig.colorbar(im, ax=ax, label="PM2.5 ug/m3", shrink=0.85)
fig.tight_layout()
fig.savefig(C.FIGURES / "fig02_heatmap_pm25_hour_weekday.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------------ fig03 when does rain fall
w = wx.copy()
p_rain = (w.pivot_table(index="month", columns="hour_ist", values="is_rainy_hour", aggfunc="mean")
          .reindex(MONTH_ORDER) * 100)
p_rain.round(1).to_csv(C.TABLES / "rain_probability_month_hour.csv")
mon = w[w["month"].isin([5, 6, 7, 8, 9, 10])]
by_hour = mon.groupby("hour_ist")["is_rainy_hour"].mean() * 100
wettest_hours = by_hour.sort_values(ascending=False).index[:4].sort_values()
share_pm = 100 * mon.loc[mon["hour_ist"].between(14, 19), "rain_mm"].sum() / mon["rain_mm"].sum()

fig, ax = plt.subplots(figsize=(11, 4.3))
im = ax.imshow(p_rain.values, cmap=S.BLUES, aspect="auto", vmin=0)
ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)])
ax.set_yticks(range(12), [MONTH_LABEL[m] + (" 25" if m >= 3 else " 26") for m in MONTH_ORDER])
ax.grid(False)
for hours, label in ((C.MORNING_PEAK, "morning commute"), (C.EVENING_PEAK, "evening commute")):
    ax.add_patch(plt.Rectangle((hours[0] - 0.5, -0.5), len(hours), 12, fill=False,
                               edgecolor=S.SERIES[1], lw=1.6))
    ax.text(hours[0] - 0.35, 11.35, label, color=S.SERIES[1], fontsize=8, va="center")
ax.set_xlabel("hour of day (IST)")
ax.set_title(f"Monsoon rain arrives in the afternoon: {share_pm:.0f}% of May-Oct rain falls between 14:00 and "
             f"20:00, the hours leading into the evening commute", pad=22)
S.subtitle(ax, "% of hours with rain >= 0.5 mm (Open-Meteo hourly, Bengaluru centre), by month and hour")
fig.colorbar(im, ax=ax, label="% of hours rainy", shrink=0.85)
fig.tight_layout()
fig.savefig(C.FIGURES / "fig03_rain_timing_month_hour.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------------ fig04 normalised profiles
prof = df[df["is_working_day"] == 1].groupby(["location_id", "hour_ist"])["pm25_z"].mean().unstack(0)
raw_mean = df.groupby("location_id")["pm25"].mean()
fig, ax = plt.subplots(figsize=(10, 4.4))
for sid in prof.columns:
    ax.plot(prof.index, prof[sid], color=S.STATION_COLOR[sid], label=f"{C.STATIONS[sid]} (mean {raw_mean[sid]:.0f})")
ax.axhline(0, color=S.AXIS, lw=1)
for h in C.EVENING_PEAK:
    ax.axvspan(h - 0.5, h + 0.5, color=S.GRID, alpha=0.5, lw=0)
ax.set_xlim(0, 23)
ax.set_xticks(range(0, 24, 2))
ax.set_xlabel("hour of day (IST), working days only")
ax.set_ylabel("PM2.5 z-score (within station)")
eve_z = prof.loc[20:21].mean().min()
ax.set_title("With each station's own level removed, all five share one rhythm:\n"
             "a morning bump at 08-09h and a bigger evening peak at 20-21h", pad=22)
S.subtitle(ax, "z = (hourly PM2.5 - station mean) / station std. Legend shows each station's raw annual mean in ug/m3")
ax.legend(loc="lower left", ncol=3, fontsize=8)
fig.tight_layout()
fig.savefig(C.FIGURES / "fig04_normalised_station_profiles.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------------ fig05 rain vs PM2.5
# Hold station, month and hour constant: compare rainy vs dry hours INSIDE each
# (station, month, hour) cell, then summarise the differences. This removes the
# obvious confounders (monsoon months are cleaner anyway; afternoons are cleaner anyway).
rows = []
for p in ["pm25", "no2"]:
    sub = df.dropna(subset=[p])
    g = sub.groupby(["location_id", "month", "hour_ist", "is_rainy_hour"])[p].agg(["mean", "count"]).unstack()
    g = g[(g[("count", 1)] >= 2) & (g[("count", 0)] >= 5)]          # need a few rainy and dry hours
    cell = pd.DataFrame({"pollutant": p, "rainy": g[("mean", 1)], "dry": g[("mean", 0)],
                         "n_rainy": g[("count", 1)]}).reset_index()
    cell["diff"] = cell["rainy"] - cell["dry"]
    cell["pct"] = 100 * cell["diff"] / cell["dry"]
    rows.append(cell)
strata = pd.concat(rows)
strata.to_csv(C.TABLES / "rain_effect_strata.csv", index=False)
eff = strata.groupby("pollutant").agg(cells=("diff", "size"), median_diff=("diff", "median"),
                                      median_pct=("pct", "median"),
                                      share_lower=("diff", lambda s: (s < 0).mean()))
eff.round(2).to_csv(C.TABLES / "rain_effect_summary.csv")
print(eff.round(2))
pm = strata[strata["pollutant"] == "pm25"]
n_cells = pm.groupby("month").size()
ok_months = [m for m in MONTH_ORDER if n_cells.get(m, 0) >= 5]      # too few cells = no estimate
by_month = pm.groupby("month")["pct"].median().reindex(ok_months)

fig, ax = plt.subplots(figsize=(9.5, 4.2))
x = np.arange(len(by_month))
colors = [S.SERIES[0] if v < 0 else S.SERIES[7] for v in by_month.values]
ax.bar(x, by_month.values, color=colors, width=0.6)
for xi, (m, v) in zip(x, by_month.items()):
    ax.text(xi, v + (-2.5 if v < 0 else 1), f"{v:.0f}%\n(n={n_cells[m]})", ha="center",
            va="top" if v < 0 else "bottom", fontsize=8, color=S.INK_2)
ax.axhline(0, color=S.INK_2, lw=1)
ax.set_xticks(x, [MONTH_LABEL[m] for m in by_month.index])
ax.set_ylabel("PM2.5: rainy vs dry hour (%)")
ax.set_ylim(min(-60, by_month.min() - 12), max(20, by_month.max() + 12))
e = eff.loc["pm25"]
ax.set_title(f"Rain washes PM2.5 out of the air: compared at the same station, month and hour,\n"
             f"rainy hours are {abs(e.median_pct):.0f}% cleaner ({e.share_lower:.0%} of comparisons lower)", pad=38)
S.subtitle(ax, "Median % difference per (station, month, hour) cell with >= 2 rainy and >= 5 dry hours; "
               "n = cells; months with < 5 cells left out.\nAssociation, not proof of cause")
fig.tight_layout()
fig.savefig(C.FIGURES / "fig05_rain_vs_pm25_same_hour.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------------ stop priority score
stops = pd.read_csv(C.PROCESSED / "bus_stops.csv", dtype={"stop_id": str})
feat = pd.read_csv(C.PROCESSED / "pedestrian_features.csv", dtype={"stop_id": str})
st = stops.merge(feat, on="stop_id", validate="1:1")

# station pollution during the evening commute on working days (whole year)
ev = df[df["hour_ist"].isin(C.EVENING_PEAK) & (df["is_working_day"] == 1)]
ev_pm = ev.groupby("location_id")["pm25"].mean()
st["station_evening_pm25"] = st["nearest_station_id"].map(ev_pm)


def minmax(s):
    return (s - s.min()) / (s.max() - s.min())


# 1 = worst. Each component is scaled 0-1 so they can be averaged.
st["c_footpath_gap"] = 1 - (st["sidewalk_per_major_road_m"] / 2).clip(0, 1)     # 2.0 = both sides mapped
cr90 = st["crossings_per_km_major"].quantile(0.9)
st["c_crossing_gap"] = 1 - (st["crossings_per_km_major"] / cr90).clip(0, 1)
st["c_pedestrian"] = st[["c_footpath_gap", "c_crossing_gap"]].mean(axis=1)
st["c_waterlog"] = (1 - st["nearest_waterlog_m"] / 1000).clip(0, 1)              # 1 = on a flood point, 0 = > 1 km
st["c_pollution"] = minmax(st["station_evening_pm25"])
WEIGHTS = {"c_pedestrian": 1 / 3, "c_waterlog": 1 / 3, "c_pollution": 1 / 3}
st["score"] = 100 * sum(st[c] * w for c, w in WEIGHTS.items())
st["busy"] = (st["trips_wed"] >= st["trips_wed"].median()).astype(int)
st["rank_all"] = st["score"].rank(ascending=False, method="min").astype(int)

# sensitivity: does the top-10 survive different weights?
top10 = set(st[st["busy"] == 1].nlargest(10, "score")["stop_id"])
sens = []
for name, wts in {"pedestrian-heavy 0.5/0.3/0.2": (0.5, 0.3, 0.2),
                  "waterlog-heavy 0.3/0.5/0.2": (0.3, 0.5, 0.2),
                  "no pollution 0.5/0.5/0": (0.5, 0.5, 0.0)}.items():
    s2 = st["c_pedestrian"] * wts[0] + st["c_waterlog"] * wts[1] + st["c_pollution"] * wts[2]
    alt = set(st.assign(s2=s2)[st["busy"] == 1].nlargest(10, "s2")["stop_id"])
    sens.append({"weights": name, "same_stops_in_top10": len(top10 & alt)})
pd.DataFrame(sens).to_csv(C.TABLES / "score_sensitivity.csv", index=False)
print(pd.DataFrame(sens))

st["station"] = st["nearest_station_id"].map(C.STATIONS)
cols = ["rank_all", "stop_id", "stop_name", "station", "lat", "lon", "trips_wed", "routes", "busy",
        "sidewalk_per_major_road_m", "crossings_per_km_major", "nearest_waterlog_m",
        "waterlog_within_500m", "station_evening_pm25", "c_pedestrian", "c_waterlog",
        "c_pollution", "score"]
ranking = st.sort_values("score", ascending=False)[cols]
ranking.round(3).to_csv(C.TABLES / "stop_priority_ranking.csv", index=False)

area = st.groupby("station").agg(stops=("stop_id", "count"), mean_score=("score", "mean"),
                                 median_sidewalk_ratio=("sidewalk_per_major_road_m", "median"),
                                 stops_within_500m_of_waterlog=("waterlog_within_500m", lambda s: int((s > 0).sum())),
                                 evening_pm25=("station_evening_pm25", "first"),
                                 wed_trips_total=("trips_wed", "sum")).sort_values("mean_score", ascending=False)
area.round(2).to_csv(C.TABLES / "area_summary.csv")
print(area.round(2))

# ------------------------------------------------------------------ fig06 priority chart
# one bar per LOCATION: stops with the same name in the same area (bays / both sides
# of the road) are merged - best score, summed trips - so one interchange cannot fill the chart
loc_rank = (st[st["busy"] == 1].sort_values("score", ascending=False)
            .groupby(["stop_name", "station"], as_index=False)
            .agg(score=("score", "first"), c_pedestrian=("c_pedestrian", "first"),
                 c_waterlog=("c_waterlog", "first"), c_pollution=("c_pollution", "first"),
                 trips_wed=("trips_wed", "sum"), n_stops=("stop_id", "count"))
            .sort_values("score", ascending=False))
loc_rank.round(3).to_csv(C.TABLES / "location_priority_ranking.csv", index=False)
top = loc_rank.head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(10, 6))
y = np.arange(len(top))
left = np.zeros(len(top))
parts = [("c_pedestrian", "mapped footpath / crossing gap", S.SERIES[0]),
         ("c_waterlog", "near a BBMP flood point", S.SERIES[2]),
         ("c_pollution", "evening PM2.5 at nearest station", S.SERIES[1])]
for col, label, color in parts:
    val = 100 * top[col].values / 3
    ax.barh(y, val, left=left, color=color, label=label, height=0.62, edgecolor=S.SURFACE, linewidth=2)
    left += val
for yi, r in zip(y, top.itertuples()):
    ax.text(r.score + 0.8, yi, f"{r.score:.0f}  ({r.trips_wed} trips/Wed)", va="center", fontsize=8, color=S.INK_2)
ax.set_yticks(y, [f"{r.stop_name[:32]} - {r.station}" for r in top.itertuples()], fontsize=8.5)
ax.set_xlim(0, 118)
ax.set_xlabel("last-mile priority score (0-100, equal weights)", labelpad=2)
lead = area.index[0]
top_areas = top["station"].value_counts()
ax.set_title(f"The top-15 busy stop locations sit around {top_areas.index[0]} ({top_areas.iloc[0]}) and "
             f"{top_areas.index[1]} ({top_areas.iloc[1]}):\nalmost no mapped footpath and a BBMP flood point "
             "within a short walk", pad=40)
S.subtitle(ax, "Busy stops (>= median Wednesday trips), same-name stops merged.\n"
               "Score = mean of 3 components scaled 0-1. A screening tool, not a measure of danger.")
ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=3, fontsize=8)
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(C.FIGURES / "fig06_stop_priority_ranking.png", dpi=150)
plt.close(fig)

# ------------------------------------------------------------------ fig07 news vs rain (two panels, one axis each)
news_m = C.PROCESSED / "news_monthly.csv"
if news_m.exists():
    nm = pd.read_csv(news_m)
    cov = pd.read_csv(C.TABLES / "news_coverage.csv")
    wl_status = cov[cov["theme"] == "waterlogging"].set_index("month")["status"]
    rain_m = w.assign(m=pd.to_datetime(w["date_ist"]).dt.strftime("%Y-%m")).groupby("m")["rain_mm"].sum()
    nm = nm.set_index("month").reindex(rain_m.index)
    nm["waterlogging"] = nm["waterlogging"].fillna(0)
    status = wl_status.reindex(rain_m.index).fillna("failed")
    nm.loc[status == "failed", "waterlogging"] = np.nan          # unknown, not zero
    good = nm["waterlogging"].notna()
    corr = np.corrcoef(rain_m[good].values, nm.loc[good, "waterlogging"].values)[0, 1]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.5, 5.6), sharex=True)
    xm = np.arange(len(rain_m))
    a1.bar(xm, rain_m.values, color=S.SERIES[0], width=0.6)
    a1.set_ylabel("rain (mm)")
    a2.bar(xm, nm["waterlogging"].fillna(0).values, color=S.SERIES[2], width=0.6)
    for xi, (m, st_) in enumerate(status.items()):
        if st_ == "failed":
            a2.text(xi, 1, "no\ndata", ha="center", va="bottom", fontsize=7.5, color=S.INK_2)
        elif st_ == "capped_250":
            a2.text(xi, nm.loc[m, "waterlogging"] + 1, ">=", ha="center", va="bottom", fontsize=8, color=S.INK_2)
    a2.set_ylabel("headlines")
    a2.set_xticks(xm, [pd.Timestamp(m + "-01").strftime("%b\n%y") for m in rain_m.index])
    top_m = pd.Timestamp(nm["waterlogging"].idxmax() + "-01").strftime("%B")
    a1.set_title(f"Waterlogging headlines rise and fall with rainfall (r = {corr:.2f} over {int(good.sum())} months "
                 f"with data); {top_m} had the most", pad=22)
    S.subtitle(a1, "Top: monthly rain, Open-Meteo. Bottom: GDELT headlines about Bengaluru tagged 'waterlogging/flood'; "
                   "'no data' = API refused, '>=' = 250-row cap")
    fig.tight_layout()
    fig.savefig(C.FIGURES / "fig07_news_vs_rain.png", dpi=150)
    plt.close(fig)
    pd.DataFrame({"rain_mm": rain_m, "waterlog_headlines": nm["waterlogging"]}).to_csv(C.TABLES / "news_vs_rain_monthly.csv")

# ------------------------------------------------------------------ 'when' table for the commissioner
when = []
for m in MONTH_ORDER:
    for wname, hours in {"morning 08-10": C.MORNING_PEAK, "evening 17-20": C.EVENING_PEAK}.items():
        ww = w[(w["month"] == m) & w["hour_ist"].isin(hours)]
        dd = df[(df["month"] == m) & df["hour_ist"].isin(hours) & (df["is_rainy_hour"] == 0)]
        when.append({"month": MONTH_LABEL[m], "window": wname,
                     "pct_hours_rainy": round(100 * ww["is_rainy_hour"].mean(), 1),
                     "rain_mm_total": round(ww["rain_mm"].sum(), 1),
                     "pm25_dry_hours_mean": round(dd["pm25"].mean(), 1)})
pd.DataFrame(when).to_csv(C.TABLES / "when_windows.csv", index=False)
print(pd.DataFrame(when).to_string(index=False))
print("figures saved to", C.FIGURES.relative_to(C.ROOT))
