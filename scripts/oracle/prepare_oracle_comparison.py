"""
prepare_oracle_comparison.py
-----------------------------
Reads oracle_performance.csv -> saves oracle_performance_for_comparison.csv
Same structure as redis_performance_for_comparison.csv:
  database, query, runs, avg_ms, min_ms, max_ms
"""

import csv
from pathlib import Path

INPUT_FILE  = Path("results/oracle_performance.csv")
OUTPUT_FILE = Path("results/oracle_performance_for_comparison.csv")


def main():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        print("Run performance_oracle.py first.")
        return

    rows = []
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "database": "Oracle NoSQL",
                "query":    row["query"],
                "runs":     row["runs"],
                "avg_ms":   row["avg_ms"],
                "min_ms":   row["min_ms"],
                "max_ms":   row["max_ms"],
            })

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["database", "query", "runs", "avg_ms", "min_ms", "max_ms"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {OUTPUT_FILE}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
