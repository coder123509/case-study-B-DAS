// Builds report/Monsoon_Last_Mile_Report.docx from the project's outputs.
// Run from the project root:  node report/build_report.js
// Text lives in this file so the team can edit wording and rebuild; numbers come from outputs/.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  AlignmentType, HeadingLevel, LevelFormat, WidthType, ShadingType, BorderStyle,
  PageBreak, Footer, PageNumber, TableOfContents,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FIG = (f) => path.join(ROOT, "outputs", "figures", f);
const FONT = "Arial";
const CONTENT_W = 9026;                 // A4 width 11906 - 2 x 1440 margins (DXA)
const ACCENT = "1F4E79";
const GREY = "595959";

// ---------------------------------------------------------------- helpers
// inline **bold** and `code` markup -> runs
function runs(text, opts = {}) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).filter(Boolean).map((t) => {
    if (t.startsWith("**")) return new TextRun({ text: t.slice(2, -2), bold: true, ...opts });
    if (t.startsWith("`")) return new TextRun({ text: t.slice(1, -1), ...opts, font: "Courier New", color: "1F3864" });
    return new TextRun({ text: t, ...opts });
  });
}
const P = (text, o = {}) => new Paragraph({ children: runs(text, o.run || {}), spacing: { after: 120 }, ...o.para });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const B = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t), spacing: { after: 60 } });
const N = (t) => new Paragraph({ numbering: { reference: "numbers", level: 0 }, children: runs(t), spacing: { after: 60 } });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function figure(file, caption, widthIn = 6.2) {
  const { w, h } = pngSize(file);
  const pxW = Math.round(widthIn * 96);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 60, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file),
        transformation: { width: pxW, height: Math.round(pxW * h / w) },
        altText: { title: caption, description: caption, name: path.basename(file) } })],
    }),
    new Paragraph({ spacing: { after: 160 },
      children: runs(caption, { size: 18, italics: true, color: GREY }) }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(rows, widths, { size = 18, header = true } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: header && i === 0, cantSplit: true,
      children: r.map((cell, j) => new TableCell({
        borders, width: { size: widths[j], type: WidthType.DXA },
        margins: { top: 50, bottom: 50, left: 90, right: 90 },
        shading: header && i === 0 ? { fill: "DCE6F1", type: ShadingType.CLEAR, color: "auto" } : undefined,
        children: String(cell).split("\n").map((line) => new Paragraph({
          children: runs(line, { size, bold: header && i === 0 ? true : undefined }) })),
      })),
    })),
  });
}
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [] });

// ---------------------------------------------------------------- data from outputs
const csv = (f) => {
  const txt = fs.readFileSync(path.join(ROOT, f), "utf8").trim().split(/\r?\n/);
  const parse = (line) => {
    const out = []; let cur = "", q = false;
    for (const ch of line) {
      if (ch === '"') q = !q; else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch;
    }
    out.push(cur); return out;
  };
  const head = parse(txt[0]);
  return txt.slice(1).map((l) => Object.fromEntries(parse(l).map((v, i) => [head[i], v])));
};
const cleaning = csv("docs/cleaning_log.csv");
const fmt = (n) => Number(n).toLocaleString("en-US");

// ================================================================== CONTENT
const body = [];

// ---- title block (page 1, no separate cover page to save space)
body.push(
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "The Monsoon Last-Mile Trap", bold: true, size: 40, font: FONT, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Where and when monsoon weather makes the walk to Bengaluru's bus stops most vulnerable", size: 24, color: GREY })] }),
  new Paragraph({ spacing: { after: 240 }, children: runs("Data and Storytelling · Module 1 · Case Study B  |  Team: **[Team name]**  |  Members: [Name 1], [Name 2], [Name 3], [Name 4], [Name 5]  |  Repo: [GitHub link]", { size: 18, color: GREY }) }),
);

// ---- a. Executive summary
body.push(H1("1. Executive summary"));
body.push(
  P("Monsoon rain threatens Bengaluru's bus-stop last mile in the late afternoon and evening, not the morning: between May and October **51% of all rain fell between 14:00 and 20:00**, and in July–October **14–19% of evening-commute hours (17:00–20:00) were wet against 4–6% of morning ones**."),
  P("The walks most exposed are at the busy stops around **Silk Board and Mysore Road (Bapuji Nagar)** – Central Silk Board, Nayandahalli Junction and the Mysore Road bus and metro stops lead the ranking – where OpenStreetMap shows almost no footpath and a BBMP flood-prone point lies **60–180 m** away."),
  P("Because rain itself goes with about **27% lower PM2.5** (same station, month and hour), the city should treat the monsoon last mile as a footpath-and-drain job at these stops, backed by rain alerts from 15:00, and handle dirty air separately as a **dry winter-evening (20:00–22:00)** problem."),
);

