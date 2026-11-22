# ER diagram

Nine tables, defined in [`sql/schema.sql`](../sql/schema.sql). GitHub renders the diagram below;
a PNG copy is in [`docs/er_diagram.png`](er_diagram.png) for the report.

```mermaid
erDiagram
    stations ||--o{ readings : "measures"
    stations ||--o{ readings_hourly : "averaged into"
    stations ||--o{ bus_stops : "is nearest AQ station of"
    calendar ||--o{ readings_hourly : "date"
    calendar ||--o{ weather_hourly : "date"
    calendar ||--o{ news_articles : "date"
    weather_hourly ||--o{ readings_hourly : "same slot_ist"
    bus_stops ||--|| pedestrian_features : "300 m walk area"
    waterlogging_locations ||--o{ pedestrian_features : "nearest flood point"

    stations {
        INT station_id PK
        VARCHAR station_name
        VARCHAR operator
        DECIMAL lat
        DECIMAL lon
    }
    readings {
        INT station_id PK,FK
        VARCHAR parameter PK
        DATETIME ts_ist PK
        DATETIME slot_ist
        VARCHAR unit
        DECIMAL value
        VARCHAR flag
    }
    readings_hourly {
        INT station_id PK,FK
        DATETIME slot_ist PK
        DATE cal_date FK
        TINYINT hour_ist
        VARCHAR weekday
        DECIMAL pm25
        DECIMAL pm10
        DECIMAL no2
        DECIMAL co
        TINYINT pm25_filled
    }
    weather_hourly {
        DATETIME slot_ist PK
        DATE cal_date FK
        TINYINT hour_ist
        DECIMAL rain_mm
        DECIMAL temp_c
        TINYINT rh_pct
        SMALLINT weather_code
        TINYINT is_rainy_hour
        TINYINT is_heavy_rain
    }
    calendar {
        DATE cal_date PK
        VARCHAR weekday
        VARCHAR season
        VARCHAR holiday_name
        TINYINT is_general_holiday
        TINYINT is_working_day
        TINYINT is_long_weekend
    }
    bus_stops {
        VARCHAR stop_id PK
        VARCHAR stop_name
        DECIMAL lat
        DECIMAL lon
        INT nearest_station_id FK
        INT dist_to_station_m
        INT trips_wed
        INT routes
    }
    pedestrian_features {
        VARCHAR stop_id PK,FK
        INT major_road_m
        INT sidewalk_m
        INT crossings_n
        DECIMAL sidewalk_per_major_road_m
        INT nearest_waterlog_m
        INT nearest_waterlog_id FK
        INT waterlog_within_500m
    }
    waterlogging_locations {
        INT wl_id PK
        VARCHAR zone
        VARCHAR severity
        VARCHAR name
        DECIMAL lat
        DECIMAL lon
        SMALLINT buffer_m
    }
    news_articles {
        INT article_id PK
        DATETIME seen_ist
        DATE cal_date FK
        VARCHAR domain
        VARCHAR title
        TINYINT tag_waterlogging
        VARCHAR places
    }
```

## How the keys work

| Relationship | Key | Note |
|---|---|---|
| stations -> readings / readings_hourly | `station_id` (OpenAQ location id) | the text name carries a changing suffix, so it is never used as a key |
| readings_hourly <-> weather_hourly | `slot_ist` | both sources are mapped to the same hourly slot (17:30-18:30 IST = slot 18:00). Not a declared FK because weather is city-wide, but it is the main join |
| readings_hourly / weather_hourly / news_articles -> calendar | `cal_date` | IST date, so a UTC 22:00 news item lands on the next Bengaluru day |
| stations -> bus_stops | `nearest_station_id` | computed by distance (stops within 1.5 km) |
| bus_stops -> pedestrian_features | `stop_id` (1:1) | metrics of what OSM shows within 300 m |
| waterlogging_locations -> pedestrian_features | `nearest_waterlog_id` | computed by distance |
