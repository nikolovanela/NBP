"""
performance_oracle.py
---------------------
Measures 10 query scenarios — same labels as performance_redis.py.
Compatible with borneo 5.4.3 — plain dict instead of MapValue.
Saves to results/oracle_performance.csv
"""

import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from borneo import NoSQLHandle, NoSQLHandleConfig, GetRequest
from borneo.kv import StoreAccessTokenProvider

ENDPOINT     = "http://localhost:8080"
TABLE        = "yelp_kv"
RESULTS_FILE = Path("results/oracle_performance.csv")


def get_client():
    provider = StoreAccessTokenProvider()
    config   = NoSQLHandleConfig(ENDPOINT, provider)
    config.set_timeout(60000)
    config.set_table_request_timeout(60000)
    return NoSQLHandle(config)


def oget(handle, key):
    req = GetRequest().set_table_name(TABLE).set_key({"kv_key": key}).set_timeout(60000)
    res = handle.get(req)
    v   = res.get_value()
    if v is None:
        return None
    return json.loads(v["kv_value"])


def oget_many(handle, keys):
    return [oget(handle, k) for k in keys]


def measure(label, fn, runs=100):
    times = []
    for i in range(runs):
        print(f"      run {i+1}/{runs}...", end="\r")
        start = time.perf_counter()
        fn()
        end   = time.perf_counter()
        times.append((end - start) * 1000)
    print()
    return {
        "query":  label,
        "runs":   runs,
        "avg_ms": round(sum(times) / len(times), 4),
        "min_ms": round(min(times), 4),
        "max_ms": round(max(times), 4),
    }


# ── Query functions ───────────────────────────────────────────────────────────

def fn_q1(handle):
    oget(handle, "city_category:Philadelphia:Restaurants")

def fn_q2(handle, business_id):
    oget(handle, f"business:{business_id}")

def fn_q3(handle, business_id):
    oget(handle, f"business_reviews:{business_id}")

def fn_q4(handle, business_id):
    oget(handle, f"stats:business:{business_id}")

def fn_q5(handle, business_id):
    raw_index = oget(handle, f"business_reviews:{business_id}")
    if not raw_index:
        return
    reviews = oget_many(handle, [f"review:{rid}" for rid in raw_index["review_ids"]])
    reviews = [v for v in reviews if v]
    reviews.sort(key=lambda x: x.get("stars", 0), reverse=True)

def fn_q6(handle, user_id):
    oget(handle, f"user:{user_id}")
    raw_index = oget(handle, f"user_reviews:{user_id}")
    if not raw_index:
        return
    oget_many(handle, [f"review:{rid}" for rid in raw_index["review_ids"][:10]])

def fn_q7(handle):
    """
    Fetches stats for all businesses and ranks by avg_stars.
    Stats keys already contain avg_stars — no need to also fetch business keys.
    This halves the number of GETs vs the original (600 instead of 1200).
    """
    raw = oget(handle, "city_category:Philadelphia:Restaurants")
    if not raw:
        return
    business_ids = raw["business_ids"]
    raw_stats    = oget_many(handle, [f"stats:business:{bid}" for bid in business_ids])
    ranked = []
    for bid, stats in zip(business_ids, raw_stats):
        if stats and stats.get("review_count", 0) >= 5:
            ranked.append((bid, stats["avg_stars"]))
    ranked.sort(key=lambda x: x[1], reverse=True)

def fn_q8(handle, business_id):
    raw_index = oget(handle, f"business_reviews:{business_id}")
    if not raw_index:
        return
    raw  = oget_many(handle, [f"review:{rid}" for rid in raw_index["review_ids"]])
    dist = defaultdict(int)
    for v in raw:
        if v:
            dist[int(v.get("stars", 0))] += 1

def fn_q9(handle):
    raw = oget(handle, "city_category:Philadelphia:Restaurants")
    if not raw:
        return
    raw_indexes = oget_many(handle, [f"business_reviews:{bid}" for bid in raw["business_ids"]])
    all_ids = []
    for v in raw_indexes:
        if v:
            all_ids.extend(v["review_ids"])
    raw_reviews = oget_many(handle, [f"review:{rid}" for rid in all_ids[:500]])
    user_count  = defaultdict(int)
    for v in raw_reviews:
        if v:
            user_count[v.get("user_id")] += 1

def fn_q10(handle):
    raw = oget(handle, "city_category:Philadelphia:Restaurants")
    if not raw:
        return
    raw_stats = oget_many(handle, [f"stats:business:{bid}" for bid in raw["business_ids"]])
    bands     = defaultdict(int)
    for v in raw_stats:
        if v:
            avg = v.get("avg_stars", 0)
            if avg < 3:   bands["1-2"] += 1
            elif avg < 4: bands["3"]   += 1
            elif avg < 5: bands["4"]   += 1
            else:         bands["5"]   += 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    handle = get_client()

    city_result = oget(handle, "city_category:Philadelphia:Restaurants")
    if not city_result:
        print("City index not found. Run import_yelp_oracle.py first.")
        handle.close()
        return

    business_ids      = city_result["business_ids"]
    first_business_id = business_ids[0]

    reviews_result  = oget(handle, f"business_reviews:{first_business_id}")
    first_review_id = None
    first_user_id   = None

    if reviews_result and reviews_result["review_ids"]:
        first_review_id = reviews_result["review_ids"][0]
        review = oget(handle, f"review:{first_review_id}")
        if review:
            first_user_id = review.get("user_id")

    # Q7/Q9/Q10 fetch hundreds of keys per run — reduce runs to stay under timeout
    # Q5 fetches all reviews for one business — also reduced
    query_defs = [
        ("Q1 – Restaurants in city (simple)",              lambda: fn_q1(handle),                                           100),
        ("Q2 – Business by ID (simple)",                   lambda: fn_q2(handle, first_business_id),                        100),
        ("Q3 – Review IDs for business (simple)",          lambda: fn_q3(handle, first_business_id),                        100),
        ("Q4 – Business stats (simple)",                   lambda: fn_q4(handle, first_business_id),                        100),
        ("Q5 – Top reviews for business (complex join)",   lambda: fn_q5(handle, first_business_id),                        10),
        ("Q6 – User profile + reviews (complex join)",     lambda: fn_q6(handle, first_user_id) if first_user_id else None, 100),
        ("Q7 – Top businesses by avg stars (aggregated)",  lambda: fn_q7(handle),                                           5),
        ("Q8 – Star distribution for business (aggregated)", lambda: fn_q8(handle, first_business_id),                      10),
        ("Q9 – Most active reviewers (aggregated)",        lambda: fn_q9(handle),                                           5),
        ("Q10 – Rating-band distribution (aggregated)",    lambda: fn_q10(handle),                                          5),
    ]

    results = []
    print("Measuring Oracle NoSQL performance...\n")

    for label, fn, runs in query_defs:
        print(f"  {label}  ({runs} runs)")
        res = measure(label, fn, runs=runs)
        results.append(res)
        print(f"    avg={res['avg_ms']} ms  min={res['min_ms']}  max={res['max_ms']}")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with RESULTS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "runs", "avg_ms", "min_ms", "max_ms"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {RESULTS_FILE}")
    handle.close()


if __name__ == "__main__":
    main()