// Builds report/Monsoon_Last_Mile_Slides.pptx (10 slides, ~7 minutes).
// Run from the project root:  node report/build_slides.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "report", "Monsoon_Last_Mile_Slides.pptx");

const THEME = {
  name: "Monsoon Last Mile",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B1B1B", lt1: "FFFFFF", dk2: "12343B", lt2: "EEF3F5",
    accent1: "2E86AB",   // rain blue
    accent2: "E07A1F",   // warning orange (problems / dirty air)
    accent3: "3D9970",   // flood-point green (score component)
    accent4: "6C8EA0", accent5: "A23B72", accent6: "F2C14E",
    hlink: "2E86AB", folHlink: "6C8EA0",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";               // 10 x 5.625 in
pres.title = "The Monsoon Last-Mile Trap";
pres.author = "[Team name]";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.25, w: 8.8, h: 1.1,
        fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.5, w: 8.8, h: 1.4,
        fontSize: 20, color: "CFE3EA", valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "LIGHT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75,
        fontSize: 24, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.5, y: 1.05, w: 9.0, h: 0.4,
        fontSize: 14, color: C.accent4, valign: "top", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Monsoon Last-Mile · Case Study B", options: { x: 0.5, y: 5.25, w: 5, h: 0.25,
        fontSize: 9, color: C.accent4, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.25, w: 0.4, h: 0.25, fontSize: 9, color: C.accent4, align: "right" },
});

// ---------------------------------------------------------------- helpers
function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
    fill: { color: fill }, line: { color: fill }, objectName: name });
}
function text(slide, t, opts) { slide.addText(t, { isTextBox: true, margin: 0, ...opts }); }
function circleNum(slide, x, y, n, color = C.accent1) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color }, line: { color }, objectName: `num${n}` });
  text(slide, String(n), { x, y, w: 0.42, h: 0.42, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle" });
}
const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", titleFontFace: "+mn-lt", catAxisLabelColor: "52514E", valAxisLabelColor: "52514E",
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, dataLabelFontSize: 10, legendFontSize: 11,
  dataLabelColor: "333333" };

