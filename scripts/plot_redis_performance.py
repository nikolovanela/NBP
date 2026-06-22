import csv
import matplotlib.pyplot as plt
from pathlib import Path

INPUT_FILE  = Path("results/redis_performance.csv")
OUTPUT_FILE = Path("results/redis_performance_chart.png")


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        print("Run performance_redis.py first.")
        return

    queries = []
    avg_ms  = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append(row["query"])
            avg_ms.append(float(row["avg_ms"]))

    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.barh(queries, avg_ms, color="tomato")
    ax.bar_label(bars, fmt="%.2f ms", padding=4)

    ax.set_xlabel("Average time (ms)")
    ax.set_title("Redis Performance - Yelp Dataset (100 runs per query)")
    ax.invert_yaxis()

    plt.tight_layout()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_FILE, dpi=150)
    print(f"Chart saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
