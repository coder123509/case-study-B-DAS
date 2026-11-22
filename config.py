"""
Shared settings for the Monsoon Last-Mile project.

Every script imports from here, so if you want to change the study window,
add a station or move a folder, change it ONCE in this file.
"""
from pathlib import Path

# ---------------------------------------------------------------- folders
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
MANUAL = DATA / "manual"          # files we typed / built by hand
INTERIM = DATA / "interim"        # flattened but not yet cleaned
PROCESSED = DATA / "processed"    # cleaned, analysis-ready
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
TABLES = OUTPUTS / "tables"
DOCS = ROOT / "docs"

for _p in (RAW, MANUAL, INTERIM, PROCESSED, FIGURES, TABLES):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- study window
# 12 full months in IST. We download one extra day on each side because the
# weather API works in UTC and the 00:00-05:30 IST hours of 1 March 2025
# belong to 28 Feb in UTC.
STUDY_START_IST = "2025-03-01 00:00"
STUDY_END_IST = "2026-02-28 23:59"
DOWNLOAD_START = "2025-02-28"
DOWNLOAD_END = "2026-03-01"

TZ = "Asia/Kolkata"

# ---------------------------------------------------------------- AQ stations
# OpenAQ location ids for the CPCB/KSPCB continuous monitoring stations (CAAQMS)
# we use. Ids were found by reading the station name inside the OpenAQ S3
# archive files (see docs/source_register.md).
STATIONS = {
    6973: "Jayanagar 5th Block",
    6974: "Bapuji Nagar",
    6975: "Silk Board",
    6983: "Hombegowda Nagar",
    6984: "Hebbal",
}

# pollutants we keep for the analysis (OpenAQ parameter names)
POLLUTANTS = ["pm25", "pm10", "no2", "co"]

# ---------------------------------------------------------------- weather point
# Bengaluru city centre (near Vidhana Soudha). Open-Meteo snaps it to the
# nearest model grid cell, so the returned lat/lon is slightly different.
WEATHER_LAT, WEATHER_LON = 12.9716, 77.5946

# ---------------------------------------------------------------- spatial rules
STOP_RADIUS_FROM_STATION_M = 1500   # bus stops "near" an AQ station
WALK_BUFFER_M = 300                 # ~4 minute walk around a bus stop
WATERLOG_RADIUS_M = 500             # waterlogging point "near" a stop
OSM_QUERY_RADIUS_M = 1800           # = 1500 + 300, so every buffer is fully covered

# ---------------------------------------------------------------- rain rules
# Open-Meteo hourly rain (mm in that hour). Thresholds follow the usual
# hourly intensity bands (light < 2.5 mm/h, moderate 2.5-7.6, heavy > 7.6),
# with a "rainy hour" being anything >= 0.5 mm so drizzle noise is ignored.
RAINY_HOUR_MM = 0.5
HEAVY_RAIN_MM = 7.6

# commuting windows used in the analysis (IST, hour-of-day labels)
MORNING_PEAK = [8, 9, 10]
EVENING_PEAK = [17, 18, 19, 20]

# seasons (IMD convention for south India)
SEASON_BY_MONTH = {
    1: "winter", 2: "winter",
    3: "pre_monsoon", 4: "pre_monsoon", 5: "pre_monsoon",
    6: "sw_monsoon", 7: "sw_monsoon", 8: "sw_monsoon", 9: "sw_monsoon",
    10: "ne_monsoon", 11: "ne_monsoon", 12: "ne_monsoon",
}
