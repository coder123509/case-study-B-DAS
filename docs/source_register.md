# Source register

All data is public. Nothing was scraped behind a login and no personal data was collected.
Access date for every source: **21 November 2026** (IST). Checksums of the exact files we analysed are in
`data/raw_checksums_sha256.txt`.

| # | Dataset | Publisher / origin | URL used | Method | Format | Coverage we used | Terms of use | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 15-min air quality, 5 Bengaluru CAAQMS stations (OpenAQ ids 6973, 6974, 6975, 6983, 6984) | Measured by **KSPCB**, published by **CPCB** (airquality.cpcb.gov.in), redistributed by **OpenAQ** | `https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=<id>/year=<yyyy>/month=<mm>/` | Public S3 bucket listing + download of daily files, joined per station (`src/01_download.py openaq`) | CSV.gz (long format) | 28 Feb 2025 - 1 Mar 2026, 1,271,160 rows | Open data with attribution (OpenAQ terms; each location's licence is listed on explore.openaq.org/locations/&lt;id&gt;); original data from Govt. of India (CPCB/KSPCB) | Station ids found by reading the station name inside the archive files. The proposal's first choice, OpenCity's copy of the same CPCB 15-min files, sits behind a Cloudflare bot check that blocks downloads, so we used OpenAQ's copy of the same CPCB feed |
| 2 | Hourly weather (rain, precipitation, temperature, RH, cloud, wind, WMO code) | **Open-Meteo** Historical Weather API (ERA5 / ERA5-Land reanalysis) | `https://archive-api.open-meteo.com/v1/archive?latitude=12.9716&longitude=77.5946&start_date=2025-02-28&end_date=2026-02-28&hourly=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m&timezone=GMT` | REST API, JSON, no key (`src/01_download.py weather`) | JSON | 8,784 hours (UTC), one grid point at the city centre | CC BY 4.0, free for non-commercial use | We asked for UTC on purpose and converted to IST ourselves |
| 3 | BMTC bus stops, trips, timetables (GTFS) | Unofficial feed built from the Namma BMTC app by **Vonter** (github.com/Vonter/bmtc-gtfs), listed in the Mobility Database (mdb-2595) | `https://raw.githubusercontent.com/Vonter/bmtc-gtfs/a4702664d65bfbb37290a5f75effaa24ead1d9dd/gtfs/bmtc.zip` | HTTPS download pinned to commit a4702664 (`src/01_download.py gtfs`) | ZIP of CSV text files | 10,128 stops (we use 351 within 1.5 km of a station) | Repository licence (see repo); data originates from BMTC's public app | **Not an official BMTC release.** Only routes with live tracking are included; timetable is a 2026-27 snapshot |
| 4 | Mapped pedestrian network (footways, sidewalks, crossings, roads) | **OpenStreetMap** contributors via the **Overpass API** | `https://overpass-api.de/api/interpreter` (query saved by the script in `data/raw/osm/overpass_query.txt`) | POST query, 1.8 km around each station (`src/01_download.py osm`) | JSON | 12,980 elements, OSM snapshot 2026-11-21 15:19 UTC | ODbL 1.0 - attribution "(c) OpenStreetMap contributors" | Shows what is **mapped**, not what exists on the ground |
| 5 | Flood-vulnerable locations with coordinates | **BBMP Storm Water Drain department**, "List of vulnerable points identified for the year 2020-21" (hosted by Citizen Matters) | `https://citizenmatters.in/wp-content/uploads/2020/06/SWD-Vul-lat-long-details-18.5.2020-1.pdf` | HTTPS download, parsed with `pdftotext -layout` (`src/05_parse_waterlogging.py`) | PDF table | 199 rows -> 191 valid points | Government document republished by a news site | Oldest source in the project (2020-21). OpenCity's newer KML ("Flooding locations in Bengaluru Urban") is behind the same bot check as #1 |
| 6 | Karnataka general holidays 2025 | **Govt. of Karnataka, DPAR** notification No. DPAR 16 HHL 2024 (copy hosted on cag.gov.in) | `https://cag.gov.in/uploads/media/Karnataka-State-Holidays-2025-067764409e26023-56493682.pdf` | Download, then **typed by hand** into `data/manual/karnataka_holidays_2025_26.csv` | Scanned PDF | Mar - Dec 2025 | Government notification (public) | OCR errors in the scan (e.g. "01. 0.2025") are why we typed it |
| 7 | Holidays Jan - Feb 2026 | Central Govt offices in Karnataka 2026 list (cag.gov.in) + Karnataka DPAR 16 HHL 2025 as reported by the press (e.g. goodreturns.in, sakshipost.com, Nov 2025) | `https://cag.gov.in/uploads/media/Holiday-List-2026-069521fe6f358d0-89936988.pdf` | Download + hand typing | PDF | 3 dates in Jan - Feb 2026 | Public | State list says Sankranti = 15 Jan 2026; the Central list says 14 Jan. We use the State date |
| 8 | News headlines on waterlogging / footpaths in Bengaluru | **GDELT Project** DOC 2.0 API | `https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=artlist&format=json&maxrecords=250` (full request URL stored per block in the JSON file) | REST API, monthly windows, two keyword themes (`src/01_download.py news`) | JSON (headline text + URL + domain + date) | Mar 2025 - Feb 2026 | GDELT: free and open for any use, citation of the GDELT Project required | Gives headlines, not full article text. Max 250 per call; some calls rate-limited - see `outputs/tables/news_failed_windows.txt` |

## How the data actually reached us
Our cloud notebook could not reach most sites directly, so on 21 Nov 2026 the files were fetched through a
normal web browser on a team laptop using exactly the URLs above, and checked with SHA-256 checksums.
`src/01_download.py` performs the same requests with Python `requests` so anyone can repeat them.
GDELT and Overpass return the *current* state of their databases, so a re-download later may differ slightly.

## Sources we tried and dropped
| Source | Why dropped |
|---|---|
| OpenCity "Bengaluru Hourly Air Quality Reports" (15-min CSVs) | Cloudflare "verify you are human" page; we do not bypass bot checks |
| OpenCity flood-point KML | same |
| OpenAQ API v3 | needs an account + API key; the public S3 archive has the same records without one |
| Reddit r/bangalore | not needed once GDELT news gave the text source; avoids handling usernames |
