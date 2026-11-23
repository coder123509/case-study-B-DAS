-- =====================================================================
-- Monsoon Last-Mile - analysis queries
-- Run in MySQL Workbench after `python src/09_load_mysql.py`,
-- or all at once with:  python src/09_load_mysql.py --run-queries
-- Each query is separated by a line starting with "-- Q".
-- =====================================================================

USE monsoon_last_mile;

-- Q1 (JOIN + GROUP BY) How complete is each station's hourly PM2.5 record?
SELECT s.station_name,
       s.operator,
       COUNT(*)                                               AS station_hours,
       SUM(CASE WHEN h.pm25 IS NULL THEN 1 ELSE 0 END)        AS hours_missing,
       ROUND(100.0 * SUM(CASE WHEN h.pm25 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_missing,
       SUM(h.pm25_filled)                                     AS hours_interpolated
FROM readings_hourly h
JOIN stations s ON s.station_id = h.station_id
GROUP BY s.station_name, s.operator
ORDER BY pct_missing DESC;

-- Q2 (GROUP BY) Which cleaning flags removed readings, per station and pollutant?
SELECT r.station_id, r.parameter, r.flag, COUNT(*) AS n_readings
FROM readings r
WHERE r.flag <> 'ok'
GROUP BY r.station_id, r.parameter, r.flag
ORDER BY n_readings DESC;

-- Q3 (GROUP BY) Hour-by-weekday average PM2.5 across all stations (the heatmap, in SQL)
SELECT h.weekday, h.hour_ist, ROUND(AVG(h.pm25), 1) AS avg_pm25, COUNT(h.pm25) AS n_hours
FROM readings_hourly h
GROUP BY h.weekday, h.hour_ist
ORDER BY avg_pm25 DESC
LIMIT 10;

-- Q4 (JOIN x3 + GROUP BY) Evening-commute PM2.5 in rainy vs dry hours, by season, working days only
SELECT c.season,
       w.is_rainy_hour,
       COUNT(h.pm25)              AS station_hours,
       ROUND(AVG(h.pm25), 1)      AS avg_pm25,
       ROUND(AVG(h.no2), 1)       AS avg_no2
FROM readings_hourly h
JOIN weather_hourly w ON w.slot_ist = h.slot_ist
JOIN calendar c       ON c.cal_date = h.cal_date
WHERE h.hour_ist BETWEEN 17 AND 20
  AND c.is_working_day = 1
GROUP BY c.season, w.is_rainy_hour
ORDER BY c.season, w.is_rainy_hour;

-- Q5 (JOIN + GROUP BY) When does rain hit the evening commute? Share of rainy hours per month.
SELECT c.month,
       ROUND(100.0 * SUM(CASE WHEN w.hour_ist BETWEEN 17 AND 20 THEN w.is_rainy_hour ELSE 0 END)
             / SUM(CASE WHEN w.hour_ist BETWEEN 17 AND 20 THEN 1 ELSE 0 END), 1) AS pct_evening_hours_rainy,
       ROUND(100.0 * SUM(CASE WHEN w.hour_ist BETWEEN 8 AND 10 THEN w.is_rainy_hour ELSE 0 END)
             / SUM(CASE WHEN w.hour_ist BETWEEN 8 AND 10 THEN 1 ELSE 0 END), 1)  AS pct_morning_hours_rainy,
       ROUND(SUM(w.rain_mm), 0) AS rain_mm_month
FROM weather_hourly w
JOIN calendar c ON c.cal_date = w.cal_date
GROUP BY c.month
ORDER BY pct_evening_hours_rainy DESC;

-- Q6 (JOIN x3 + GROUP BY) Per station area: stops with no mapped footpath that are also near a flood point
SELECT s.station_name,
       COUNT(*)                                                         AS stops,
       SUM(CASE WHEN p.sidewalk_m = 0 THEN 1 ELSE 0 END)                AS stops_no_mapped_footpath,
       SUM(CASE WHEN p.waterlog_within_500m > 0 THEN 1 ELSE 0 END)      AS stops_near_flood_point,
       SUM(CASE WHEN p.sidewalk_m = 0 AND p.waterlog_within_500m > 0 THEN 1 ELSE 0 END) AS both_problems,
       SUM(b.trips_wed)                                                 AS bus_trips_wed
FROM bus_stops b
JOIN pedestrian_features p ON p.stop_id = b.stop_id
JOIN stations s            ON s.station_id = b.nearest_station_id
GROUP BY s.station_name
ORDER BY both_problems DESC;

-- Q7 (JOIN x3) The 10 busiest stops with no mapped footpath, and their nearest BBMP flood point
SELECT b.stop_name,
       s.station_name                AS area,
       b.trips_wed,
       p.crossings_n,
       p.nearest_waterlog_m,
       wl.name                       AS nearest_flood_point,
       wl.severity
FROM bus_stops b
JOIN pedestrian_features p    ON p.stop_id = b.stop_id
JOIN waterlogging_locations wl ON wl.wl_id = p.nearest_waterlog_id
JOIN stations s               ON s.station_id = b.nearest_station_id
WHERE p.sidewalk_m = 0
ORDER BY b.trips_wed DESC
LIMIT 10;

-- Q8 (JOIN + GROUP BY + subquery) Waterlogging headlines vs monthly rain
-- (months where the GDELT request failed have low counts - check outputs/tables/news_coverage.csv)
SELECT n.month, n.waterlog_headlines, r.rain_mm
FROM (SELECT c.month, SUM(a.tag_waterlogging) AS waterlog_headlines
      FROM news_articles a JOIN calendar c ON c.cal_date = a.cal_date
      GROUP BY c.month) n
JOIN (SELECT c.month, ROUND(SUM(w.rain_mm), 0) AS rain_mm
      FROM weather_hourly w JOIN calendar c ON c.cal_date = w.cal_date
      GROUP BY c.month) r ON r.month = n.month
ORDER BY n.waterlog_headlines DESC;
