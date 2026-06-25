import csv
import json
import time
import redis
from collections import defaultdict
from pathlib import Path

RESULTS_FILE = Path("results/redis_performance.csv")


def get_client():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)


def rget(r, key):
    value = r.get(key)
    return json.loads(value) if value else None


# ── timing helper ────────────────────────────────────────────────────────────

def measure(label, fn, runs=100):
    """Run fn() `runs` times and return timing stats (ms)."""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        end = time.perf_counter()
        times.append((end - start) * 1000)
    return {
        "query":  label,
        "runs":   runs,
        "avg_ms": round(sum(times) / len(times), 4),
        "min_ms": round(min(times), 4),
        "max_ms": round(max(times), 4),
    }


# ── query implementations (same logic as query_redis.py) ────────────────────

def fn_q1(r, city="Philadelphia"):
    r.get(f"city_category:{city}:Restaurants")


def fn_q2(r, business_id):
    r.get(f"business:{business_id}")


def fn_q3(r, business_id):
    r.get(f"business_reviews:{business_id}")


def fn_q4(r, business_id):
    r.get(f"stats:business:{business_id}")


def fn_q5(r, business_id):
    """Top reviews for business (pipeline join)."""
    raw_index = r.get(f"business_reviews:{business_id}")
    if not raw_index:
        return
    review_ids = json.loads(raw_index)["review_ids"]
    pipe = r.pipeline()
    for rid in review_ids:
        pipe.get(f"review:{rid}")
    results = pipe.execute()
    reviews = [json.loads(v) for v in results if v]
    reviews.sort(key=lambda x: x.get("stars", 0), reverse=True)


def fn_q6(r, user_id):
    """User profile + reviews (join)."""
    r.get(f"user:{user_id}")
    raw_index = r.get(f"user_reviews:{user_id}")
    if not raw_index:
        return
    review_ids = json.loads(raw_index)["review_ids"]
    pipe = r.pipeline()
    for rid in review_ids[:10]:
        pipe.get(f"review:{rid}")
    pipe.execute()


def fn_q7(r, city="Philadelphia"):
    """Top businesses by avg stars (full aggregation)."""
    raw = r.get(f"city_category:{city}:Restaurants")
    if not raw:
        return
    business_ids = json.loads(raw)["business_ids"]
    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"stats:business:{bid}")
    raw_stats = pipe.execute()
    pipe2 = r.pipeline()
    for bid in business_ids:
        pipe2.get(f"business:{bid}")
    raw_biz = pipe2.execute()
    ranked = []
    for stats_raw, biz_raw in zip(raw_stats, raw_biz):
        if stats_raw and biz_raw:
            stats = json.loads(stats_raw)
            biz   = json.loads(biz_raw)
            if stats["review_count"] >= 5:
                ranked.append((biz.get("name"), stats["avg_stars"]))
    ranked.sort(key=lambda x: x[1], reverse=True)


def fn_q8(r, business_id):
    """Star distribution histogram."""
    raw_index = r.get(f"business_reviews:{business_id}")
    if not raw_index:
        return
    review_ids = json.loads(raw_index)["review_ids"]
    pipe = r.pipeline()
    for rid in review_ids:
        pipe.get(f"review:{rid}")
    raw = pipe.execute()
    dist = defaultdict(int)
    for v in raw:
        if v:
            dist[int(json.loads(v).get("stars", 0))] += 1


def fn_q9(r, city="Philadelphia"):
    """Most active reviewers (multi-join aggregation)."""
    raw = r.get(f"city_category:{city}:Restaurants")
    if not raw:
        return
    business_ids = json.loads(raw)["business_ids"]
    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"business_reviews:{bid}")
    raw_indexes = pipe.execute()
    all_review_ids = []
    for v in raw_indexes:
        if v:
            all_review_ids.extend(json.loads(v)["review_ids"])
    sample = all_review_ids[:500]   # keep fast for benchmarking
    pipe2 = r.pipeline()
    for rid in sample:
        pipe2.get(f"review:{rid}")
    raw_reviews = pipe2.execute()
    user_count = defaultdict(int)
    for v in raw_reviews:
        if v:
            user_count[json.loads(v).get("user_id")] += 1


def fn_q10(r, city="Philadelphia"):
    """Rating-band distribution."""
    raw = r.get(f"city_category:{city}:Restaurants")
    if not raw:
        return
    business_ids = json.loads(raw)["business_ids"]
    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"stats:business:{bid}")
    raw_stats = pipe.execute()
    bands = defaultdict(int)
    for v in raw_stats:
        if v:
            avg = json.loads(v).get("avg_stars", 0)
            if avg < 3:
                bands["1-2"] += 1
            elif avg < 4:
                bands["3"] += 1
            elif avg < 5:
                bands["4"] += 1
            else:
                bands["5"] += 1


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    r = get_client()

    # Resolve seed IDs
    city_result = rget(r, "city_category:Philadelphia:Restaurants")
    if not city_result:
        print("City index not found. Run import_yelp_redis.py first.")
        return

    business_ids      = city_result["business_ids"]
    first_business_id = business_ids[0]

    reviews_result  = rget(r, f"business_reviews:{first_business_id}")
    first_review_id = None
    first_user_id   = None

    if reviews_result and reviews_result["review_ids"]:
        first_review_id = reviews_result["review_ids"][0]
        review = rget(r, f"review:{first_review_id}")
        if review:
            first_user_id = review.get("user_id")

    RUNS = 100

    query_defs = [
        # (label, lambda)
        ("Q1 – Restaurants in city (simple)",
            lambda: fn_q1(r)),
        ("Q2 – Business by ID (simple)",
            lambda: fn_q2(r, first_business_id)),
        ("Q3 – Review IDs for business (simple)",
            lambda: fn_q3(r, first_business_id)),
        ("Q4 – Business stats (simple)",
            lambda: fn_q4(r, first_business_id)),
        ("Q5 – Top reviews for business (complex join)",
            lambda: fn_q5(r, first_business_id)),
        ("Q6 – User profile + reviews (complex join)",
            lambda: fn_q6(r, first_user_id) if first_user_id else None),
        ("Q7 – Top businesses by avg stars (aggregated)",
            lambda: fn_q7(r)),
        ("Q8 – Star distribution for business (aggregated)",
            lambda: fn_q8(r, first_business_id)),
        ("Q9 – Most active reviewers (aggregated)",
            lambda: fn_q9(r)),
        ("Q10 – Rating-band distribution (aggregated)",
            lambda: fn_q10(r)),
    ]

    results = []
    print(f"Measuring {len(query_defs)} queries × {RUNS} runs each...\n")

    for label, fn in query_defs:
        print(f"  {label}")
        res = measure(label, fn, runs=RUNS)
        results.append(res)
        print(f"    avg={res['avg_ms']} ms  min={res['min_ms']}  max={res['max_ms']}")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "runs", "avg_ms", "min_ms", "max_ms"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()