// ---- b. Question
body.push(H1("2. Question and why it matters to the city"));
body.push(
  P("**Research question.** Where and when does monsoon weather make the last mile to Bengaluru's BMTC bus stops most vulnerable, particularly where gaps in the mapped pedestrian network, known waterlogging spots and elevated nearby air pollution overlap?"),
  P("**Why it matters.** Every bus trip starts and ends on foot. Footpaths, drains, bus service and air quality are planned by different departments, so the place where all four fail together – a busy stop with no footpath next to a flooding drain – falls between them. The Urban Services Cell needs to know which stops to fix first and at what time of day commuters are most exposed."),
  P("**Decision supported.** (1) Which stop areas get footpath, crossing and drain work before the next monsoon; (2) when rain alerts should go out; (3) whether pollution alerts belong to the same monsoon plan or a different season. The study ranks locations for attention; it does not prove that any intervention will reduce flooding, pollution or risk."),
);
body.push(table([
  ["Sub-question", "Answered with", "Section"],
  ["Which stop areas have poor mapped pedestrian coverage?", "OSM footways, sidewalks, crossings within 300 m of 351 BMTC stops", "6.4"],
  ["Which are near documented waterlogging points?", "BBMP SWD list of 191 flood-vulnerable points (2020-21)", "6.4"],
  ["Which months / hours is rain most relevant?", "Open-Meteo hourly rain, 8,760 hours", "6.2"],
  ["Is pollution high in those periods?", "1.27 M 15-min CPCB/KSPCB readings, rainy vs dry comparison", "6.1, 6.3"],
  ["Which locations should get attention first?", "Transparent 3-part priority score + sensitivity test", "6.4, 7"],
], [3600, 4426, 1000]));

// ---- c. Data inventory and V profile
body.push(H1("3. Data inventory and V profile"));
body.push(P("Seven public sources, five formats. Full URLs, access dates, licences and the sources we tried and dropped are in Appendix A; every field is classified by measurement level in the repo (`docs/data_inventory.md`)."));
body.push(table([
  ["Source (publisher)", "Format / structure", "Rows", "Coverage", "Key field types"],
  ["Air quality: 5 CAAQMS stations (KSPCB/CPCB via OpenAQ archive)", "CSV.gz – structured, long", "1,271,160", "15-min, 28 Feb 2025 – 1 Mar 2026", "value continuous; parameter nominal; AQI category ordinal"],
  ["Weather (Open-Meteo Historical API)", "JSON – semi-structured", "8,784 h", "hourly, UTC", "rain continuous; weather_code nominal"],
  ["BMTC GTFS (unofficial feed, pinned commit)", "ZIP of CSVs – relational", "2.32 M", "10,128 stops; 351 used", "stop_id nominal; trips/day discrete"],
  ["OpenStreetMap (Overpass API)", "JSON – nested tags + geometry", "12,980", "1.8 km around each station", "highway nominal; length continuous"],
  ["BBMP SWD flood-vulnerable points", "PDF table", "199 → 191", "city-wide, 2020-21", "severity ordinal; lat/lon continuous"],
  ["News headlines (GDELT DOC API)", "JSON with free text – unstructured", "931 → 847", "Mar 2025 – Feb 2026", "title text; tags nominal"],
  ["Holiday calendar (typed by us from DPAR PDF)", "CSV – structured", "365 days", "study year", "holiday nominal; long weekend binary"],
], [2550, 1700, 900, 1850, 2026], { size: 16 }));
body.push(gap());
body.push(H2("V profile"));
body.push(
  B("**Volume.** The largest time-series table has **1,271,160 rows**: 6.8 MB gzipped, 159 MB as text and about 450 MB in pandas memory, above Excel's 1,048,576-row limit. After keeping 4 pollutants and the study window it holds 488,215 readings, which resample to 43,800 station-hours. The static GTFS stop_times file is larger again (~2.1 M rows, 455 MB unzipped), so we read only 2 of its columns."),
  B("**Velocity.** Each station reports every 15 minutes, about **144 readings per hour** across the five. In practice the PM feed repeats one hourly value four times (75% of PM readings equal the previous one), so the effective PM resolution is hourly; NO2 and CO really change every 15 minutes. Weather arrives hourly in UTC; GDELT updates every 15 minutes."),
  B("**Variety.** CSV, two very differently shaped JSONs, a ZIP of relational text files, a PDF table and free-text headlines. Keys had to be built for time (IST quarter-hours vs UTC hours vs compact UTC strings), space (distances between stations, stops, footpaths and flood points) and identity (OpenAQ ids vs suffixed station names)."),
  B("**Which V dominated.** Volume and velocity chose the tools: cleaning and resampling also run in PySpark, and only the 8,760-row hourly city series goes into the spreadsheet. Variety cost the most time: every source needed its own parser before anything could be joined."),
);
body.push(P("**Scope check.** 12 months of 15-minute data (> hourly requirement); 7 sources (≥ 3); 3 JSON APIs (Open-Meteo, Overpass, GDELT); text source (GDELT headlines); hand-built holiday calendar; largest table 1.27 M rows (≥ 100,000)."));

