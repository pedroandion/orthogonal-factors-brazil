"""
plotting.py — colors and matplotlib settings shared by the notebooks.

The categorical colors are the eight slots of a palette validated for
colorblind readers, used in a fixed order, so each factor keeps its color in
every chart. Three slots have low contrast on white, so every chart comes
with the table of its values.
"""

import matplotlib as mpl
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import PercentFormatter

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
IDIOSYNCRATIC = "#c3c2b7"
DIVERGING = LinearSegmentedColormap.from_list("diverging", ["#e34948", "#f0efec", "#2a78d6"])
SEQUENTIAL = LinearSegmentedColormap.from_list("sequential", ["#f0efec", "#86b6ef", "#2a78d6", "#1c5cab", "#0d366b"])


def set_style():
    """Thin marks, recessive axes and grid, and the categorical colors in order."""
    mpl.rcParams.update({
        "figure.figsize": (20, 8),
        "axes.prop_cycle": mpl.cycler(color=CATEGORICAL),
        "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": "#52514e",
        "axes.titlesize": 15,
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e1e0d9",
        "grid.linewidth": 0.8,
        "xtick.color": "#898781",
        "ytick.color": "#898781",
        "xtick.labelcolor": "#52514e",
        "ytick.labelcolor": "#52514e",
        "text.color": "#0b0b0b",
        "lines.linewidth": 1.5,
        "legend.frameon": False,
        "font.size": 12,
    })


def factor_colors(factors: list) -> dict:
    """One color per factor, in the order of the full factor list of the notebook."""
    return dict(zip(factors, CATEGORICAL))


def plot_decomposition(ax, components, factors: list, title: str = None):
    """
    Stacked areas of the decomposed R² of each factor and of 1 - R².

    components has one column per factor and one named 'idiosyncratic',
    indexed by date, with values between 0 and 1.
    """
    colors = [factor_colors(factors)[f] for f in factors] + [IDIOSYNCRATIC]
    labels = factors + ["Idiosyncratic (1 - R²)"]
    ax.stackplot(components.index, [components[c] for c in factors + ["idiosyncratic"]],
                 colors=colors, labels=labels, edgecolor="white", linewidth=0.6)
    ax.set_ylim(0, 1)
    ax.margins(x=0)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(False)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    if title:
        ax.set_title(title)


def plot_decomposition_bars(ax, table, factors: list, title: str = None, label_min: float = 0.03):
    """
    Horizontal stacked bars of the decomposed R² of each factor and of 1 - R².

    table has one row per bar and the same columns as in plot_decomposition,
    with values between 0 and 1. Segments of at least label_min are labeled.
    """
    colors = {**factor_colors(factors), "idiosyncratic": IDIOSYNCRATIC}
    left = np.zeros(len(table))
    for component in factors + ["idiosyncratic"]:
        values = table[component].to_numpy(dtype=float)
        label = "Idiosyncratic (1 - R²)" if component == "idiosyncratic" else component
        ax.barh(range(len(table)), values, left=left, height=0.6, color=colors[component],
                edgecolor="white", linewidth=1.5, label=label)
        # White labels inside the fills, except on the yellow slot and the gray
        ink = "#0b0b0b" if colors[component] in ("#eda100", IDIOSYNCRATIC) else "#ffffff"
        for y, (x0, value) in enumerate(zip(left, values)):
            if value >= label_min:
                ax.text(x0 + value / 2, y, f"{value:.0%}", ha="center", va="center", color=ink, fontsize=11)
        left += values
    ax.set_yticks(range(len(table)), table.index)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.invert_yaxis()
    ax.grid(False)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    if title:
        ax.set_title(title)
