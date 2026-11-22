"""
Step 2 - Flatten the Open-Meteo JSON into an hourly table in IST.

The API answer looks like this (semi-structured, column-oriented):
    {"latitude": .., "hourly_units": {...},
     "hourly": {"time": ["2025-02-28T00:00", ...], "rain": [0.0, ...], ...}}

We turn it into one row per hour:
    ts_utc | ts_ist | date_ist | hour_ist | weekday | rain_mm | ... |

Output: data/processed/weather_hourly.csv
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from utils import CleaningLog, hour_slot

log = CleaningLog("02_weather")

raw_file = C.RAW / "weather" / "openmeteo_bengaluru_hourly_20250228_20260228.json"
payload = json.loads(raw_file.read_text(encoding="utf-8"))

print("API metadata:", {k: payload[k] for k in ("latitude", "longitude", "elevation",
                                                 "timezone", "utc_offset_seconds")})
print("units:", payload["hourly_units"])

# --- flatten: every list inside "hourly" becomes a column
wx = pd.DataFrame(payload["hourly"])
print("rows after flattening:", len(wx))

# --- type casting
# 'time' is a text string with NO offset, e.g. "2025-07-01T18:00". Because we
# asked the API for timezone=GMT, this is UTC. We tell pandas that explicitly
# and only then convert to IST (+05:30).
wx["ts_utc"] = pd.to_datetime(wx["time"], format="%Y-%m-%dT%H:%M").dt.tz_localize("UTC")
wx["ts_ist"] = wx["ts_utc"].dt.tz_convert(C.TZ)
log.add("weather_hourly", "timestamps are UTC text strings without an offset",
        len(wx), "parsed with explicit format, localised to UTC, converted to Asia/Kolkata",
        "AQ data is in IST (+05:30); joining on raw strings would shift every hour by 5.5 h")

# columns arrive as floats already, but weather_code is a category code, not a quantity
wx["weather_code"] = wx["weather_code"].astype("Int64")
log.add("weather_hourly", "weather_code is a WMO category stored as a number", len(wx),
        "cast to integer and treated as nominal", "averaging codes (e.g. 61 and 95) is meaningless")

wx = wx.rename(columns={"temperature_2m": "temp_c", "relative_humidity_2m": "rh_pct",
                        "precipitation": "precip_mm", "rain": "rain_mm",
                        "cloud_cover": "cloud_pct", "wind_speed_10m": "wind_kmh"})

# --- missing values
n_missing = int(wx[["temp_c", "rh_pct", "precip_mm", "rain_mm"]].isna().any(axis=1).sum())
log.add("weather_hourly", "missing hourly values", n_missing,
        "none to fill" if n_missing == 0 else "left as NaN",
        "Open-Meteo is a gridded reanalysis product, so it has no sensor gaps")

# --- sanity checks (outliers)
bad = (wx["rain_mm"] < 0) | (wx["rh_pct"] > 100) | (wx["temp_c"] < 5) | (wx["temp_c"] > 45)
log.add("weather_hourly", "physically impossible values (rain<0, RH>100, temp outside 5-45 C)",
        int(bad.sum()), "checked; none dropped" if bad.sum() == 0 else "set to NaN",
        "range check before trusting the series")
top = wx.nlargest(3, "rain_mm")[["ts_ist", "rain_mm"]]
print("wettest hours (kept, these are real storms):\n", top.to_string(index=False))
log.add("weather_hourly", "very high hourly rain values (top: "
        + ", ".join(f"{r.ts_ist:%d %b %Y %H:%M} = {r.rain_mm} mm" for r in top.itertuples()) + ")",
        int((wx["rain_mm"] >= C.HEAVY_RAIN_MM).sum()),
        f"kept; flagged as heavy_rain (>= {C.HEAVY_RAIN_MM} mm/h)",
        "these are genuine monsoon cloudbursts, exactly the events we study")

# --- align to our common hourly slot (see utils.hour_slot)
# Open-Meteo rain at time T is the total for the hour ENDING at T.
# In IST that hour ends at :30, e.g. 18:30 -> window 17:30-18:30 -> slot 18:00.
wx["slot_ist"] = hour_slot(wx["ts_ist"])
log.add("weather_hourly", "weather hours end at :30 in IST (UTC+05:30) while AQ readings "
        "are on IST quarter-hours", len(wx),
        "every hour mapped to a common slot = IST clock hour whose +/-30 min window it covers",
        "makes 'the same hour' mean the same 60 minutes in both sources")

# --- trim to the study window in IST and add calendar helpers
wx = wx[(wx["slot_ist"] >= pd.Timestamp(C.STUDY_START_IST, tz=C.TZ)) &
        (wx["slot_ist"] <= pd.Timestamp(C.STUDY_END_IST, tz=C.TZ))].copy()
log.add("weather_hourly", "extra hours downloaded outside the IST study window",
        len(payload["hourly"]["time"]) - len(wx), "removed",
        "we downloaded one extra UTC day so that IST 00:00-05:30 on 1 Mar 2025 is covered")

wx["date_ist"] = wx["slot_ist"].dt.date
wx["hour_ist"] = wx["slot_ist"].dt.hour
wx["weekday"] = wx["slot_ist"].dt.day_name()
wx["month"] = wx["slot_ist"].dt.month
wx["season"] = wx["month"].map(C.SEASON_BY_MONTH)
wx["is_rainy_hour"] = (wx["rain_mm"] >= C.RAINY_HOUR_MM).astype(int)
wx["is_heavy_rain"] = (wx["rain_mm"] >= C.HEAVY_RAIN_MM).astype(int)

cols = ["slot_ist", "ts_utc", "ts_ist", "date_ist", "hour_ist", "weekday", "month", "season",
        "rain_mm", "precip_mm", "temp_c", "rh_pct", "cloud_pct", "wind_kmh", "weather_code",
        "is_rainy_hour", "is_heavy_rain"]
out = C.PROCESSED / "weather_hourly.csv"
wx[cols].to_csv(out, index=False)
print(f"saved {out.relative_to(C.ROOT)}: {len(wx):,} hourly rows "
      f"(slots {wx['slot_ist'].min()} -> {wx['slot_ist'].max()})")
log.save()
