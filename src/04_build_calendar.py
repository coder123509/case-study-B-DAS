"""
Step 4 - Build the daily calendar table from our hand-typed holiday list.

Input : data/manual/karnataka_holidays_2025_26.csv
        (typed by the team from the Karnataka DPAR holiday notification PDFs in
        data/raw/calendar/ - the 2025 PDF is a scan with OCR errors, so it could
        not be parsed automatically)
Output: data/processed/calendar.csv  (one row per day of the study year)

Rules used:
- Karnataka govt offices are closed on Sundays, the 2nd and 4th Saturday, and
  every general holiday (stated at the top of the notification).
- long weekend = a run of 3 or more consecutive office-closed days.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from utils import CleaningLog

log = CleaningLog("04_calendar")

hol = pd.read_csv(C.MANUAL / "karnataka_holidays_2025_26.csv", parse_dates=["date"])

# --- check our typing: the weekday printed in the notification must match the date
hol["computed_day"] = hol["date"].dt.day_name()
wrong = hol[hol["computed_day"] != hol["day_in_notification"]]
if len(wrong):
    print(wrong[["date", "day_in_notification", "computed_day", "holiday_name"]])
    raise SystemExit("Typing error in the holiday CSV - fix the rows above")
log.add("calendar", "hand-typed holiday dates (2025 notification is a scanned PDF with OCR "
        "errors like '01. 0.2025')", len(hol),
        "typed by hand; every date checked against the weekday printed in the notification",
        "catches typos such as 01.10 vs 01.11")

cal = pd.DataFrame({"date": pd.date_range("2025-03-01", "2026-02-28", freq="D")})
cal["weekday"] = cal["date"].dt.day_name()
cal["weekday_num"] = cal["date"].dt.dayofweek          # Mon=0 ... Sun=6
cal["month"] = cal["date"].dt.month
cal["season"] = cal["month"].map(C.SEASON_BY_MONTH)
cal["saturday_of_month"] = ((cal["date"].dt.day - 1) // 7 + 1).where(cal["weekday_num"] == 5)
cal["is_weekend"] = (cal["weekday_num"] >= 5).astype(int)

cal = cal.merge(hol[["date", "holiday_name", "holiday_type"]], on="date", how="left")
cal["is_general_holiday"] = (cal["holiday_type"] == "general_holiday").astype(int)
cal["is_festival"] = cal["holiday_name"].notna().astype(int)

closed = (cal["weekday_num"] == 6) | cal["saturday_of_month"].isin([2, 4]) | \
         (cal["is_general_holiday"] == 1)
cal["govt_offices_closed"] = closed.astype(int)
cal["is_working_day"] = (~closed).astype(int)

# long weekends: runs of >= 3 closed days
run_id = (cal["govt_offices_closed"] != cal["govt_offices_closed"].shift()).cumsum()
run_len = cal.groupby(run_id)["govt_offices_closed"].transform("size")
cal["is_long_weekend"] = ((cal["govt_offices_closed"] == 1) & (run_len >= 3)).astype(int)

cal["date"] = cal["date"].dt.date
cal.to_csv(C.PROCESSED / "calendar.csv", index=False)
print(cal["season"].value_counts().to_string())
print("general holidays in window:", cal["is_general_holiday"].sum(),
      "| long-weekend days:", cal["is_long_weekend"].sum(),
      "| working days:", cal["is_working_day"].sum())
print(cal[cal["is_long_weekend"] == 1][["date", "weekday", "holiday_name"]].to_string(index=False))
log.save()