// ---- d. Pipeline
body.push(H1("4. Pipeline: from source to chart"));
body.push(P("Every step is a numbered script in `src/`; `python run_all.py` rebuilds all tables and charts from `data/raw/` in about a minute. The PySpark job and the MySQL loader are run separately because they need Java and a database server."));
body.push(table([
  ["Step", "Script", "In → out", "Tool"],
  ["1 Download", "01_download.py", "7 sources → data/raw (+ SHA-256 checksums)", "requests"],
  ["2 Flatten weather", "02_flatten_weather.py", "column-array JSON → one row per hour, UTC → IST slot", "pandas"],
  ["3 Clean AQ", "03_clean_air_quality.py", "1.27 M readings → flags → hourly grid (43,800) + gap chart", "pandas"],
  ["4 Calendar", "04_build_calendar.py", "hand-typed holidays → 365-day calendar, long weekends", "pandas"],
  ["5 Flood points", "05_parse_waterlogging.py", "BBMP PDF → 191 points with coordinates", "pdftotext + regex"],
  ["6 Spatial", "06_build_spatial.py", "GTFS + OSM + flood points → 351 stops with 300 m metrics", "pandas, haversine"],
  ["7 Text", "07_process_news.py", "nested GDELT JSON → 847 tagged headlines", "pandas, regex"],
  ["8 Analysis", "08_analysis.py", "joins, z-scores, score, 7 charts, tables", "pandas, matplotlib"],
  ["9 SQL", "09_load_mysql.py + sql/", "9 tables, 8 queries", "MySQL 8"],
  ["10 Spreadsheet", "10_spreadsheet_pivot.py", "AVERAGEIFS pivot vs pandas pivot", "Excel, pandas"],
  ["Spark", "spark/spark_resample_join.py", "raw 1.27 M → clean → hourly → join weather → hour × weekday", "PySpark"],
], [1500, 2500, 3900, 1126], { size: 16 }));
body.push(gap());
body.push(H2("Representations and SQL"));
body.push(P("The weather JSON stores each variable as a parallel array (`hourly.time[]`, `hourly.rain[]`); we flatten it to one row per hour in pandas and, in Spark, with `arrays_zip` + `explode`. The relational model has **9 tables** linked by primary and foreign keys (Figure 1): `stations`, `readings` (15-min, 488,215 rows), `readings_hourly`, `weather_hourly`, `calendar`, `bus_stops`, `pedestrian_features` (1:1 with stops), `waterlogging_locations` and `news_articles`. All times are stored in IST using one rule: slot 18:00 = 17:30–18:30 IST, because a UTC weather hour ends at :30 in India. Eight working queries (Appendix C) use JOINs across up to four tables and GROUP BY; for example, Q4 compares evening PM2.5 in rainy and dry hours by season, and Q6 counts, per station area, the stops with no mapped footpath that are also near a flood point."));
body.push(...figure(path.join(ROOT, "docs", "er_diagram.png"), "Figure 1. ER diagram of the MySQL schema (sql/schema.sql). PK/FK marked; readings_hourly joins weather_hourly on slot_ist.", 4.4));
body.push(H2("PySpark and reproducibility"));
body.push(P("`spark/spark_resample_join.py` loads all five raw AQ files (1,271,160 rows), casts text to numbers and timestamps (session time zone Asia/Kolkata), applies the same six cleaning rules as pandas using window functions (lag for flat-lines, a 13-row rolling median for spikes), resamples 15-minute readings to hourly slots with the completeness rule, flattens the weather JSON, joins the two on `slot`, and groups by hour and weekday. It prints the row count after every step and asserts that UTC 13:00 maps to IST slot 18:00. Row counts are in Appendix D. Outsiders can rerun everything from the README; the repository history shows commits from every member."));

