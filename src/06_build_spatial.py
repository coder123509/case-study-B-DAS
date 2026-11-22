"""
Step 6 - Bus stops, mapped pedestrian network and waterlogging proximity.

Inputs : data/raw/gtfs/bmtc_gtfs_*.zip                (stops, trips, stop_times)
         data/raw/osm/osm_overpass_pedestrian_*.json   (OSM ways + crossing nodes)
         data/processed/waterlogging_locations.csv
         data/processed/stations.csv
Outputs: data/processed/bus_stops.csv            one row per selected BMTC stop
         data/processed/pedestrian_features.csv  one row per stop: what is MAPPED within 300 m
         data/interim/osm_ways_flat.csv          flattened OSM ways (for the data inventory)

Selection rule: a stop is "selected" if it lies within 1.5 km of one of our
5 air-quality stations, so every stop has a nearby pollution reading.

IMPORTANT: OSM shows what volunteers have MAPPED. A missing footpath in OSM
does not prove the footpath is missing on the ground.
"""
import glob
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from utils import CleaningLog, haversine_m

log = CleaningLog("06_spatial")
stations = pd.read_csv(C.PROCESSED / "stations.csv")

# ------------------------------------------------------------------ GTFS
gtfs_zip = sorted(glob.glob(str(C.RAW / "gtfs" / "bmtc_gtfs_*.zip")))[-1]
z = zipfile.ZipFile(gtfs_zip)
stops = pd.read_csv(z.open("stops.txt"), dtype={"stop_id": str, "stop_code": str})
n_all = len(stops)
stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
bad = stops["stop_lat"].isna() | stops["stop_lon"].isna()
log.add("bus_stops", "GTFS stops with missing / unparsable coordinates", int(bad.sum()),
        "dropped" if bad.sum() else "none found", "a stop without a location cannot be mapped")
stops = stops[~bad]

# distance from every stop to every station -> nearest station
d = np.column_stack([haversine_m(stops["stop_lat"].values, stops["stop_lon"].values, r.lat, r.lon)
                     for r in stations.itertuples()])
stops["nearest_station_id"] = stations["location_id"].values[d.argmin(axis=1)]
stops["dist_to_station_m"] = d.min(axis=1).round(0)
sel = stops[stops["dist_to_station_m"] <= C.STOP_RADIUS_FROM_STATION_M].copy()
log.add("bus_stops", f"BMTC stops further than {C.STOP_RADIUS_FROM_STATION_M} m from any of our 5 AQ stations",
        n_all - len(sel), "not selected for the study",
        "the case is about selected stop areas that have a nearby pollution monitor")

# same-name stops a few metres apart are the two sides of the road - we keep both
# (a commuter walks to one specific side), but we report the count.
pairs = sel.duplicated("stop_name", keep=False)
log.add("bus_stops", "stops sharing a name (usually the two directions of one road)",
        int(pairs.sum()), "kept as separate stops", "each side of the road has its own walk-in route")

# service level: trips stopping on a normal Wednesday (service_id like 'days:1111100')
trips = pd.read_csv(z.open("trips.txt"), usecols=["trip_id", "service_id", "route_id"])
trips = trips[trips["service_id"].str.slice(5 + 2, 5 + 3) == "1"]        # 3rd flag = Wednesday
st = pd.read_csv(z.open("stop_times.txt"), usecols=["trip_id", "stop_id"], dtype={"stop_id": str})
st = st[st["stop_id"].isin(sel["stop_id"])].merge(trips, on="trip_id")
service = st.groupby("stop_id").agg(trips_wed=("trip_id", "nunique"),
                                    routes=("route_id", "nunique")).reset_index()
sel = sel.merge(service, on="stop_id", how="left")
sel[["trips_wed", "routes"]] = sel[["trips_wed", "routes"]].fillna(0).astype(int)
no_service = sel["trips_wed"] == 0
log.add("bus_stops", "selected stops with no Wednesday trip in the GTFS timetable",
        int(no_service.sum()), "kept but flagged (trips_wed = 0)",
        "the feed only includes routes with live tracking, so 0 may mean 'not tracked'")
log.add("bus_stops", "GTFS timetable is a 2026-27 snapshot, study year is 2025-26",
        len(sel), "used stop locations + service counts as an approximation",
        "BMTC publishes no historical feed; stop locations change slowly")

sel = sel.rename(columns={"stop_lat": "lat", "stop_lon": "lon"})
sel = sel[["stop_id", "stop_code", "stop_name", "lat", "lon", "nearest_station_id",
           "dist_to_station_m", "trips_wed", "routes"]]

# ------------------------------------------------------------------ OSM flatten
osm = json.loads((C.RAW / "osm" / "osm_overpass_pedestrian_5stations_1800m.json").read_text(encoding="utf-8"))
print("OSM snapshot:", osm["osm3s"]["timestamp_osm_base"], "| elements:", len(osm["elements"]))
FOOT = {"footway", "pedestrian", "path", "steps", "living_street"}
MAJOR = {"trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
         "tertiary", "tertiary_link"}
SIDEWALK_YES = {"both", "left", "right", "yes"}

