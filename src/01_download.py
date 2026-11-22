"""
Step 1 - Download every raw dataset into data/raw/.

Run:   python src/01_download.py              (everything)
       python src/01_download.py openaq osm   (only some sources)

Nothing here changes the data. Files are saved exactly as the source sends
them (only the OpenAQ daily files are concatenated per station, see below).
After downloading, compare your files against data/raw_checksums_sha256.txt.
Note: GDELT and Overpass return *today's* view of the data, so their checksums
will differ if you re-download later. That is expected; keep the copy you analysed.

Sources (full details in docs/source_register.md):
  openaq   OpenAQ public archive on AWS S3 (CPCB / KSPCB station data, 15-min)
  weather  Open-Meteo Historical Weather API (JSON, no key)
  osm      OpenStreetMap via the Overpass API (JSON)
  gtfs     Unofficial BMTC GTFS feed (github.com/Vonter/bmtc-gtfs)
  docs     BBMP storm-water-drain vulnerable points PDF + Karnataka holiday PDFs
  news     GDELT DOC 2.0 API - news headlines (JSON)
"""
import gzip
import io
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

HEADERS = {"User-Agent": "monsoon-last-mile student project (Data & Storytelling, Module 1)"}
S3 = "https://openaq-data-archive.s3.amazonaws.com"


# --------------------------------------------------------------------- OpenAQ
def s3_list(prefix):
    """List every object key under a prefix (S3 returns max 1000 per page)."""
    keys, token = [], None
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        r = requests.get(S3 + "/", params=params, headers=HEADERS, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        keys += [c.find("s3:Key", ns).text for c in root.findall("s3:Contents", ns)]
        nxt = root.find("s3:NextContinuationToken", ns)
        if nxt is None:
            return keys
        token = nxt.text


def download_openaq():
    out_dir = C.RAW / "openaq"
    out_dir.mkdir(parents=True, exist_ok=True)
    d0 = C.DOWNLOAD_START.replace("-", "")
    d1 = C.DOWNLOAD_END.replace("-", "")
    for loc_id, name in C.STATIONS.items():
        keys = []
        for year in (2025, 2026):
            keys += s3_list(f"records/csv.gz/locationid={loc_id}/year={year}/")
        # file names end in -YYYYMMDD.csv.gz ; keep only our window
        keys = sorted(k for k in keys if d0 <= k[-15:-7] <= d1)
        print(f"[openaq] {loc_id} {name}: {len(keys)} daily files")

        # Concatenate the daily files into one CSV per station.
        # Same logic we used in the browser: normalise line endings, drop empty
        # lines, keep the header only from the first file.
        lines_out = []
        for i, key in enumerate(keys):
            r = requests.get(f"{S3}/{key}", headers=HEADERS, timeout=60)
            r.raise_for_status()
            text = gzip.decompress(r.content).decode("utf-8").replace("\r\n", "\n")
            lines = [l for l in text.split("\n") if l]
            lines_out += lines if i == 0 else lines[1:]
        fname = out_dir / f"openaq_location_{loc_id}_{d0}_{d1}.csv.gz"
        with gzip.open(fname, "wt", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines_out) + "\n")
        print(f"          -> {fname.name}  ({len(lines_out) - 1:,} data rows)")


# --------------------------------------------------------------------- weather
def download_weather():
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": C.WEATHER_LAT, "longitude": C.WEATHER_LON,
        "start_date": C.DOWNLOAD_START, "end_date": "2026-02-28",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,rain,"
                  "weather_code,cloud_cover,wind_speed_10m",
        "timezone": "GMT",          # we deliberately ask for UTC and convert ourselves
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    out = C.RAW / "weather" / "openmeteo_bengaluru_hourly_20250228_20260228.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r.text, encoding="utf-8")
    print(f"[weather] saved {out.name} ({len(r.text):,} chars)")


# --------------------------------------------------------------------- OSM
def overpass_query():
    """Footways, walkable roads and crossings within 1.8 km of each station."""
    q = "[out:json][timeout:180];\n(\n"
    for loc_id in C.STATIONS:
        lat, lon = STATION_COORDS[loc_id]
        p = f"{lat},{lon}"
        r = C.OSM_QUERY_RADIUS_M
        q += (f'  way(around:{r},{p})[highway~"^(footway|pedestrian|path|steps|living_street)$"];\n'
              f'  way(around:{r},{p})[highway~"^(trunk|trunk_link|primary|primary_link|secondary|'
              f'secondary_link|tertiary|tertiary_link|residential|unclassified)$"];\n'
              f'  node(around:{r},{p})[highway=crossing];\n')
    return q + ");\nout tags geom;"


# coordinates exactly as written in the OpenAQ files (used for the OSM query)
STATION_COORDS = {
    6973: ("12.920984", "77.584908"),
    6974: ("12.951913", "77.539784"),
    6975: ("12.917348", "77.622813"),
    6983: ("12.938539", "77.5901"),
    6984: ("13.029152", "77.585901"),
}