// ---- e. Cleaning log
body.push(H1("5. Cleaning log"));
body.push(P("Every decision is logged with the rows it touched (53 entries; full log in Appendix B and `docs/cleaning_log.csv`, written automatically by each script). We never delete a bad reading: it becomes NULL with a flag, so every choice stays visible. Key decisions:"));
body.push(table([
  ["Topic", "Problem found", "Rows", "Action and reason"],
  ["Time zones", "Weather hours are UTC strings without offset; AQ uses +05:30, so a weather hour ends at :30 IST", "8,784", "Localise to UTC, convert to IST, map both sources to a common hourly slot (17:30–18:30 = 18:00); otherwise every join is 5.5 h off"],
  ["Type casting", "AQ values stored as quoted text; GDELT time '20250614T013000Z'; BBMP lat/lon as PDF text", "491,472 / 931 / 199", "Explicit casts and formats; weather_code kept as a nominal category (averaging codes is meaningless)"],
  ["Units", "CO labelled 'ppb' but median 0.39", "107,258", "Relabelled mg/m³ (values unchanged): 0.4 ppb is physically impossible, 0.4 mg/m³ matches CPCB"],
  ["Gaps", "All 5 stations silent for ~10 days in Jan 2026; Bapuji Nagar out for 53 days (Nov–Dec 2025)", "PM2.5 10–26% of hours missing", "Gaps ≤ 3 h interpolated linearly (1,478 PM2.5 hours); longer gaps left empty (6,828) – filling them would invent data. Figure 2"],
  ["Completeness", "Hours with too few 15-min readings", "6,743 gas hours", "NO2/CO need ≥ 2 of 4 readings; PM needs 1 because PM quarter-hours repeat one hourly value"],
  ["Invalid values", "Negative CO (Bapuji Nagar); NO2 = 1,270.7 (≥ 999 sentinel)", "20 / 1", "Set to NULL: a concentration cannot be negative; 999+ is a fill value"],
  ["Error code", "Jayanagar PM2.5 = 794.0 repeated on 8 days while neighbours read ~15", "34", "Rule: > 10× station median and ≥ 20 times on ≥ 3 days → error code"],
  ["Impossible pair", "PM2.5 > PM10 at the same time (e.g. Bapuji 26 Jan 2026: 813 vs 63)", "701", "PM2.5 set to NULL: PM2.5 is a subset of PM10"],
  ["Stuck sensor", "Same value for ≥ 24 readings (6 h)", "283", "NULL: real air never stays exactly constant for 6 h (runs of 4 are normal here)"],
  ["Spikes vs real events", "Single readings > 4× the 3-h rolling median (incl. a daily 04:30 NO2 jump at Bapuji Nagar in May)", "144", "NULL as glitches. Deepavali (19–23 Oct) and New Year's Eve are protected: 139 extreme readings kept, PM2.5 up to 251 µg/m³ – real exposure"],
  ["Flood points", "3 coordinates outside Bengaluru (e.g. 12.01 instead of 13.01); 5 duplicates", "8", "Dropped, not guessed"],
  ["Duplicates (text)", "Same story found by both queries / syndicated", "84", "Kept first copy"],
  ["Normalisation", "Stations differ in level (annual PM2.5 means 19–32 µg/m³)", "43,800", "z-score within station to compare daily shapes (Figure 3); min-max / capped 0–1 scaling for the priority score"],
], [1300, 2900, 1150, 3676], { size: 16 }));
body.push(gap());
body.push(...figure(FIG("fig01_sensor_gaps.png"), "Figure 2. Share of hours with no valid PM2.5 by station and month, after cleaning and before gap filling.", 6.2));
body.push(...figure(FIG("fig04_normalised_station_profiles.png"), "Figure 3. Normalised (z-score) daily PM2.5 profile per station, working days.", 5.6));