seg_rows, way_rows, crossings = [], [], []
seen = set()
for el in osm["elements"]:
    if (el["type"], el["id"]) in seen:          # the 5 circles overlap -> same way twice
        continue
    seen.add((el["type"], el["id"]))
    tags = el.get("tags", {})
    if el["type"] == "node":
        crossings.append((el["lat"], el["lon"]))
        continue
    hw = tags.get("highway")
    geom = el.get("geometry", [])
    if len(geom) < 2:
        continue
    if hw in FOOT:
        kind = "sidewalk" if tags.get("footway") == "sidewalk" else \
               "crossing_way" if tags.get("footway") == "crossing" else "other_footpath"
    elif hw in MAJOR:
        kind = "major_road"
    else:
        kind = "minor_road"
    sw = tags.get("sidewalk", tags.get("sidewalk:both", ""))
    has_sidewalk_tag = sw in SIDEWALK_YES or tags.get("sidewalk:left") in ("yes",) or \
        tags.get("sidewalk:right") in ("yes",)
    no_sidewalk = sw in ("no", "none")
    lat = np.array([g["lat"] for g in geom])
    lon = np.array([g["lon"] for g in geom])
    seg_len = haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    way_rows.append({"osm_way_id": el["id"], "highway": hw, "kind": kind, "name": tags.get("name"),
                     "sidewalk_tag": sw or None, "surface": tags.get("surface"),
                     "n_nodes": len(geom), "length_m": round(float(seg_len.sum()), 1)})
    seg_rows.append(pd.DataFrame({"mid_lat": (lat[:-1] + lat[1:]) / 2,
                                  "mid_lon": (lon[:-1] + lon[1:]) / 2,
                                  "len_m": seg_len, "kind": kind,
                                  "sidewalk_tagged": has_sidewalk_tag, "no_sidewalk": no_sidewalk}))
n_dups = len(osm["elements"]) - len(seen)
log.add("osm_ways", "same OSM element returned more than once (the 5 search circles overlap)",
        n_dups, "kept once", "otherwise roads between two stations would be counted twice")
ways = pd.DataFrame(way_rows)
ways.to_csv(C.INTERIM / "osm_ways_flat.csv", index=False)
segs = pd.concat(seg_rows, ignore_index=True)
cross = np.array(crossings)
print(ways["kind"].value_counts().to_string())

# ------------------------------------------------------------------ per-stop metrics (300 m)
feat = []
for s in sel.itertuples():
    dist = haversine_m(s.lat, s.lon, segs["mid_lat"].values, segs["mid_lon"].values)
    inside = segs[dist <= C.WALK_BUFFER_M]
    L = inside.groupby("kind")["len_m"].sum()
    major = L.get("major_road", 0.0)
    sidewalk = L.get("sidewalk", 0.0) + \
        inside.loc[inside["sidewalk_tagged"] & inside["kind"].isin(["major_road", "minor_road"]), "len_m"].sum()
    n_cross = int((haversine_m(s.lat, s.lon, cross[:, 0], cross[:, 1]) <= C.WALK_BUFFER_M).sum())
    feat.append({"stop_id": s.stop_id,
                 "major_road_m": round(major), "minor_road_m": round(L.get("minor_road", 0.0)),
                 "sidewalk_m": round(sidewalk),
                 "other_footpath_m": round(L.get("other_footpath", 0.0)),
                 "no_sidewalk_tagged_m": round(inside.loc[inside["no_sidewalk"], "len_m"].sum()),
                 "crossings_n": n_cross})
feat = pd.DataFrame(feat)
# mapped footpath per metre of main road. 2.0 would mean both sides fully mapped.
feat["sidewalk_per_major_road_m"] = np.where(
    feat["major_road_m"] > 0, (feat["sidewalk_m"] / feat["major_road_m"]).round(2), np.nan)
feat["crossings_per_km_major"] = np.where(
    feat["major_road_m"] > 0, (1000 * feat["crossings_n"] / feat["major_road_m"]).round(1), np.nan)
no_major = feat["major_road_m"] == 0
log.add("pedestrian_features", "stops with no main road within 300 m", int(no_major.sum()),
        "sidewalk ratio left empty (NaN)", "a ratio with a zero denominator is undefined, not 0")

# ------------------------------------------------------------------ waterlogging proximity
wl = pd.read_csv(C.PROCESSED / "waterlogging_locations.csv")
dwl = np.column_stack([haversine_m(sel["lat"].values, sel["lon"].values, r.lat, r.lon)
                       for r in wl.itertuples()])
feat["nearest_waterlog_m"] = dwl.min(axis=1).round(0)
feat["nearest_waterlog_id"] = wl["wl_id"].values[dwl.argmin(axis=1)]
feat["waterlog_within_500m"] = (dwl <= C.WATERLOG_RADIUS_M).sum(axis=1)
feat["severe_waterlog_within_500m"] = ((dwl <= C.WATERLOG_RADIUS_M) &
                                       (wl["severity"].values == "severe")).sum(axis=1)

sel.to_csv(C.PROCESSED / "bus_stops.csv", index=False)
feat.to_csv(C.PROCESSED / "pedestrian_features.csv", index=False)
summary = sel.merge(feat, on="stop_id").groupby("nearest_station_id").agg(
    stops=("stop_id", "count"), median_trips=("trips_wed", "median"),
    median_sidewalk_ratio=("sidewalk_per_major_road_m", "median"),
    stops_near_waterlog=("waterlog_within_500m", lambda s: int((s > 0).sum())))
summary.index = summary.index.map(C.STATIONS)
print(summary.to_string())
print(f"saved {len(sel)} bus stops and their pedestrian features")
log.save()
