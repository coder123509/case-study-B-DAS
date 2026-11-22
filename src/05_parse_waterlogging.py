"""
Step 5 - Turn the BBMP storm-water-drain (SWD) PDF into a table.

Input : data/raw/waterlogging/bbmp_swd_vulnerable_locations_2020-21.pdf
        "List of vulnerable points identified for the year 2020-21" (BBMP SWD dept.)
Output: data/processed/waterlogging_locations.csv

The PDF was exported from Excel, so `pdftotext -layout` keeps the columns.
One problem: long location names wrap onto the line above/below the line
that has the coordinates. We attach those wrapped pieces to the nearest
coordinate line (see assign_fragments). Names may still need a manual
look, but the coordinates - which is what we actually use - are exact.

Needs the `pdftotext` command (poppler). On Windows: conda install -c conda-forge poppler
"""
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from utils import CleaningLog

log = CleaningLog("05_waterlogging")
pdf = C.RAW / "waterlogging" / "bbmp_swd_vulnerable_locations_2020-21.pdf"
text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
                      text=True, check=True).stdout
lines = text.splitlines()

COORD = re.compile(r"^\s*(\d+)?\s*(.*?)\s+(1[23]\.\d+)\s+(77\.\d+)\s+(\d+)\s*(.*)$")
NAME_COL_END = 58          # location names sit in the first ~58 characters
SKIP = ("Sl. No", "Geographic", "Latitude", "radius", "BRUHUT", "STORM WATER", "List of")

def next_text(i):
    for l in lines[i + 1:i + 4]:
        if l.strip():
            return l.strip()
    return ""


zone, severity = None, None
rows, fragments = [], []
for i, line in enumerate(lines):
    s = line.strip()
    if not s:
        continue
    # a zone header is a centred line followed by "a) Severely..." or "b) Moderately..."
    if line.startswith(" " * 40) and next_text(i).startswith(("a) ", "b) ")) \
            and not any(ch.isdigit() for ch in s) and s[0].isupper() \
            and not any(ch in s for ch in "&()"):
        zone = s.title().replace(" Zone", "")
        continue
    m = COORD.match(line)
    if m:
        sl, name, lat, lon, buf, rest = m.groups()
        rows.append({"line": i, "zone": zone, "severity": severity, "sl_no": sl,
                     "name": name.strip(), "lat": lat, "lon": lon, "buffer_m": buf,
                     "remarks_raw": rest.strip()})
        continue
    if s.startswith("a) Severely"):
        severity = "severe"
    elif s.startswith("b) Moderately"):
        severity = "moderate"
    elif not s.startswith(SKIP):
        frag = line[:NAME_COL_END].strip()
        if frag and not frag.isdigit():
            fragments.append((i, frag))


def assign_fragments(rows, fragments):
    """Attach each wrapped name piece to the closest coordinate line.
    On a tie, prefer the coordinate line whose own name cell is empty."""
    coord_lines = [r["line"] for r in rows]
    for i, frag in fragments:
        dists = [abs(i - c) for c in coord_lines]
        best = min(dists)
        if best > 2:
            continue
        cands = [k for k, d in enumerate(dists) if d == best]
        k = next((k for k in cands if rows[k]["name"] == ""), cands[-1] if i < coord_lines[cands[-1]] else cands[0])
        side = "before" if i < rows[k]["line"] else "after"
        rows[k].setdefault(side, []).append(frag)
    for r in rows:
        r["name"] = " ".join(r.get("before", []) + ([r["name"]] if r["name"] else []) + r.get("after", []))


assign_fragments(rows, fragments)
wl = pd.DataFrame(rows).drop(columns=["before", "after"], errors="ignore")
log.add("waterlogging_locations", "PDF table (not machine-readable); names wrap over 2-3 lines",
        len(wl), "parsed with pdftotext -layout + regex; wrapped name pieces joined to the "
        "nearest coordinate line", "OpenCity's KML copy is behind a bot-check we cannot pass")

# --- type casting
wl["lat"] = wl["lat"].astype(float)
wl["lon"] = wl["lon"].astype(float)
wl["buffer_m"] = wl["buffer_m"].astype(int)
wl["sl_no"] = pd.to_numeric(wl["sl_no"], errors="coerce").astype("Int64")
log.add("waterlogging_locations", "lat / lon / buffer read as text", len(wl),
        "cast to float / int", "needed for distance calculations")

# --- checks
outside = ~(wl["lat"].between(12.7, 13.3) & wl["lon"].between(77.3, 77.9))
bad_pts = "; ".join(f"{r.name[:35]} ({r.lat}, {r.lon})" for r in wl[outside].itertuples())
log.add("waterlogging_locations", "coordinates outside the Bengaluru bounding box: " + (bad_pts or "none"),
        int(outside.sum()), "dropped (not guessed)" if outside.sum() else "none found",
        "clear typos in the BBMP sheet (e.g. 12.01 instead of 13.01) - correcting them would be guessing")
wl = wl[~outside]
dups = wl.duplicated(["lat", "lon"], keep="first")
log.add("waterlogging_locations", "same coordinates listed twice (e.g. once per zone)",
        int(dups.sum()), "kept first, dropped repeats", "one physical spot should count once")
wl = wl[~dups]
log.add("waterlogging_locations", "list is from 2020-21 (BBMP has not published a newer "
        "point list with coordinates)", len(wl), "used as-is, flagged as limitation",
        "some spots may have been fixed since; others may be new. Treat as 'known history of flooding'")

wl.insert(0, "wl_id", range(1, len(wl) + 1))
wl["zone"] = wl["zone"].fillna("East")      # first block has its header above the table title
wl = wl[["wl_id", "zone", "severity", "sl_no", "name", "lat", "lon", "buffer_m", "remarks_raw"]]
wl.to_csv(C.PROCESSED / "waterlogging_locations.csv", index=False)
print(wl.groupby(["zone", "severity"]).size().to_string())
print(f"saved {len(wl)} waterlogging points")
log.save()