// ---- f. Findings
body.push(H1("6. Findings"));
body.push(H2("6.1 Bengaluru's PM2.5 peaks in the evening, not at the morning rush"));
body.push(P("Averaged over the year and the five stations, PM2.5 climbs from 17:00 and peaks at **20:00–21:00** (Saturday 20:00 = 32.4 µg/m³, the highest cell); evenings (19:00–22:00) average 30 µg/m³ against 23 in the afternoon. The same rhythm appears at every station once levels are removed (Figure 3). The spreadsheet pivot reproduces all 168 cells exactly (Appendix C)."));
body.push(...figure(FIG("fig02_heatmap_pm25_hour_weekday.png"), "Figure 4. Hour-by-weekday heatmap of mean PM2.5 (µg/m³), five stations, Mar 2025 – Feb 2026.", 6.2));
body.push(H2("6.2 Monsoon rain falls just before and during the evening commute"));
body.push(P("Rain is concentrated in the afternoon: the wettest hours in May–October are 15:00–17:00 (23–26% of those hours rainy), and **51% of the season's rain** fell between 14:00 and 20:00. In July–October, 14–19% of evening-commute hours (17:00–20:00) were rainy versus 4–6% of morning-commute hours (08:00–10:00). In July alone, 50 mm fell in evening-commute hours against 13 mm in morning ones."));
body.push(...figure(FIG("fig03_rain_timing_month_hour.png"), "Figure 5. Percentage of rainy hours (≥ 0.5 mm) by month and hour; boxes mark commute windows.", 6.2));
body.push(H2("6.3 Rain hours are cleaner hours – wet and dirty commutes are different problems"));
body.push(P("Comparing rainy and dry hours **inside the same station, month and hour** (501 comparisons) removes the season and time-of-day effects. PM2.5 is a median **27% lower** in rainy hours and lower in 81% of comparisons; NO2 shows no change (median −0.3%). Daily CPCB categories agree: in the south-west monsoon 511 of 535 station-days were 'Good', while 'Moderate' or worse days cluster in the north-east monsoon and winter. This is an association: rain washing out particles and fewer vehicles on the road both fit it, and we do not separate them."));
body.push(...figure(FIG("fig05_rain_vs_pm25_same_hour.png"), "Figure 6. Joining weather and air quality: median % difference in PM2.5, rainy vs dry hours, same station-month-hour.", 5.6));
body.push(H2("6.4 Where: Silk Board and Mysore Road stops combine all three gaps"));
body.push(P("Of 351 BMTC stops within 1.5 km of a station, 59 have no mapped footpath at all within 300 m and 128 are within 500 m of a BBMP flood point. Each stop gets a score: the mean of a pedestrian gap (mapped footpath per metre of main road, crossings per km), closeness to the nearest flood point (0 at 1 km or more) and evening PM2.5 at the nearest station, each scaled 0–1. Among busy stops (≥ median Wednesday trips), the top locations sit around **Silk Board** (mean score 80) and **Bapuji Nagar / Mysore Road** (73). The top-10 is stable: changing the weights keeps 10/10 stops, and dropping pollution entirely still keeps 8/10."));
body.push(table([
  ["#", "Stop location (area)", "Bus calls / Wed", "Footpath per m of main road", "Nearest flood point", "Score"],
  ["1", "Central Silk Board (Silk Board, 6 bays)", "6,191", "0.07", "72 m", "96"],
  ["2", "Nayandahalli Junction (Bapuji Nagar)", "1,225", "0.04", "59 m", "92"],
  ["3", "Mysore Road Bus Station (Bapuji Nagar)", "4,760", "0.01", "64 m", "91"],
  ["4", "Mysore Road Metro Station (Bapuji Nagar)", "3,992", "0.05", "127 m", "90"],
  ["5", "Deepanjalinagara (Bapuji Nagar)", "2,552", "0.00", "174 m", "89"],
  ["6", "Madivala (Silk Board)", "3,433", "0.41", "221 m", "88"],
  ["7", "Kuvempunagara Bus Stand, BTM Layout (Silk Board)", "1,685", "0.26", "61 m", "87"],
], [400, 3400, 1300, 1500, 1300, 1126], { size: 16 }));
body.push(gap());
body.push(...figure(FIG("fig06_stop_priority_ranking.png"), "Figure 7. Top-15 busy stop locations by priority score, split into its three components.", 5.8));
body.push(H2("6.5 Public reporting follows the rain"));
body.push(P("Of 847 unique Bengaluru headlines, those tagged waterlogging/flood track monthly rainfall (r = 0.63 over the 8 months the API answered). May 2025 – the month of the 18–19 May floods – had the most even though the API's 250-row cap truncated it. Headlines name Hebbal and the Outer Ring Road most often; footpath stories are rare, which suggests pedestrian problems are under-reported rather than absent."));
body.push(...figure(FIG("fig07_news_vs_rain.png"), "Figure 8. Joining text and weather: monthly rain (top) and waterlogging headlines (bottom); 'no data' = API refused.", 5.8));

