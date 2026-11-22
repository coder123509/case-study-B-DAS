"""
Small helpers shared by the scripts.

- CleaningLog: every cleaning decision is written as one row
  (step, problem, rows affected, action, reason) to docs/cleaning_log.csv.
  Re-running a script replaces that script's old rows, so the log never
  has duplicates.
- haversine_m: distance in metres between lat/lon points (no GIS library needed).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

LOG_PATH = C.DOCS / "cleaning_log.csv"
LOG_COLS = ["step", "dataset", "problem_found", "rows_affected", "action_taken", "why"]


class CleaningLog:
    def __init__(self, step):
        self.step = step
        self.rows = []

    def add(self, dataset, problem, rows_affected, action, why):
        self.rows.append({"step": self.step, "dataset": dataset, "problem_found": problem,
                          "rows_affected": rows_affected, "action_taken": action, "why": why})
        print(f"  [log] {dataset}: {problem} -> {rows_affected}")

    def save(self):
        old = pd.read_csv(LOG_PATH) if LOG_PATH.exists() else pd.DataFrame(columns=LOG_COLS)
        old = old[old["step"] != self.step]
        new = pd.concat([old, pd.DataFrame(self.rows, columns=LOG_COLS)], ignore_index=True)
        new = new.sort_values("step", kind="stable")
        new.to_csv(LOG_PATH, index=False)


def hour_slot(ts_end_ist):
    """
    Map an 'end of measuring interval' timestamp (IST) to our common hourly slot.

    Why: India is UTC+05:30, so a weather value for the UTC hour 12:00-13:00
    covers 17:30-18:30 IST. We therefore define slot "18:00" = the window
    17:30-18:30 IST, and put every 15-min AQ reading into the slot whose
    window contains it. Same formula for both sources:
        slot = floor_to_hour(ts_end - 1 min + 30 min)
    Examples: AQ 17:45 -> 18:00 ; AQ 18:30 -> 18:00 ; AQ 18:45 -> 19:00 ;
              weather 18:30 IST (UTC 13:00) -> 18:00
    """
    return (ts_end_ist - pd.Timedelta(minutes=1) + pd.Timedelta(minutes=30)).dt.floor("h")


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres. Works on numbers or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


def line_length_m(coords):
    """Length of a polyline given as a list of (lat, lon)."""
    if len(coords) < 2:
        return 0.0
    a = np.array(coords, dtype=float)
    return float(haversine_m(a[:-1, 0], a[:-1, 1], a[1:, 0], a[1:, 1]).sum())
