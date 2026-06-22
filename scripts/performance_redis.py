import csv
import json
import time
import redis
from pathlib import Path


RESULTS_FILE = Path("results/redis_performance.csv")


def get_client():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)


def rget(r, key):
    value = r.get(key)
    return json.loads(value) if value else None


def measure_query(r, label, key, runs=100):
    times = []

    for _ in range(runs):
        start = time.perf_counter()
        r.get(key)
        end   = time.perf_counter()
        times.append((end - start) * 1000)

    return {
        "query":  label,
        "key":    key,
        "runs":   runs,
        "avg_ms": round(sum(times) / len(times), 4),
        "min_ms": round(min(times), 4),
        "max_ms": round(max(times), 4)
    }


def main():
    r = get_client()

    # Resolve dynamic IDs from the data (same approach as Oracle script)
    city_key    = "city_category:Philadelphia:Restaurants"
    city_result = rget(r, city_key)

    if not city_result:
        print("City category key not found. Run import_yelp_redis.py first.")
        return

    business_ids      = city_result["business_ids"]
    first_business_id = business_ids[0]

    reviews_result = rget(r, f"business_reviews:{first_business_id}")
    first_review_id = None
    first_user_id   = None

    if reviews_result and reviews_result["review_ids"]:
        first_review_id = reviews_result["review_ids"][0]
        review = rget(r, f"review:{first_review_id}")
        if review:
            first_user_id = review.get("user_id")

    # Build query list (same 6 scenarios as Oracle)
    queries = [
        {"label": "Get restaurants in city/category", "key": city_key},
        {"label": "Get business by id",               "key": f"business:{first_business_id}"},
        {"label": "Get reviews for business",          "key": f"business_reviews:{first_business_id}"},
        {"label": "Get business statistics",           "key": f"stats:business:{first_business_id}"},
    ]

    if first_review_id:
        queries.append({"label": "Get review by id", "key": f"review:{first_review_id}"})

    if first_user_id:
        queries.append({"label": "Get user by id", "key": f"user:{first_user_id}"})

    # Measure
    results = []
    print("Measuring Redis performance...\n")

    for q in queries:
        print(f"Measuring: {q['label']}")
        result = measure_query(r, q["label"], q["key"], runs=100)
        results.append(result)

    # Save
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "key", "runs", "avg_ms", "min_ms", "max_ms"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {RESULTS_FILE}")
    print("\nResults:")
    for row in results:
        print(row)


if __name__ == "__main__":
    main()
