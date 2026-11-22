-- =====================================================================
-- Monsoon Last-Mile  -  relational model (MySQL 8)
-- All times are Indian Standard Time (IST, UTC+05:30), stored without
-- an offset. Hourly tables use the "slot" convention from src/utils.py:
-- slot 18:00 = the 60 minutes from 17:30 to 18:30 IST.
--
-- Written in plain SQL (no ENGINE / ENUM / AUTO_INCREMENT) so the same
-- file also runs on SQLite for a quick test:  python src/09_load_mysql.py --sqlite
-- =====================================================================

DROP TABLE IF EXISTS news_articles;
DROP TABLE IF EXISTS pedestrian_features;
DROP TABLE IF EXISTS bus_stops;
DROP TABLE IF EXISTS waterlogging_locations;
DROP TABLE IF EXISTS readings_hourly;
DROP TABLE IF EXISTS readings;
DROP TABLE IF EXISTS weather_hourly;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS stations;

-- one row per air-quality monitoring station
CREATE TABLE stations (
    station_id      INT            NOT NULL,      -- OpenAQ location id
    station_name    VARCHAR(60)    NOT NULL,
    operator        VARCHAR(10),                  -- KSPCB / CPCB
    lat             DECIMAL(9,6)   NOT NULL,
    lon             DECIMAL(9,6)   NOT NULL,
    PRIMARY KEY (station_id)
);

-- one row per day of the study year (built by hand from the Karnataka holiday notification)
CREATE TABLE calendar (
    cal_date             DATE         NOT NULL,
    weekday              VARCHAR(9)   NOT NULL,
    weekday_num          TINYINT      NOT NULL,   -- Mon=0 ... Sun=6
    month                TINYINT      NOT NULL,
    season               VARCHAR(12)  NOT NULL,   -- pre_monsoon / sw_monsoon / ne_monsoon / winter
    is_weekend           TINYINT      NOT NULL,
    holiday_name         VARCHAR(80),
    is_general_holiday   TINYINT      NOT NULL,
    govt_offices_closed  TINYINT      NOT NULL,
    is_working_day       TINYINT      NOT NULL,
    is_long_weekend      TINYINT      NOT NULL,
    PRIMARY KEY (cal_date)
);

-- the cleaned 15-minute readings (largest table, ~488k rows, bad readings kept with value NULL + flag)
CREATE TABLE readings (
    station_id   INT          NOT NULL,
    parameter    VARCHAR(8)   NOT NULL,           -- pm25 / pm10 / no2 / co
    unit         VARCHAR(8)   NOT NULL,
    ts_ist       DATETIME     NOT NULL,           -- end of the 15-min interval
    slot_ist     DATETIME     NOT NULL,           -- hourly slot it belongs to
    value        DECIMAL(9,3),                    -- NULL when flagged
    flag         VARCHAR(16)  NOT NULL,           -- ok / negative / spike / ...
    PRIMARY KEY (station_id, parameter, ts_ist),
    FOREIGN KEY (station_id) REFERENCES stations (station_id)
);

-- hourly averages per station (after gap rules)
CREATE TABLE readings_hourly (
    station_id   INT          NOT NULL,
    slot_ist     DATETIME     NOT NULL,
    cal_date     DATE         NOT NULL,
    hour_ist     TINYINT      NOT NULL,
    weekday      VARCHAR(9)   NOT NULL,
    pm25         DECIMAL(8,2),
    pm10         DECIMAL(8,2),
    no2          DECIMAL(8,2),
    co           DECIMAL(8,3),
    pm25_filled  TINYINT      NOT NULL,           -- 1 = value came from <=3 h interpolation
    PRIMARY KEY (station_id, slot_ist),
    FOREIGN KEY (station_id) REFERENCES stations (station_id),
    FOREIGN KEY (cal_date)   REFERENCES calendar (cal_date)
);

