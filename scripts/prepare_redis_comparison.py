import csv
from pathlib import Path

INPUT_FILE  = Path("results/redis_performance.csv")
OUTPUT_FILE = Path("results/redis_performance_for_comparison.csv")


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        print("Run performance_redis.py first.")
        return

    rows = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "database": "Redis",
                "query":    row["query"],
                "runs":     row["runs"],
                "avg_ms":   row["avg_ms"],
                "min_ms":   row["min_ms"],
                "max_ms":   row["max_ms"],
            })

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["database", "query", "runs", "avg_ms", "min_ms", "max_ms"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Comparison CSV saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()