// ================================================================ 1. Title + answer
pres.addSection({ title: "Answer" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Answer" });
s.addText("The Monsoon Last-Mile Trap", { placeholder: "title" });
s.addText("Fix the walk at Silk Board and Mysore Road bus stops before the next monsoon, and warn commuters from 15:00 on rainy days.",
  { placeholder: "body" });
text(s, "Data and Storytelling · Module 1 · Case Study B   |   [Team name]: [Name 1], [Name 2], [Name 3], [Name 4], [Name 5]",
  { x: 0.6, y: 4.75, w: 8.8, h: 0.35, fontSize: 12, color: "9FC3D1" });
s.addNotes("[Presenter: Name 1] ~30 s. Our answer first: the monsoon problem for bus commuters in Bengaluru is the wet walk to the stop in the late afternoon and evening, and it is worst at Silk Board and Mysore Road. The next slide gives the three numbers behind that.");

// ================================================================ 2. Answer in three numbers
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Answer" });
s.addText("The answer in three numbers", { placeholder: "title" });
s.addText("12 months of 15-minute air data, hourly rain, 351 bus stops, 191 BBMP flood points", { placeholder: "body" });
const stats = [
  ["51%", "of May–Oct rain falls between 14:00 and 20:00", "WHEN: the evening commute gets wet; mornings mostly stay dry", C.accent1],
  ["60–180 m", "from the top busy stops to a BBMP flood point", "WHERE: Silk Board and Mysore Road, with almost no mapped footpath", C.accent3],
  ["−27%", "PM2.5 in rainy hours vs dry ones (same station, month, hour)", "AIR: dirty air is a separate, dry winter-evening problem", C.accent2],
];
stats.forEach(([big, line, tag, col], i) => {
  const x = 0.5 + i * 3.07;
  card(s, x, 1.65, 2.86, 3.3, `stat${i}`);
  text(s, big, { x: x + 0.25, y: 1.85, w: 2.5, h: 0.95, fontSize: 36, bold: true, color: col, fontFace: THEME.headFontFace });
  text(s, line, { x: x + 0.25, y: 2.85, w: 2.4, h: 0.85, fontSize: 14, color: C.text1, valign: "top" });
  text(s, tag, { x: x + 0.25, y: 3.85, w: 2.4, h: 0.9, fontSize: 12, bold: true, color: col, valign: "top" });
});
s.addNotes("[Presenter: Name 1] ~45 s. When: half of the season's rain falls in the six hours before and during the evening rush. Where: the busiest stops with no mapped footpath sit 60 to 180 metres from a known flood point. Air: rainy hours are cleaner, so pollution is not the monsoon problem; it peaks on dry winter evenings.");

// ================================================================ 3. Question & decision
pres.addSection({ title: "Question and data" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Question and data" });
s.addText("Our question was tied to three city decisions", { placeholder: "title" });
s.addText("Footpaths, drains, buses and air are planned separately; the overlap falls between departments", { placeholder: "body" });
card(s, 0.5, 1.65, 4.1, 3.3, "questionCard", C.text2);
text(s, "Research question", { x: 0.75, y: 1.85, w: 3.6, h: 0.35, fontSize: 13, bold: true, color: "9FC3D1" });
text(s, "Where and when does monsoon weather make the last mile to BMTC bus stops most vulnerable, where footpath gaps, waterlogging spots and nearby air pollution overlap?",
  { x: 0.75, y: 2.25, w: 3.6, h: 2.5, fontSize: 17, color: C.background1, valign: "top", fontFace: THEME.headFontFace });
const decisions = [
  ["Where to fix first", "Which stop areas get footpath, crossing and drain work"],
  ["When to warn", "Which hours and months rain alerts should cover"],
  ["Is air part of it?", "Do pollution alerts belong in the monsoon plan"],
];
decisions.forEach(([h, d], i) => {
  const y = 1.65 + i * 1.12;
  circleNum(s, 4.95, y + 0.2, i + 1);
  text(s, h, { x: 5.55, y: y + 0.1, w: 3.9, h: 0.35, fontSize: 16, bold: true, color: C.text2 });
  text(s, d, { x: 5.55, y: y + 0.47, w: 3.9, h: 0.5, fontSize: 14, color: C.text1, valign: "top" });
});
s.addNotes("[Presenter: Name 2] ~35 s. Our question is answerable with data and tied to three decisions the Urban Services Cell actually makes: where to send footpath and drain crews, when to send rain alerts, and whether air quality belongs in the same plan. We rank places for attention; we do not claim any fix will cause less flooding.");

// ================================================================ 4. Data & V profile
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Question and data" });
s.addText("Seven public sources, 1.27 million 15-minute readings", { placeholder: "title" });
s.addText("Every URL, licence and checksum is in the source register", { placeholder: "body" });
const sources = [
  ["Air quality · 5 KSPCB stations", "CSV · 15-min · 1.27 M rows", C.accent1],
  ["Weather · Open-Meteo API", "JSON · hourly · 8,784 h", C.accent1],
  ["Bus stops · BMTC GTFS", "CSV in ZIP · 351 stops used", C.accent4],
  ["Footpaths · OpenStreetMap API", "JSON · 12,980 elements", C.accent4],
  ["Flood points · BBMP SWD", "PDF table · 191 points", C.accent3],
  ["News · GDELT API", "JSON + free text · 847 headlines", C.accent2],
  ["Holidays · typed by us", "CSV from DPAR PDF · 365 days", C.accent4],
];
sources.forEach(([h, d, col], i) => {
  const col2 = i % 2, row = Math.floor(i / 2);
  const x = 0.5 + col2 * 2.7, y = 1.65 + row * 0.84;
  card(s, x, y, 2.55, 0.72, `src${i}`);
  s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: y + 0.26, w: 0.2, h: 0.2, fill: { color: col }, line: { color: col }, objectName: `dot${i}` });
  text(s, h, { x: x + 0.45, y: y + 0.08, w: 2.05, h: 0.3, fontSize: 11, bold: true, color: C.text2 });
  text(s, d, { x: x + 0.45, y: y + 0.38, w: 2.05, h: 0.28, fontSize: 10, color: C.text1 });
});
const vs = [
  ["Volume", "1.27 M", "rows in the largest table: too big for Excel, so PySpark"],
  ["Velocity", "144 / h", "readings per hour, but PM repeats each hourly value 4 times"],
  ["Variety", "5 formats", "CSV, JSON, ZIP, PDF and free text, plus UTC vs IST time"],
];
vs.forEach(([k, big, d], i) => {
  const y = 1.65 + i * 1.12;
  text(s, k.toUpperCase(), { x: 6.15, y, w: 3.3, h: 0.25, fontSize: 11, bold: true, color: C.accent4, charSpacing: 2 });
  text(s, big, { x: 6.15, y: y + 0.25, w: 3.3, h: 0.45, fontSize: 26, bold: true, color: C.text2, fontFace: THEME.headFontFace });
  text(s, d, { x: 6.15, y: y + 0.7, w: 3.35, h: 0.38, fontSize: 11, color: C.text1 });
});
s.addNotes("[Presenter: Name 2] ~40 s. Seven public sources, five formats. The air-quality table is 1.27 million rows of 15-minute readings from five KSPCB stations, taken from OpenAQ's public archive because OpenCity's copy sits behind a bot check. Three JSON APIs: Open-Meteo, OpenStreetMap and GDELT news. A surprise for velocity: the 15-minute PM feed repeats one hourly value four times, so PM is really hourly data.");

// ================================================================ 5. Pipeline
pres.addSection({ title: "Method" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Method" });
s.addText("One script per step, rerunnable end to end", { placeholder: "title" });
s.addText("python run_all.py rebuilds every table and chart from the raw files in about a minute", { placeholder: "body" });
const steps = ["Download\n7 sources", "Flatten\nJSON → rows", "Clean\nflags, gaps", "Align time\nUTC → IST slot", "Join\nAQ × rain × stops", "Analyse\nscore, charts"];
steps.forEach((t, i) => {
  const x = 0.5 + i * 1.53;
  card(s, x, 1.7, 1.3, 1.0, `step${i}`, i === 3 ? C.accent1 : C.background2);
  text(s, t, { x: x + 0.05, y: 1.7, w: 1.2, h: 1.0, fontSize: 12, bold: true, align: "center", valign: "middle",
    color: i === 3 ? C.background1 : C.text2 });
  if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.33, y: 2.1, w: 0.17, h: 0.2,
    fill: { color: C.accent4 }, line: { color: C.accent4 }, objectName: `arrow${i}` });
});
const tools = [
  ["MySQL", "9 tables with keys, ER diagram, 8 queries with JOINs and GROUP BY"],
  ["PySpark", "Cleans and resamples the 1.27 M-row table to hourly, joins rain, groups by hour × weekday"],
  ["Spreadsheet", "Hour × weekday pivot rebuilt in pandas: 168 of 168 cells match"],
];
tools.forEach(([h, d], i) => {
  const x = 0.5 + i * 3.07;
  card(s, x, 3.05, 2.86, 1.85, `tool${i}`);
  text(s, h, { x: x + 0.2, y: 3.2, w: 2.5, h: 0.4, fontSize: 16, bold: true, color: C.text2 });
  text(s, d, { x: x + 0.2, y: 3.62, w: 2.5, h: 1.15, fontSize: 13, color: C.text1, valign: "top" });
});
s.addNotes("[Presenter: Name 3] ~40 s. Each step is one numbered script. The key design step is time alignment: weather comes hourly in UTC, which ends at half past the hour in India, so we put every reading into one IST slot, 17:30 to 18:30 equals the 18:00 slot. The data then lives in nine MySQL tables; PySpark repeats the cleaning and resampling on the full table; and the spreadsheet pivot matches pandas cell for cell.");

// ================================================================ 6. Cleaning
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Method" });
s.addText("Every gap and sensor fault counted, none hidden", { placeholder: "title" });
s.addText("53 logged decisions; bad readings become NULL with a flag, never silently deleted", { placeholder: "body" });
s.addImage({ path: path.join(ROOT, "outputs", "figures", "fig01_sensor_gaps.png"), x: 0.5, y: 1.6, w: 5.3, h: 1.88,
  altText: "Share of missing PM2.5 hours by station and month" });
text(s, "Gaps ≤ 3 h interpolated; the 53-day Bapuji Nagar outage and the 10-day city-wide outage in Jan 2026 left empty",
  { x: 0.5, y: 3.6, w: 5.3, h: 0.6, fontSize: 12, color: C.text1 });
const faults = [
  ["794.0 × 34", "Jayanagar error code: the same 'reading' on 8 days while neighbours read ~15", C.accent2],
  ["701", "PM2.5 above PM10 at the same moment: physically impossible", C.accent2],
  ["283 + 144", "six-hour flat-lines and one-off spikes (incl. a 04:30 calibration jump)", C.accent2],
  ["139 kept", "Deepavali and New Year peaks (PM2.5 up to 251): real events, protected", C.accent3],
];
faults.forEach(([big, d, col], i) => {
  const y = 1.6 + i * 0.84;
  card(s, 6.1, y, 3.4, 0.74, `fault${i}`);
  text(s, big, { x: 6.25, y: y + 0.05, w: 3.1, h: 0.32, fontSize: 15, bold: true, color: col });
  text(s, d, { x: 6.25, y: y + 0.37, w: 3.15, h: 0.34, fontSize: 10.5, color: C.text1 });
});
s.addNotes("[Presenter: Name 3] ~45 s. Gaps: every station went dark for ten days in January 2026, and Bapuji Nagar was out for 53 days. Short gaps up to three hours are interpolated; long ones stay empty, because filling them would invent data. Faults versus real events: we removed a repeated 794 error code, impossible PM2.5-above-PM10 pairs, flat-lines and one-reading spikes, but protected the Deepavali nights, because those peaks are real air people breathe.");

// ================================================================ 7. When
pres.addSection({ title: "Findings" });
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Findings" });
s.addText("Monsoon rain hits the evening commute, not the morning", { placeholder: "title" });
s.addText("% of commute hours with rain ≥ 0.5 mm, Mar 2025 – Feb 2026 (Open-Meteo hourly)", { placeholder: "body" });
const months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb"];
s.addChart(pres.charts.BAR, [
  { name: "Morning 08–10", labels: months, values: [0.0, 2.2, 6.5, 3.3, 4.3, 4.3, 5.6, 5.4, 2.2, 0.0, 0.0, 0.0] },
  { name: "Evening 17–20", labels: months, values: [2.4, 6.7, 12.9, 10.0, 18.5, 16.9, 14.2, 13.7, 0.8, 0.8, 0.0, 0.0] },
], { x: 0.5, y: 1.5, w: 6.3, h: 3.6, barDir: "col", barGapWidthPct: 60, chartColors: [HEX.accent4, HEX.accent1],
  showLegend: true, legendPos: "t", showValue: false, valAxisMaxVal: 20, valAxisMajorUnit: 5,
  valAxisLabelFormatCode: "0\"%\"", valGridLine: { color: "E1E0D9", size: 0.5 }, catGridLine: { style: "none" },
  ...chartText, objectName: "rainChart" });
card(s, 7.05, 1.6, 2.45, 3.4, "whenCard", C.text2);
text(s, "Jul–Oct", { x: 7.25, y: 1.8, w: 2.1, h: 0.3, fontSize: 13, bold: true, color: "9FC3D1" });
text(s, "14–19%", { x: 7.25, y: 2.1, w: 2.1, h: 0.6, fontSize: 32, bold: true, color: C.background1, fontFace: THEME.headFontFace });
text(s, "of evening hours wet, vs 4–6% of mornings", { x: 7.25, y: 2.7, w: 2.1, h: 0.6, fontSize: 12, color: C.background1 });
text(s, "Peak rain: 15:00–17:00, so alerts should go out before the rush", { x: 7.25, y: 3.55, w: 2.1, h: 1.2, fontSize: 12, bold: true, color: "F2C14E" });
s.addNotes("[Presenter: Name 4] ~40 s. This is the 'when'. In every monsoon month the evening bars are far taller than the morning ones. In July 18.5% of evening commute hours were rainy against 4.3% of mornings. Rain peaks between 15:00 and 17:00, so a rain alert at 15:00 reaches people before they leave work.");

// ================================================================ 8. Air
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Findings" });
s.addText("Rainy hours are cleaner: wet and dirty commutes differ", { placeholder: "title" });
s.addText("Median % change in PM2.5, rainy vs dry hour, same station, month and hour (501 comparisons)", { placeholder: "body" });
s.addChart(pres.charts.BAR, [
  { name: "PM2.5 rainy vs dry (%)", labels: ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"],
    values: [2.9, -15.6, -33.1, -26.6, -13.9, -29.7, -22.4, -50.1] },
], { x: 0.5, y: 1.5, w: 6.0, h: 3.6, barDir: "col", barGapWidthPct: 70, chartColors: [HEX.accent1], invertedColors: [HEX.accent1],
  showLegend: false, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0\"%\"",
  valAxisMinVal: -60, valAxisMaxVal: 10, valAxisMajorUnit: 10, valAxisLabelFormatCode: "0\"%\"",
  valGridLine: { color: "E1E0D9", size: 0.5 }, catGridLine: { style: "none" }, ...chartText, objectName: "airChart" });
card(s, 6.8, 1.6, 2.7, 1.55, "airCard1");
text(s, "−27% overall", { x: 7.0, y: 1.72, w: 2.35, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
text(s, "lower in 81% of comparisons; NO2 unchanged", { x: 7.0, y: 2.15, w: 2.35, h: 0.85, fontSize: 12, color: C.text1 });
card(s, 6.8, 3.3, 2.7, 1.7, "airCard2");
text(s, "Worst air: 20–22h", { x: 7.0, y: 3.42, w: 2.35, h: 0.4, fontSize: 18, bold: true, color: C.accent2 });
text(s, "on dry Nov–Feb evenings, outside the monsoon. Association, not proof of cause", { x: 7.0, y: 3.85, w: 2.35, h: 1.05, fontSize: 12, color: C.text1 });
s.addNotes("[Presenter: Name 4] ~40 s. We compared rainy and dry hours inside the same station, month and hour, which holds season and time of day constant. PM2.5 is a median 27% lower when it rains. So the wet commute is not the dirty commute: the pollution peak is 20:00 to 22:00 on dry winter evenings. This is a correlation; washout and fewer vehicles both fit it, and we do not separate them.");

// ================================================================ 9. Where
s = pres.addSlide({ masterName: "LIGHT", sectionTitle: "Findings" });
s.addText("Silk Board and Mysore Road stops top the priority list", { placeholder: "title" });
s.addText("Busy stop locations; score = mean of three parts scaled 0–1 (a screening tool)", { placeholder: "body" });
const locs = ["Central Silk Board", "Nayandahalli Jn (Mysore Rd)", "Mysore Road Bus Stn", "Mysore Road Metro", "Deepanjalinagara", "Madivala", "Kuvempunagara (BTM)"];
const ped = [0.948, 0.990, 0.956, 0.988, 1.000, 0.856, 0.675].map((v) => +(v * 100 / 3).toFixed(1));
const wl = [0.928, 0.941, 0.936, 0.873, 0.826, 0.779, 0.939].map((v) => +(v * 100 / 3).toFixed(1));
const pol = [1.000, 0.832, 0.832, 0.832, 0.832, 1.000, 1.000].map((v) => +(v * 100 / 3).toFixed(1));
const rev = (a) => a.slice().reverse();
s.addChart(pres.charts.BAR, [
  { name: "No mapped footpath / crossing", labels: rev(locs), values: rev(ped) },
  { name: "Near a BBMP flood point", labels: rev(locs), values: rev(wl) },
  { name: "Evening PM2.5 nearby", labels: rev(locs), values: rev(pol) },
], { x: 0.5, y: 1.5, w: 6.3, h: 3.65, barDir: "bar", barGrouping: "stacked", barGapWidthPct: 45,
  chartColors: [HEX.accent1, HEX.accent3, HEX.accent2], showLegend: true, legendPos: "b",
  valAxisMaxVal: 100, valAxisMajorUnit: 20, valGridLine: { color: "E1E0D9", size: 0.5 }, catGridLine: { style: "none" },
  ...chartText, catAxisLabelFontSize: 10, objectName: "whereChart" });
const whereFacts = [
  ["6,191", "bus calls on a Wednesday at Central Silk Board (6 bays), score 96"],
  ["59 m–174 m", "from the Mysore Road cluster to a flood point"],
  ["10 / 10", "top stops unchanged when weights change; 8/10 with pollution removed"],
];
whereFacts.forEach(([big, d], i) => {
  const y = 1.6 + i * 1.15;
  card(s, 7.05, y, 2.45, 1.02, `where${i}`);
  text(s, big, { x: 7.2, y: y + 0.07, w: 2.2, h: 0.38, fontSize: 18, bold: true, color: C.text2 });
  text(s, d, { x: 7.2, y: y + 0.46, w: 2.2, h: 0.52, fontSize: 10.5, color: C.text1 });
});
s.addNotes("[Presenter: Name 5] ~45 s. This is the 'where'. For 351 stops near a monitor we measured what OpenStreetMap shows within a 300-metre walk, and the distance to BBMP's flood points. Central Silk Board and the Mysore Road cluster score highest: busy, almost no mapped footpath, a flood point within 60 to 180 metres. The top ten does not change when we change the weights.");

// ================================================================ 10. Recommendation
pres.addSection({ title: "Recommendation" });
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Recommendation" });
text(s, "What the city should do", { x: 0.6, y: 0.4, w: 8.8, h: 0.7, fontSize: 32, bold: true, color: C.background1, fontFace: THEME.headFontFace });
const recs = [
  ["Fix the walk by May 2027", "Footpath, crossing and drain audit at the top-10 stops, starting with Silk Board and Mysore Road"],
  ["Alert from 15:00", "Rain alerts on monsoon days (Jun–Oct) via Namma BMTC, before the 17:00–20:00 rush"],
  ["Separate the air plan", "Pollution advisories for dry evenings, 20–22h, Nov–Feb"],
  ["Close the data gaps", "Yearly flood points with coordinates; ground-check 59 'no footpath' stops; monitors in the east"],
];
recs.forEach(([h, d], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.6 + col * 4.5, y = 1.35 + row * 1.35;
  circleNum(s, x, y + 0.05, i + 1, i === 2 ? C.accent2 : C.accent1);
  text(s, h, { x: x + 0.6, y, w: 3.7, h: 0.4, fontSize: 16, bold: true, color: C.background1 });
  text(s, d, { x: x + 0.6, y: y + 0.42, w: 3.7, h: 0.8, fontSize: 13, color: "CFE3EA", valign: "top" });
});
text(s, "Limits: 5 stations (none in the east) · one weather grid cell · OSM shows mapped, not built, footpaths · BBMP list from 2020-21 · news gaps from API limits. These rankings say where to look first, not that the works will reduce risk.",
  { x: 0.6, y: 4.2, w: 8.8, h: 0.75, fontSize: 11, color: "9FC3D1", italic: true });
s.addNotes("[Presenter: Name 5] ~40 s, then Q&A. Four actions that follow from the evidence: fix the walk at the top stops before next May; time rain alerts for 15:00; keep pollution alerts for winter evenings; and publish better data. Our limits: five stations and none in the east, one weather cell, OpenStreetMap shows mapped footpaths not built ones, and the flood list is from 2020-21. This ranking says where to look first, not that the works will cut risk. Every member can take questions on any script or cleaning choice.");

// ---------------------------------------------------------------- write + theme
(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("saved", OUT);
})();