// ---- g. Recommendation
body.push(H1("7. Recommendation"));
body.push(
  N("**Fix the walk at the top stops before the next monsoon (May 2027).** Audit footpaths, crossings and the nearest drain at the top-10 locations, starting with Central Silk Board and the Mysore Road cluster (Mysore Road bus and metro stops, Nayandahalli, Deepanjalinagara). These carry more than 20,000 bus calls on a weekday and sit 60–180 m from a BBMP flood point. Desilt those drains in April–May."),
  N("**Time rain alerts for 15:00–17:00 on monsoon days (June–October).** That is when rain peaks and just before the 17:00–20:00 commute. Push them through the Namma BMTC app and stop displays."),
  N("**Keep pollution alerts separate and seasonal.** The worst air is on dry evenings, 20:00–22:00, in November–February, not on rainy days. A monsoon plan should not lead with air quality."),
  N("**Close the data gaps the city controls.** Publish an updated flood-point list with coordinates every year; ground-check the 59 stops where OSM shows no footpath (Bapuji Nagar shows almost none mapped); add monitors in the east (Whitefield, Mahadevapura), which has no station in our set."),
);
body.push(P("These follow from where the three conditions overlap. They are where to look first, not proof that the works will reduce flooding, pollution or pedestrian risk; that needs before/after measurement."));

// ---- h. Limitations
body.push(H1("8. Limitations and bias"));
body.push(
  B("**Sensor coverage.** Five KSPCB stations for a city of well over 10 million. East Bengaluru (Whitefield, Mahadevapura, KR Puram), Yelahanka, Electronic City and the western outskirts have no station in our set, so their stops are not assessed at all; the ranking only covers stops within 1.5 km of a monitor."),
  B("**Station is not person.** A reading up to 1.5 km away stands in for air at the stop; it is not personal exposure."),
  B("**One weather cell.** Open-Meteo reanalysis for the city centre smooths local cloudbursts; rain at Silk Board and Hebbal can differ."),
  B("**Mapped is not built.** OSM is volunteer-mapped. Areas with fewer mappers look worse; a missing footpath in OSM may exist on the ground, and a mapped one may be broken or encroached."),
  B("**Old flood list.** BBMP's coordinates are from 2020-21; some points are fixed, new ones are missing. Our flood component describes a known history of flooding, not the present."),
  B("**Unofficial GTFS.** Built from the Namma BMTC app (2026-27 snapshot); only routes with live tracking appear, and 47 selected stops show no Wednesday trips."),
  B("**Who appears in the news.** GDELT indexes online English-heavy outlets that favour high-profile spots (Hebbal, ORR); 98 non-English headlines were not tagged, and 4 of 12 waterlogging months and 6 of 12 footpath months are missing because the API rate-limited us. Missing months are shown as missing, never as zero. We used no Reddit or Kaggle data."),
  B("**Correlation, not cause.** Rainy-vs-dry comparisons hold station, month and hour constant, but traffic, wind and humidity also change with rain."),
);

// ---- i. Reflection
body.push(H1("9. Reflection"));
body.push(
  P("**How the question changed.** We expected the worst monsoon commutes to combine rain, flooding and dirty air. The data split them: rain hours were the cleanest, and the dirty-air peak sat in dry winter evenings. The question moved from 'where do all three overlap in time' to 'where do footpath gaps and flood points overlap, and when does rain hit the commute', with air quality treated as a separate, seasonal problem."),
  P("**What the data forced on us.** OpenCity's 15-minute files sat behind a bot check, so we used OpenAQ's copy of the same CPCB feed. The 15-minute PM feed turned out to be hourly values repeated, which changed our completeness rule. The +05:30 offset made 'the same hour' a design decision. GDELT's rate limit left gaps we chose to show rather than fill."),
  P("**With better data we would:** use BMTC stop-level boardings instead of scheduled trips; use a ward-level footpath audit instead of OSM; use BBMP's current flood points and the KSNDMC rain-gauge network instead of one reanalysis cell; add the east-Bengaluru monitors; and use traffic counts to separate washout from fewer vehicles."),
);