def download_osm():
    q = overpass_query()
    for endpoint in ("https://overpass-api.de/api/interpreter",
                     "https://overpass.kumi.systems/api/interpreter"):
        r = requests.post(endpoint, data={"data": q}, headers=HEADERS, timeout=300)
        if r.status_code == 200:
            out = C.RAW / "osm" / "osm_overpass_pedestrian_5stations_1800m.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(r.text, encoding="utf-8")
            (C.RAW / "osm" / "overpass_query.txt").write_text(q, encoding="utf-8")
            print(f"[osm] saved {out.name} from {endpoint}")
            return
        print(f"[osm] {endpoint} answered {r.status_code}, trying next mirror in 10 s")
        time.sleep(10)
    raise RuntimeError("All Overpass mirrors busy - try again later")


# --------------------------------------------------------------------- GTFS
GTFS_COMMIT = "a4702664d65bfbb37290a5f75effaa24ead1d9dd"   # pinned for reproducibility


def download_gtfs():
    url = f"https://raw.githubusercontent.com/Vonter/bmtc-gtfs/{GTFS_COMMIT}/gtfs/bmtc.zip"
    out = C.RAW / "gtfs" / f"bmtc_gtfs_{GTFS_COMMIT[:8]}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=HEADERS, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"[gtfs] saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")


# --------------------------------------------------------------------- PDFs
DOCS_TO_FETCH = {
    "waterlogging/bbmp_swd_vulnerable_locations_2020-21.pdf":
        "https://citizenmatters.in/wp-content/uploads/2020/06/SWD-Vul-lat-long-details-18.5.2020-1.pdf",
    "calendar/karnataka_dpar_general_holidays_2025.pdf":
        "https://cag.gov.in/uploads/media/Karnataka-State-Holidays-2025-067764409e26023-56493682.pdf",
    "calendar/cg_offices_karnataka_holidays_2026.pdf":
        "https://cag.gov.in/uploads/media/Holiday-List-2026-069521fe6f358d0-89936988.pdf",
}


def download_docs():
    for rel, url in DOCS_TO_FETCH.items():
        out = C.RAW / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, headers=HEADERS, timeout=120)
        r.raise_for_status()
        out.write_bytes(r.content)
        print(f"[docs] saved {rel} ({len(r.content):,} bytes)")


# --------------------------------------------------------------------- news
NEWS_THEMES = {
    "waterlogging": '(waterlogging OR waterlogged OR flooding OR "heavy rain") '
                    '(Bengaluru OR Bangalore) sourcecountry:IN',
    "pedestrian": '(footpath OR pedestrian OR "bus stop" OR footpaths) '
                  '(Bengaluru OR Bangalore) sourcecountry:IN',
}
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"


def gdelt_call(query, start, end):
    params = {"query": query, "mode": "artlist", "format": "json", "maxrecords": 250,
              "sort": "datedesc", "startdatetime": start, "enddatetime": end}
    # GDELT asks for at most 1 request every 5 s and answers HTTP 429 when you go faster.
    # After a burst it keeps refusing for several minutes, so we back off hard.
    for attempt in range(5):
        r = requests.get(GDELT, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 200 and r.text.strip().startswith("{"):
            return r.url, r.json().get("articles", [])
        print(f"   GDELT answered {r.status_code}, waiting {60 * (attempt + 1)} s")
        time.sleep(60 * (attempt + 1))
    return r.url, None


def month_windows():
    out = []
    y, m = 2025, 3
    for _ in range(12):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((f"{y}{m:02d}01000000", f"{ny}{nm:02d}01000000"))
        y, m = ny, nm
    return out


def download_news():
    results = []
    for theme, q in NEWS_THEMES.items():
        for start, end in month_windows():
            url, arts = gdelt_call(q, start, end)
            # GDELT returns at most 250 articles. If a month hits the cap we
            # split it into two halves so we do not silently lose headlines.
            if arts is not None and len(arts) >= 250:
                mid = start[:6] + "16000000"
                for s, e in ((start, mid), (mid, end)):
                    u2, a2 = gdelt_call(q, s, e)
                    results.append({"theme": theme, "query": q, "startdatetime": s,
                                    "enddatetime": e, "request_url": u2,
                                    "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                                    "articles": a2})
                    time.sleep(30)
            else:
                results.append({"theme": theme, "query": q, "startdatetime": start,
                                "enddatetime": end, "request_url": url,
                                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                                "articles": arts})
            print(f"[news] {theme} {start[:6]}: {None if arts is None else len(arts)}")
            time.sleep(30)
    out = C.RAW / "news" / "gdelt_bengaluru_headlines_202503_202602.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[news] saved {out.name}")


# --------------------------------------------------------------------- main
STEPS = {"openaq": download_openaq, "weather": download_weather, "osm": download_osm,
         "gtfs": download_gtfs, "docs": download_docs, "news": download_news}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(STEPS)
    for name in wanted:
        STEPS[name]()
