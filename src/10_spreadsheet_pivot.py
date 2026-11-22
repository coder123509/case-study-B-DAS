"""
Step 10 - Hour-by-weekday pivot: spreadsheet version vs pandas version.

Part A (build): writes spreadsheet/pm25_hour_weekday_pivot.xlsx
   sheet 'data'   : 8,760 rows, one per hour - city-mean PM2.5 (mean of the stations that reported)
   sheet 'pivot'  : weekday x hour grid built with AVERAGEIFS formulas (live, recalculates)
   sheet 'notes'  : how to also make a real Excel PivotTable from the same data
Part B (compare): reads the spreadsheet's calculated values and compares them with the
   pandas pivot_table, writes docs/pivot_comparison.md

Run:  python src/10_spreadsheet_pivot.py build
      -> open the xlsx in Excel (or LibreOffice), let it calculate, SAVE, close
      python src/10_spreadsheet_pivot.py compare
"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

XLSX = C.ROOT / "spreadsheet" / "pm25_hour_weekday_pivot.xlsx"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FONT = "Arial"


def city_hourly():
    aq = pd.read_csv(C.PROCESSED / "aq_hourly.csv")
    city = (aq.groupby(["slot_ist", "date_ist", "weekday", "hour_ist"], as_index=False)
            .agg(pm25_city=("pm25", "mean"), stations_reporting=("pm25", "count")))
    city["slot_ist"] = city["slot_ist"].str[:16]            # '2025-03-01 00:00' (IST)
    return city


def build():
    city = city_hourly()
    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    head = ["slot_ist (IST)", "date", "weekday", "hour", "pm25_city_ugm3", "stations_reporting"]
    ws.append(head)
    for r in city.itertuples(index=False):
        ws.append([r.slot_ist, r.date_ist, r.weekday, int(r.hour_ist),
                   None if pd.isna(r.pm25_city) else round(float(r.pm25_city), 3), int(r.stations_reporting)])
    for c in ws[1]:
        c.font = Font(name=FONT, bold=True)
    ws.freeze_panes = "A2"
    for col, w in zip("ABCDEF", (18, 12, 12, 7, 16, 18)):
        ws.column_dimensions[col].width = w
    last = ws.max_row

    pv = wb.create_sheet("pivot")
    pv["A1"] = "Average city PM2.5 (ug/m3) by weekday and hour - AVERAGEIFS over sheet 'data'"
    pv["A1"].font = Font(name=FONT, bold=True, size=12)
    pv["A2"] = "Blank PM2.5 hours (all stations offline) are ignored by AVERAGEIFS, same as pandas' mean()."
    pv["A2"].font = Font(name=FONT, italic=True, color="555555")
    pv["A4"] = "weekday \\ hour"
    for h in range(24):
        pv.cell(row=4, column=2 + h, value=h)
    for i, d in enumerate(DAYS):
        row = 5 + i
        pv.cell(row=row, column=1, value=d)
        for h in range(24):
            col = 2 + h
            hour_ref = pv.cell(row=4, column=col).coordinate
            f = (f"=AVERAGEIFS(data!$E$2:$E${last},data!$C$2:$C${last},$A{row},"
                 f"data!$D$2:$D${last},{hour_ref})")
            c = pv.cell(row=row, column=col, value=f)
            c.number_format = "0.0"
    pv["A13"] = "row mean"
    for h in range(24):
        col = pv.cell(row=4, column=2 + h).column_letter
        pv.cell(row=13, column=2 + h, value=f"=AVERAGE({col}5:{col}11)").number_format = "0.0"
    for row in pv.iter_rows(min_row=4, max_row=13):
        for c in row:
            c.font = Font(name=FONT, bold=(c.row == 4 or c.column == 1))
            c.alignment = Alignment(horizontal="center")
    pv.column_dimensions["A"].width = 16
    pv.conditional_formatting.add("B5:Y11", ColorScaleRule(start_type="min", start_color="F4F8FD",
                                                           end_type="max", end_color="256ABF"))
    pv["A15"] = "Peak cell:"
    pv["B15"] = "=MAX(B5:Y11)"
    pv["B15"].number_format = "0.0"
    for c in ("A15", "B15"):
        pv[c].font = Font(name=FONT, bold=True)

    nt = wb.create_sheet("notes")
    lines = ["How this sheet was made",
             "1. 'data' = output of src/03_clean_air_quality.py averaged over the 5 stations per hour.",
             "2. 'pivot' uses AVERAGEIFS(value, weekday=row, hour=column) so it recalculates if data changes.",
             "3. To also build a native PivotTable: click any cell in 'data' > Insert > PivotTable >",
             "   Rows = weekday, Columns = hour, Values = Average of pm25_city_ugm3.",
             "   It must give the same numbers as the AVERAGEIFS grid.",
             "4. Save, then run:  python src/10_spreadsheet_pivot.py compare",
             "Source data: OpenAQ archive of CPCB/KSPCB stations (see docs/source_register.md)."]
    for i, t in enumerate(lines, 1):
        nt.cell(row=i, column=1, value=t).font = Font(name=FONT, bold=(i == 1))
    nt.column_dimensions["A"].width = 100
    XLSX.parent.mkdir(exist_ok=True)
    wb.save(XLSX)
    print(f"saved {XLSX.relative_to(C.ROOT)} ({last - 1} data rows). Open it in Excel, save, then run 'compare'.")


def compare():
    wb = load_workbook(XLSX, data_only=True)
    pv = wb["pivot"]
    sheet = pd.DataFrame([[pv.cell(row=5 + i, column=2 + h).value for h in range(24)] for i in range(7)],
                         index=DAYS, columns=range(24))
    if sheet.isna().all().all():
        raise SystemExit("No calculated values found - open the xlsx in Excel/LibreOffice, save it, try again.")
    city = city_hourly()
    pandas_pv = city.pivot_table(index="weekday", columns="hour_ist", values="pm25_city", aggfunc="mean").reindex(DAYS)
    diff = (sheet.astype(float) - pandas_pv).abs()
    worst = diff.max().max()
    md = [
        "# Spreadsheet vs pandas: hour-by-weekday PM2.5 pivot",
        "",
        "Same input (`data` sheet = city-mean PM2.5 per hour, 8,760 rows), two tools.",
        "",
        "| | Spreadsheet (`spreadsheet/pm25_hour_weekday_pivot.xlsx`) | pandas (`src/10_spreadsheet_pivot.py`) |",
        "|---|---|---|",
        "| How | `AVERAGEIFS(pm25, weekday=row, hour=col)` in 168 cells (+ optional native PivotTable) | "
        "`df.pivot_table(index='weekday', columns='hour_ist', values='pm25_city', aggfunc='mean')` - one line |",
        "| Missing hours | blank cells are skipped by AVERAGEIFS | NaN skipped by `mean()` |",
        "| Weekday order | typed by hand in column A | `.reindex([...Monday...Sunday])` |",
        "| Re-running on new data | paste new rows, formulas update; range must be extended by hand | rerun the script |",
        "| Scale | fine at 8,760 rows; 1.27 M raw rows exceed Excel's 1,048,576-row limit | handles all rows |",
        "| Audit trail | formulas visible cell by cell | code in git |",
        "",
        (f"**Result:** all 168 cells match. Largest absolute difference = {worst:.4f} ug/m3 "
         "(only rounding: the data sheet stores values to 3 decimals)." if worst < 0.01 else
         f"**Result:** {(diff > 0.01).sum().sum()} of 168 cells differ by more than 0.01; largest "
         f"difference = {worst:.3f} ug/m3 - investigate before using."),
        "",
        f"Peak cell in both: **{pandas_pv.stack().idxmax()[0]} {pandas_pv.stack().idxmax()[1]:02d}:00 "
        f"= {pandas_pv.stack().max():.1f} ug/m3**.",
        "",
        "**Take-away:** the spreadsheet is easier to show to a non-technical reader and to check by "
        "hand, but it cannot hold the raw 15-minute table (1.27 M rows), so the cleaning and resampling "
        "must happen in pandas / PySpark first. That is the Volume 'V' forcing our tool choice.",
    ]
    (C.DOCS / "pivot_comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    {"build": build, "compare": compare}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
