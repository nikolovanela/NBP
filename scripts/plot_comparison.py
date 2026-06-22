"""
Generates a side-by-side bar chart comparing Oracle NoSQL vs Redis performance.
Run AFTER both oracle_performance_for_comparison.csv and redis_performance_for_comparison.csv exist.
"""

import csv
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

ORACLE_FILE = Path("results/oracle_performance_for_comparison.csv")
REDIS_FILE  = Path("results/redis_performance_for_comparison.csv")
OUTPUT_FILE = Path("results/comparison_chart.png")


def load(path):
    rows = {}
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["query"]] = float(row["avg_ms"])
    return rows


def main():
    for f in [ORACLE_FILE, REDIS_FILE]:
        if not f.exists():
            print(f"Missing file: {f}")
            print("Run prepare_redis_comparison.py (and the Oracle equivalent) first.")
            return

    oracle = load(ORACLE_FILE)
    redis  = load(REDIS_FILE)

    # Use the union of queries, preserving order
    queries = list(dict.fromkeys(list(oracle.keys()) + list(redis.keys())))

    oracle_vals = [oracle.get(q, 0) for q in queries]
    redis_vals  = [redis.get(q, 0)  for q in queries]

    x     = np.arange(len(queries))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))

    bars1 = ax.bar(x - width / 2, oracle_vals, width, label="Oracle NoSQL", color="steelblue")
    bars2 = ax.bar(x + width / 2, redis_vals,  width, label="Redis",        color="tomato")

    ax.bar_label(bars1, fmt="%.2f", fontsize=8, padding=2)
    ax.bar_label(bars2, fmt="%.2f", fontsize=8, padding=2)

    ax.set_ylabel("Average time (ms)")
    ax.set_title("Oracle NoSQL vs Redis — Yelp Dataset Performance (100 runs per query)")
    ax.set_xticks(x)
    ax.set_xticklabels(queries, rotation=15, ha="right", fontsize=9)
    ax.legend()

    plt.tight_layout()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_FILE, dpi=150)
    print(f"Comparison chart saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
