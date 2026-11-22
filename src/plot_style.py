"""
One place for chart styling so every figure looks like it belongs to the same report.

Colours: a colour-blind-checked categorical order (one fixed colour per station,
never re-assigned), a single-hue blue ramp for magnitudes (heatmaps) and a
blue <-> red diverging pair with a grey midpoint for 'above / below average'.
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

import config as C

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STATION_COLOR = {sid: SERIES[i] for i, sid in enumerate(C.STATIONS)}     # fixed per station

INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"
NEUTRAL = "#9a9890"

BLUES = LinearSegmentedColormap.from_list(
    "blues_seq", ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list(
    "blue_red", ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f3a7a0", "#e34948", "#a8211f"])


def apply():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
        "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "font.size": 9.5, "legend.frameon": False, "lines.linewidth": 2,
        "figure.dpi": 110,
    })


def subtitle(ax, text):
    """Grey second line under the finding-style title."""
    ax.text(0, 1.02, text, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")