// ================================================================== APPENDICES
const app = [];
app.push(pageBreak(), H1("Appendix A. Source register"));
app.push(P("All sources accessed on 21 November 2026 (IST). SHA-256 checksums of the analysed files: `data/raw_checksums_sha256.txt`. Nothing was scraped behind a login and no personal data was collected.", { run: { size: 20 } }));
app.push(table([
  ["#", "Dataset / publisher", "URL used", "Method & format", "Terms"],
  ["1", "15-min AQ, OpenAQ ids 6973, 6974, 6975, 6983, 6984 (KSPCB → CPCB → OpenAQ)", "openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=<id>/year=/month=/", "S3 listing + daily files joined per station; CSV.gz", "Open data with attribution (OpenAQ; licence per location)"],
  ["2", "Hourly weather (Open-Meteo Historical, ERA5)", "archive-api.open-meteo.com/v1/archive?latitude=12.9716&longitude=77.5946&start_date=2025-02-28&end_date=2026-02-28&hourly=...&timezone=GMT", "REST, JSON, no key", "CC BY 4.0"],
  ["3", "BMTC GTFS (Vonter/bmtc-gtfs, unofficial)", "raw.githubusercontent.com/Vonter/bmtc-gtfs/a4702664.../gtfs/bmtc.zip", "Pinned commit; ZIP of CSVs", "See repository; data from BMTC app"],
  ["4", "OpenStreetMap via Overpass", "overpass-api.de/api/interpreter (query in data/raw/osm/overpass_query.txt)", "POST, JSON", "ODbL 1.0, © OpenStreetMap contributors"],
  ["5", "BBMP SWD vulnerable points 2020-21", "citizenmatters.in/wp-content/uploads/2020/06/SWD-Vul-lat-long-details-18.5.2020-1.pdf", "PDF, parsed with pdftotext", "Government document"],
  ["6", "Karnataka general holidays 2025 (DPAR 16 HHL 2024)", "cag.gov.in/uploads/media/Karnataka-State-Holidays-2025-...pdf", "Scanned PDF, typed by hand", "Public notification"],
  ["7", "Holidays Jan–Feb 2026 (CG offices Karnataka + DPAR 16 HHL 2025 as reported)", "cag.gov.in/uploads/media/Holiday-List-2026-...pdf", "PDF, typed by hand", "Public"],
  ["8", "News headlines (GDELT DOC 2.0)", "api.gdeltproject.org/api/v2/doc/doc?query=...&mode=artlist&format=json", "REST, JSON, monthly windows, 2 themes", "Free with citation"],
], [350, 2200, 3200, 1700, 1576], { size: 15 }));
app.push(P("Dropped: OpenCity 15-min CSVs and flood KML (Cloudflare bot check – not bypassed); OpenAQ API v3 (needs key; archive has the same records); Reddit (not needed, avoids usernames).", { run: { size: 18 } }));

app.push(pageBreak(), H1("Appendix B. Full cleaning log"));
app.push(P("Generated by the pipeline (`docs/cleaning_log.csv`). Example rows for every outlier type: `outputs/tables/outlier_examples.csv`.", { run: { size: 20 } }));
app.push(table(
  [["#", "Dataset", "Problem found", "Rows", "Action", "Why"]].concat(
    cleaning.map((r, i) => [String(i + 1), r.dataset, r.problem_found,
      /^\d+$/.test(r.rows_affected) ? fmt(r.rows_affected) : r.rows_affected, r.action_taken, r.why])),
  [350, 1300, 2300, 800, 2100, 2176], { size: 14 }));

