"""
plot_oracle_performance.py
--------------------------
Reads oracle_performance.csv -> saves oracle_performance_chart.png
Same style/colors as plot_redis_performance.py.
"""

import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

INPUT_FILE  = Path("results/oracle_performance.csv")
OUTPUT_FILE = Path("results/oracle_performance_chart.png")

CATEGORY_COLORS = {
    "simple":     "#4C9BE8",
    "complex":    "#F5A623",
    "aggregated": "#7ED321",
}


def categorize(label):
    l = label.lower()
    if "simple"  in l: return "simple"
    if "complex" in l: return "complex"
    return "aggregated"


def main():
    if not INPUT_FILE.exists():
        print(f"Not found: {INPUT_FILE}")
        print("Run performance_oracle.py first.")
        return

    labels, avg_ms, err_low, err_high, colors = [], [], [], [], []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            labels.append(row["query"])
            avg = float(row["avg_ms"])
            mn  = float(row["min_ms"])
            mx  = float(row["max_ms"])
            avg_ms.append(avg)
            err_low.append(avg - mn)
            err_high.append(mx - avg)
            colors.append(CATEGORY_COLORS[categorize(row["query"])])

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(13, 6))

    bars = ax.bar(x, avg_ms, color=colors,
                  yerr=[err_low, err_high],
                  error_kw=dict(ecolor="gray", capsize=4, linewidth=1))

    for bar, val in zip(bars, avg_ms):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(err_high) * 0.05,
                f"{val:.2f}", ha="center", va="bottom", fontsize=7.5)

    ax.set_ylabel("Average time (ms)", fontsize=10)
    ax.set_title("Oracle NoSQL Performance — Yelp Dataset", fontsize=12)
    ax.set_xticks(x)
    clean = [
        lbl.replace(" (simple)", "").replace(" (complex join)", "").replace(" (aggregated)", "")
        for lbl in labels
    ]
    ax.set_xticklabels(clean, fontsize=8, rotation=20, ha="right")

    patches = [mpatches.Patch(color=v, label=k.capitalize())
               for k, v in CATEGORY_COLORS.items()]
    ax.legend(handles=patches, fontsize=9)

    plt.tight_layout(pad=2)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_FILE, dpi=150)
    print(f"Chart saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
