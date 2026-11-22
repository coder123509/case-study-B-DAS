"""
Step 7 - Turn news headlines (unstructured text) into something we can count.

Input : data/raw/news/gdelt_bengaluru_headlines_202503_202602.json
        (GDELT DOC 2.0 API: one block per theme x month, each with a list of articles)
Output: data/processed/news_articles.csv   one row per unique article
        data/processed/news_monthly.csv    counts per month and tag

What we do with the text:
 1. flatten the nested JSON (theme -> month -> articles[])
 2. parse GDELT's compact UTC timestamp "20250614T013000Z" and convert to IST
 3. de-duplicate (the same story is found by both themes / syndicated copies)
 4. lower-case + keyword tags (waterlogging, footpath, ...) and locality mentions
GDELT gives headlines + URLs, not full article text, and no personal data.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from utils import CleaningLog

log = CleaningLog("07_news")
raw = json.loads((C.RAW / "news" / "gdelt_bengaluru_headlines_202503_202602.json").read_text(encoding="utf-8"))

failed = [f"{b['theme']} {b['startdatetime'][:8]}" for b in raw if b["articles"] is None]
log.add("news_articles", "API windows that returned no answer after retries", len(failed),
        "listed in outputs/tables/news_failed_windows.txt; counts for those windows are missing",
        "GDELT rate-limits requests; we report the gap instead of guessing")
(C.TABLES / "news_failed_windows.txt").write_text("\n".join(failed) or "none", encoding="utf-8")

# coverage: which theme-month windows actually answered (a failed month must show as
# "no data", never as zero headlines)
cov = pd.DataFrame([{"theme": b["theme"], "month": pd.Timestamp(b["startdatetime"][:8]).strftime("%Y-%m"),
                     "status": "failed" if b["articles"] is None else
                               ("capped_250" if len(b["articles"]) >= 250 else "ok"),
                     "n_articles": None if b["articles"] is None else len(b["articles"])} for b in raw])
cov = (cov.groupby(["theme", "month"])
       .agg(status=("status", lambda s: "failed" if (s == "failed").any() else
                    ("capped_250" if (s == "capped_250").any() else "ok")),
            n_articles=("n_articles", "sum")).reset_index())
cov.to_csv(C.TABLES / "news_coverage.csv", index=False)
print(cov.pivot(index="month", columns="theme", values="status").to_string())

rows = []
for block in raw:
    for a in block["articles"] or []:
        rows.append({"theme_query": block["theme"], **a})
news = pd.DataFrame(rows)
capped = [f"{b['theme']} {b['startdatetime'][:8]}" for b in raw if b["articles"] and len(b["articles"]) >= 250]
log.add("news_articles", "windows that hit GDELT's 250-article cap", len(capped),
        "those windows were split in half when downloading" if not capped else
        "kept; counts for " + ", ".join(capped) + " are a lower bound",
        "the API never returns more than 250 rows per call")
n_raw = len(news)

# --- type casting: compact UTC string -> IST datetime
news["seen_utc"] = pd.to_datetime(news["seendate"], format="%Y%m%dT%H%M%SZ", utc=True)
news["seen_ist"] = news["seen_utc"].dt.tz_convert(C.TZ)
news["date_ist"] = news["seen_ist"].dt.date
log.add("news_articles", "GDELT time is a compact UTC string like '20250614T013000Z'", n_raw,
        "parsed with an explicit format and converted to IST", "a story seen at 22:00 UTC is already the next day in Bengaluru")

# --- de-duplicate: same URL from two themes, then same headline on mirror sites
news = news.sort_values("seen_utc")
themes = news.groupby("url")["theme_query"].agg(lambda s: "+".join(sorted(set(s))))
d1 = news.duplicated("url")
news = news[~d1].copy()
news["theme_query"] = news["url"].map(themes)
news["title_clean"] = news["title"].str.lower().str.replace(r"[^a-z0-9 ]+", " ", regex=True) \
    .str.replace(r"\s+", " ", regex=True).str.strip()
d2 = news.duplicated("title_clean")
log.add("news_articles", "duplicate articles (same URL found by both queries / same headline "
        "re-published on another site)", int(d1.sum() + d2.sum()), "kept the first copy",
        "otherwise one story would be counted several times")
news = news[~d2].copy()

# --- keep only the study window (the API window edges are inclusive)
in_win = news["seen_ist"].between(pd.Timestamp(C.STUDY_START_IST, tz=C.TZ),
                                  pd.Timestamp(C.STUDY_END_IST, tz=C.TZ))
log.add("news_articles", "articles seen outside 1 Mar 2025 - 28 Feb 2026 IST", int((~in_win).sum()),
        "dropped", "keep the same 12 months as the sensor data")
news = news[in_win].copy()

non_en = news["language"].ne("English")
log.add("news_articles", "headlines not in English (Kannada, Hindi ...)", int(non_en.sum()),
        "kept but not keyword-tagged", "our keyword list is English; translating would add errors")

# --- keyword tags (simple, transparent dictionary)
TAGS = {
    "waterlogging": r"waterlog|water log|flood|inundat|rain water|rainwater|deluge|knee deep|submerge",
    "rain": r"\brain|downpour|cloudburst|monsoon|shower|thunder",
    "footpath": r"footpath|pavement|sidewalk|pedestrian|skywalk|foot over|zebra|crossing",
    "bus": r"\bbus\b|bmtc|bus stop|bus shelter|commut",
    "traffic": r"traffic|jam|gridlock|congest",
    "pollution": r"pollution|\baqi\b|air quality|pm2 5|smog",
    "drains": r"drain|swd|storm water|stormwater|desilt|culvert",
}
for tag, pattern in TAGS.items():
    news[f"tag_{tag}"] = (~non_en & news["title_clean"].str.contains(pattern, regex=True)).astype(int)

# --- locality mentions (our 5 station areas + well-known flood / commute hotspots)
PLACES = {
    "Silk Board": r"silk board|silkboard", "Hebbal": r"hebbal", "Jayanagar": r"jayanagar",
    "Bapuji Nagar": r"bapuji", "Hombegowda Nagar": r"hombegowda", "BTM Layout": r"\bbtm\b",
    "Koramangala": r"koramangala", "HSR Layout": r"\bhsr\b", "Mahadevapura": r"mahadevapura",
    "Whitefield": r"whitefield", "Bellandur": r"bellandur", "Yelahanka": r"yelahanka",
    "Majestic": r"majestic|kempegowda bus", "Hosur Road": r"hosur road", "Outer Ring Road": r"outer ring road|\borr\b",
    "Sai Layout": r"sai layout", "Electronic City": r"electronic city|electronics city",
    "KR Puram": r"k r puram|kr puram", "Mysuru Road": r"mysore road|mysuru road",
}
news["places"] = news["title_clean"].apply(
    lambda t: ";".join(p for p, rx in PLACES.items() if re.search(rx, t)))

news.insert(0, "article_id", range(1, len(news) + 1))
keep = ["article_id", "seen_ist", "date_ist", "domain", "language", "sourcecountry", "title", "url",
        "theme_query"] + [f"tag_{t}" for t in TAGS] + ["places"]
news[keep].to_csv(C.PROCESSED / "news_articles.csv", index=False)

news["month"] = news["seen_ist"].dt.strftime("%Y-%m")
monthly = news.groupby("month").agg(
    articles=("article_id", "count"),
    waterlogging=("tag_waterlogging", "sum"), rain=("tag_rain", "sum"),
    footpath=("tag_footpath", "sum"), bus=("tag_bus", "sum"), traffic=("tag_traffic", "sum"),
    drains=("tag_drains", "sum"), pollution=("tag_pollution", "sum")).reset_index()
wl_status = cov[cov["theme"] == "waterlogging"].set_index("month")["status"]
monthly["waterlog_query_status"] = monthly["month"].map(wl_status)
monthly.to_csv(C.PROCESSED / "news_monthly.csv", index=False)
print(monthly.to_string(index=False))
places = news["places"].str.split(";").explode()
print("most mentioned places:\n", places[places != ""].value_counts().head(12).to_string())
print(f"saved {len(news)} unique articles")
log.save()