app.push(pageBreak(), H1("Appendix C. SQL queries and spreadsheet check"));
app.push(table([
  ["Query", "What it answers", "JOIN / GROUP BY"],
  ["Q1", "Completeness of each station's hourly PM2.5", "readings_hourly ⋈ stations; GROUP BY station"],
  ["Q2", "Which cleaning flags removed readings", "GROUP BY station, parameter, flag"],
  ["Q3", "Hour × weekday mean PM2.5 (heatmap in SQL)", "GROUP BY weekday, hour"],
  ["Q4", "Evening PM2.5/NO2, rainy vs dry, by season, working days", "readings_hourly ⋈ weather_hourly ⋈ calendar; GROUP BY season, rain"],
  ["Q5", "Share of rainy hours in morning vs evening commute by month", "weather_hourly ⋈ calendar; GROUP BY month"],
  ["Q6", "Stops with no mapped footpath and near a flood point, per area", "bus_stops ⋈ pedestrian_features ⋈ stations; GROUP BY area"],
  ["Q7", "Busiest stops with no mapped footpath + nearest flood point", "4-table JOIN"],
  ["Q8", "Waterlogging headlines vs monthly rain", "two GROUP BY subqueries joined on month"],
], [800, 4700, 3526], { size: 16 }));
app.push(gap());
app.push(P("**Sample output (Q1):** Bapuji Nagar 23.9% of hours missing after gap rules, Silk Board 16.9%, Jayanagar 13.9%, Hebbal 13.2%, Hombegowda Nagar 10.0%. **Q3:** Saturday 20:00 = 32.1 µg/m³, Friday 20:00 = 31.8 (station-hour average). Full results: `outputs/tables/sql_results.txt`.", { run: { size: 20 } }));
app.push(P("**Spreadsheet vs pandas.** `spreadsheet/pm25_hour_weekday_pivot.xlsx` builds the hour × weekday pivot with AVERAGEIFS over 8,760 hourly rows; `pivot_table` in pandas gives the same 168 values (largest difference 0.0000 µg/m³). The spreadsheet is easier to audit by eye but cannot hold the 1.27 M raw rows, so cleaning must happen in code first.", { run: { size: 20 } }));

app.push(H1("Appendix D. PySpark row counts"));
app.push(P("Fill in from `outputs/tables/spark_row_counts.csv` after running `python spark/spark_resample_join.py`. The pandas column shows the matching pandas counts for comparison.", { run: { size: 20 } }));
app.push(table([
  ["Spark step", "Spark rows", "pandas equivalent"],
  ["1 raw rows, all parameters", "[fill]", "1,271,160"],
  ["2 pollutant readings in study window", "[fill]", "488,215"],
  ["3b valid readings after cleaning", "[fill]", "487,032"],
  ["4 hourly station-slots with ≥ 1 reading", "[fill]", "(grid of 43,800 incl. empty hours)"],
  ["5b weather hourly slots in window", "[fill]", "8,760"],
  ["6 joined station-hours", "[fill]", "43,800 (grid)"],
  ["7a hour × weekday cells", "[fill]", "168"],
], [4000, 1800, 3226], { size: 16 }));

app.push(H1("Appendix E. Use of generative AI"));
app.push(table([
  ["Tool", "What we asked", "What we changed / checked"],
  ["Claude (Anthropic)", "Find public sources for 15-min AQ, weather, GTFS, OSM, flood points, holidays, news; draft the download, cleaning, analysis, SQL and PySpark code, and draft this report and slides", "[Team to complete: e.g. reran every script, checked station ids and holiday dates against the PDFs, reviewed each cleaning threshold, rewrote sections ...]"],
  ["[other tool]", "", ""],
], [1800, 3800, 3426], { size: 16 }));

app.push(H1("Appendix F. Team contribution"));
app.push(table([
  ["Member", "Role", "Main work", "%"],
  ["[Name 1]", "Data collection", "01_download, source register, checksums", ""],
  ["[Name 2]", "Cleaning & time alignment", "02, 03, cleaning log", ""],
  ["[Name 3]", "Spatial data & calendar", "04, 05, 06, manual holiday list", ""],
  ["[Name 4]", "SQL & PySpark", "schema, queries, ER diagram, Spark job", ""],
  ["[Name 5]", "Analysis, charts, story", "07, 08, 10, report and slides", ""],
], [1700, 2300, 4226, 800], { size: 16 }));

// ================================================================== DOCUMENT
const doc = new Document({
  creator: "[Team name]", title: "The Monsoon Last-Mile Trap",
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 28, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true, color: "262626" },
        paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 260 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1300, bottom: 1300, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "The Monsoon Last-Mile Trap · page ", size: 16, color: GREY }),
                 new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY })] })] }) },
    children: [...body, ...app],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "report", "Monsoon_Last_Mile_Report.docx");
  fs.writeFileSync(out, buf);
  console.log("saved", out);
});
