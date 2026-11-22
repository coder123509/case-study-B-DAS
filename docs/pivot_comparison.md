# Spreadsheet vs pandas: hour-by-weekday PM2.5 pivot

Same input (`data` sheet = city-mean PM2.5 per hour, 8,760 rows), two tools.

| | Spreadsheet (`spreadsheet/pm25_hour_weekday_pivot.xlsx`) | pandas (`src/10_spreadsheet_pivot.py`) |
|---|---|---|
| How | `AVERAGEIFS(pm25, weekday=row, hour=col)` in 168 cells (+ optional native PivotTable) | `df.pivot_table(index='weekday', columns='hour_ist', values='pm25_city', aggfunc='mean')` - one line |
| Missing hours | blank cells are skipped by AVERAGEIFS | NaN skipped by `mean()` |
| Weekday order | typed by hand in column A | `.reindex([...Monday...Sunday])` |
| Re-running on new data | paste new rows, formulas update; range must be extended by hand | rerun the script |
| Scale | fine at 8,760 rows; 1.27 M raw rows exceed Excel's 1,048,576-row limit | handles all rows |
| Audit trail | formulas visible cell by cell | code in git |

**Result:** all 168 cells match. Largest absolute difference = 0.0000 ug/m3 (only rounding: the data sheet stores values to 3 decimals).

Peak cell in both: **Saturday 20:00 = 32.4 ug/m3**.

**Take-away:** the spreadsheet is easier to show to a non-technical reader and to check by hand, but it cannot hold the raw 15-minute table (1.27 M rows), so the cleaning and resampling must happen in pandas / PySpark first. That is the Volume 'V' forcing our tool choice.
