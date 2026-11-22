# Data inventory - every field we use, and what type it is

**Structure:** S = structured (rows and columns), SS = semi-structured (JSON / nested / PDF table), U = unstructured (free text)
**Measurement level:** nominal (labels, no order) · ordinal (ordered labels) · discrete (counts) · continuous (measured quantities)

## 1. Air quality - OpenAQ archive of CPCB/KSPCB stations (S, CSV)
| Field | Example | Level | Notes |
|---|---|---|---|
| location_id | 6975 | nominal | a number, but only an identifier - averaging it is meaningless |
| location (station name) | "Silk Board, Bengaluru - KSPCB-3379537" | nominal | text label with a system suffix |
| sensors_id | 12235257 | nominal | |
| parameter | pm25 / pm10 / no2 / co | nominal | |
| datetime | 2025-07-01T18:00:00+05:30 | continuous (interval scale) | end of a 15-min interval, IST |
| value | 45.0 | continuous (ratio) | stored as text in the file -> cast to float |
| units | µg/m³ / ppb | nominal | CO label is wrong (values are mg/m³) - see cleaning log |
| lat, lon | 12.917348 | continuous | |
| **AQI category** (derived, Good -> Satisfactory -> Moderate -> Poor -> Very Poor -> Severe) | Moderate | **ordinal** | CPCB bands; ordered, but the gaps between categories are not equal |
| flag (we create) | ok / spike / flatline_6h | nominal | |

## 2. Weather - Open-Meteo API (SS, JSON -> flattened to S)
| Field | Example | Level | Notes |
|---|---|---|---|
| hourly.time | "2025-07-01T13:00" (UTC, no offset) | continuous (interval) | converted to IST |
| rain, precipitation | 2.4 mm | continuous (ratio) | rain = liquid only |
| temperature_2m | 22.6 °C | continuous (interval) | |
| relative_humidity_2m | 88 % | continuous (ratio, bounded 0-100) | |
| cloud_cover | 100 % | continuous | |
| wind_speed_10m | 11.9 km/h | continuous (ratio) | |
| weather_code | 61 | **nominal** | WMO code; numbers are category labels |
| is_rainy_hour / is_heavy_rain (we create) | 1 | nominal (binary) | thresholds 0.5 mm and 7.6 mm |
| season (we create) | sw_monsoon | nominal (cyclic order) | |

## 3. Bus stops - BMTC GTFS (S, CSV in ZIP)
| Field | Example | Level | Notes |
|---|---|---|---|
| stop_id, stop_code | "00heTtot", 31376 | nominal | |
| stop_name | "Central Silk Board" | nominal | |
| stop_lat, stop_lon | 12.9173 | continuous | |
| service_id | days:1111100 | nominal | encodes which weekdays run |
| trips_wed (we count) | 217 | discrete | trips calling at the stop on a Wednesday |
| routes (we count) | 14 | discrete | |
| dist_to_station_m (we compute) | 640 | continuous | |

## 4. Pedestrian network - OpenStreetMap / Overpass (SS, JSON)
| Field | Example | Level | Notes |
|---|---|---|---|
| element type | way / node | nominal | |
| highway | footway / primary / crossing | nominal | |
| footway, sidewalk tags | sidewalk / separate / no | nominal | |
| surface | paving_stones | nominal | |
| geometry (list of lat/lon) | [{lat, lon}, ...] | continuous (nested) | used to compute lengths |
| sidewalk_m, major_road_m (we compute) | 412 | continuous | metres inside a 300 m circle |
| crossings_n (we compute) | 3 | discrete | |
| sidewalk_per_major_road_m (we compute) | 0.55 | continuous (ratio) | |

## 5. Waterlogging - BBMP PDF (SS, PDF table -> S)
| Field | Example | Level | Notes |
|---|---|---|---|
| zone | South / K-Valley | nominal | |
| severity | severe / moderate | **ordinal** | severe > moderate |
| sl_no | 3 | nominal | row number inside its section |
| name | "SILK BOARD due to choked Rsd..." | nominal / short text | |
| lat, lon | 12.9186389 | continuous | |
| buffer_m | 100 | continuous (ratio) | BBMP's own "vulnerable radius" |
| remarks | "RSD to be desilted" | unstructured text | not analysed |
| nearest_waterlog_m (we compute) | 281 | continuous | |
| waterlog_within_500m (we compute) | 2 | discrete | |

## 6. Calendar - hand-built (S, CSV)
| Field | Example | Level |
|---|---|---|
| date | 2025-10-20 | continuous (interval) |
| weekday | Monday | nominal (cyclic order) |
| holiday_name | Naraka Chaturdashi | nominal |
| holiday_type | general_holiday / festival_on_weekend | nominal |
| is_working_day, is_long_weekend | 1 | nominal (binary) |
| saturday_of_month | 2 | ordinal |

## 7. News - GDELT (U inside SS: headline text in JSON)
| Field | Example | Level | Notes |
|---|---|---|---|
| title | "Paved drain turns perilous road, traps Mahadevapura in monsoon chaos" | **unstructured text** | |
| url, domain | bangaloremirror.indiatimes.com | nominal | |
| seendate | 20250614T013000Z | continuous (interval) | compact UTC string |
| language, sourcecountry | English, India | nominal | |
| tag_* (we create) | tag_waterlogging = 1 | nominal (binary) | keyword dictionary |
| places (we create) | "Silk Board;Hosur Road" | nominal (multi-valued) | |

## Derived analysis fields
| Field | Level | Notes |
|---|---|---|
| slot_ist | continuous (interval) | common hourly key for all time series |
| pm25_z, no2_z | continuous | z-score within station (normalisation) |
| c_pedestrian, c_waterlog, c_pollution | continuous 0-1 | min-max / capped scaling |
| score | continuous 0-100 | priority score; its **rank** is ordinal |