-- city-wide hourly weather (Open-Meteo, flattened from JSON)
CREATE TABLE weather_hourly (
    slot_ist       DATETIME      NOT NULL,
    cal_date       DATE          NOT NULL,
    hour_ist       TINYINT       NOT NULL,
    rain_mm        DECIMAL(6,2)  NOT NULL,
    precip_mm      DECIMAL(6,2)  NOT NULL,
    temp_c         DECIMAL(5,2),
    rh_pct         TINYINT,
    wind_kmh       DECIMAL(5,2),
    weather_code   SMALLINT,                      -- WMO code (nominal)
    is_rainy_hour  TINYINT       NOT NULL,        -- rain >= 0.5 mm
    is_heavy_rain  TINYINT       NOT NULL,        -- rain >= 7.6 mm
    PRIMARY KEY (slot_ist),
    FOREIGN KEY (cal_date) REFERENCES calendar (cal_date)
);

-- BBMP storm-water-drain vulnerable points (2020-21 list)
CREATE TABLE waterlogging_locations (
    wl_id      INT            NOT NULL,
    zone       VARCHAR(40),
    severity   VARCHAR(10)    NOT NULL,           -- severe / moderate
    name       VARCHAR(200),
    lat        DECIMAL(10,7)  NOT NULL,
    lon        DECIMAL(10,7)  NOT NULL,
    buffer_m   SMALLINT,
    PRIMARY KEY (wl_id)
);

-- BMTC stops within 1.5 km of a station
CREATE TABLE bus_stops (
    stop_id             VARCHAR(16)   NOT NULL,
    stop_code           VARCHAR(10),
    stop_name           VARCHAR(120)  NOT NULL,
    lat                 DECIMAL(9,6)  NOT NULL,
    lon                 DECIMAL(9,6)  NOT NULL,
    nearest_station_id  INT           NOT NULL,
    dist_to_station_m   INT           NOT NULL,
    trips_wed           INT           NOT NULL,
    routes              INT           NOT NULL,
    PRIMARY KEY (stop_id),
    FOREIGN KEY (nearest_station_id) REFERENCES stations (station_id)
);

-- what OpenStreetMap shows within 300 m of each stop (1:1 with bus_stops)
CREATE TABLE pedestrian_features (
    stop_id                      VARCHAR(16)  NOT NULL,
    major_road_m                 INT          NOT NULL,
    minor_road_m                 INT          NOT NULL,
    sidewalk_m                   INT          NOT NULL,
    other_footpath_m             INT          NOT NULL,
    no_sidewalk_tagged_m         INT          NOT NULL,
    crossings_n                  INT          NOT NULL,
    sidewalk_per_major_road_m    DECIMAL(5,2),
    crossings_per_km_major       DECIMAL(6,1),
    nearest_waterlog_m           INT          NOT NULL,
    nearest_waterlog_id          INT          NOT NULL,
    waterlog_within_500m         INT          NOT NULL,
    severe_waterlog_within_500m  INT          NOT NULL,
    PRIMARY KEY (stop_id),
    FOREIGN KEY (stop_id)             REFERENCES bus_stops (stop_id),
    FOREIGN KEY (nearest_waterlog_id) REFERENCES waterlogging_locations (wl_id)
);

-- news headlines (GDELT), one row per unique article
CREATE TABLE news_articles (
    article_id        INT           NOT NULL,
    seen_ist          DATETIME      NOT NULL,
    cal_date          DATE          NOT NULL,
    domain            VARCHAR(80),
    language          VARCHAR(20),
    title             VARCHAR(400)  NOT NULL,
    url               VARCHAR(600)  NOT NULL,
    theme_query       VARCHAR(40),
    tag_waterlogging  TINYINT       NOT NULL,
    tag_rain          TINYINT       NOT NULL,
    tag_footpath      TINYINT       NOT NULL,
    tag_bus           TINYINT       NOT NULL,
    tag_traffic       TINYINT       NOT NULL,
    tag_pollution     TINYINT       NOT NULL,
    tag_drains        TINYINT       NOT NULL,
    places            VARCHAR(200),
    PRIMARY KEY (article_id),
    FOREIGN KEY (cal_date) REFERENCES calendar (cal_date)
);

CREATE INDEX idx_readings_slot      ON readings (slot_ist);
CREATE INDEX idx_hourly_date        ON readings_hourly (cal_date);
CREATE INDEX idx_weather_date       ON weather_hourly (cal_date);
CREATE INDEX idx_stops_station      ON bus_stops (nearest_station_id);
