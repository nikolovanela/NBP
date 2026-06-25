"""
query_oracle.py
---------------
10 query scenarios identical to query_redis.py.
Compatible with borneo 5.4.3 — uses plain dict instead of MapValue.

Simple    : Q1–Q4  (single key lookup)
Complex   : Q5–Q6  (multi-key join)
Aggregated: Q7–Q10 (pipeline fetch + in-memory aggregation)
"""

import json
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

from borneo import NoSQLHandle, NoSQLHandleConfig, GetRequest
from borneo.kv import StoreAccessTokenProvider

ENDPOINT = "http://localhost:8080"
TABLE    = "yelp_kv"


def get_client():
    provider = StoreAccessTokenProvider()
    config   = NoSQLHandleConfig(ENDPOINT, provider)
    config.set_timeout(30000)        # 30s — needed for aggregated queries (Q7, Q9)
    config.set_table_request_timeout(30000)
    return NoSQLHandle(config)


def oget(handle, key):
    """Fetch one key and parse JSON. Returns None if not found."""
    req = GetRequest().set_table_name(TABLE).set_key({"kv_key": key}).set_timeout(30000)
    res = handle.get(req)
    v   = res.get_value()
    if v is None:
        return None
    return json.loads(v["kv_value"])


def oget_many(handle, keys):
    """Fetch multiple keys sequentially — mirrors Redis pipeline structure."""
    return [oget(handle, k) for k in keys]


# ════════════════════════════════════════════════════════════
#  SIMPLE QUERIES
# ════════════════════════════════════════════════════════════

def q1_restaurants_in_city(handle, city="Philadelphia"):
    """Q1 (Simple): List all restaurant business IDs in a city."""
    print(f"\n=== Q1 (Simple): Restaurants in {city} ===")
    result = oget(handle, f"city_category:{city}:Restaurants")
    if not result:
        print("Key not found.")
        return []
    ids = result["business_ids"]
    print(f"Total restaurants: {len(ids)}")
    print(f"First 3 IDs: {ids[:3]}")
    return ids


def q2_business_by_id(handle, business_id):
    """Q2 (Simple): Fetch one business by ID."""
    print(f"\n=== Q2 (Simple): Business by ID ===")
    b = oget(handle, f"business:{business_id}")
    if b:
        print(f"  Name      : {b.get('name')}")
        print(f"  City      : {b.get('city')}")
        print(f"  Stars     : {b.get('stars')}")
        print(f"  Categories: {b.get('categories')}")
    return b


def q3_reviews_for_business(handle, business_id):
    """Q3 (Simple): Get all review IDs for a business."""
    print(f"\n=== Q3 (Simple): Review IDs for business ===")
    result = oget(handle, f"business_reviews:{business_id}")
    if result:
        ids = result["review_ids"]
        print(f"  Total reviews: {len(ids)}")
        print(f"  First 3: {ids[:3]}")
        return ids
    return []


def q4_business_stats(handle, business_id):
    """Q4 (Simple): Fetch pre-computed stats for a business."""
    print(f"\n=== Q4 (Simple): Business stats ===")
    stats = oget(handle, f"stats:business:{business_id}")
    if stats:
        print(f"  Review count : {stats.get('review_count')}")
        print(f"  Avg stars    : {stats.get('avg_stars'):.3f}")
    return stats


# ════════════════════════════════════════════════════════════
#  COMPLEX QUERIES
# ════════════════════════════════════════════════════════════

def q5_top_reviews_for_business(handle, business_id, top_n=5):
    """Q5 (Complex): Fetch full review objects and sort by stars.
    Multi-key join: business_reviews key + N × review keys.
    """
    print(f"\n=== Q5 (Complex): Top-{top_n} reviews for business (join) ===")
    review_index = oget(handle, f"business_reviews:{business_id}")
    if not review_index:
        print("  No review index found.")
        return []

    review_ids = review_index["review_ids"]
    raw_values = oget_many(handle, [f"review:{rid}" for rid in review_ids])
    reviews    = [v for v in raw_values if v]
    reviews.sort(key=lambda x: x.get("stars", 0), reverse=True)

    for rev in reviews[:top_n]:
        print(f"  [{rev.get('stars')}★] {rev.get('text', '')[:80]}...")
    return reviews[:top_n]


def q6_user_profile_with_reviews(handle, user_id, preview=3):
    """Q6 (Complex): Fetch user profile + review texts (join).
    Joins: user key + user_reviews key + N × review keys.
    """
    print(f"\n=== Q6 (Complex): User profile + reviews (join) ===")
    user = oget(handle, f"user:{user_id}")
    if not user:
        print("  User not found.")
        return

    print(f"  Name         : {user.get('name')}")
    print(f"  Review count : {user.get('review_count')}")
    print(f"  Avg stars    : {user.get('average_stars')}")

    review_index = oget(handle, f"user_reviews:{user_id}")
    if not review_index:
        print("  No reviews found for this user.")
        return

    review_ids = review_index["review_ids"]
    print(f"  Reviews in DB: {len(review_ids)}")

    raw = oget_many(handle, [f"review:{rid}" for rid in review_ids[:preview]])
    print(f"  Last {preview} reviews:")
    for v in raw:
        if v:
            print(f"    [{v.get('stars')}★] {v.get('text', '')[:70]}...")


# ════════════════════════════════════════════════════════════
#  AGGREGATED QUERIES
# ════════════════════════════════════════════════════════════

def q7_top_businesses_by_avg_stars(handle, city="Philadelphia", top_n=10):
    """Q7 (Aggregated): Rank all businesses by avg stars."""
    print(f"\n=== Q7 (Aggregated): Top-{top_n} businesses by avg stars in {city} ===")
    city_result = oget(handle, f"city_category:{city}:Restaurants")
    if not city_result:
        print("  City index not found.")
        return []

    business_ids = city_result["business_ids"]
    raw_stats    = oget_many(handle, [f"stats:business:{bid}" for bid in business_ids])
    raw_biz      = oget_many(handle, [f"business:{bid}"       for bid in business_ids])

    ranked = []
    for stats, biz in zip(raw_stats, raw_biz):
        if not stats or not biz:
            continue
        if stats["review_count"] >= 5:
            ranked.append({
                "name":         biz.get("name"),
                "avg_stars":    round(stats["avg_stars"], 3),
                "review_count": stats["review_count"]
            })

    ranked.sort(key=lambda x: x["avg_stars"], reverse=True)

    for i, entry in enumerate(ranked[:top_n], 1):
        print(f"  {i:2}. {entry['name']:<40} "
              f"{entry['avg_stars']:.2f}★  ({entry['review_count']} reviews)")
    return ranked[:top_n]


def q8_star_distribution_for_business(handle, business_id):
    """Q8 (Aggregated): Star-rating distribution (histogram) for one business."""
    print(f"\n=== Q8 (Aggregated): Star distribution for business ===")
    review_index = oget(handle, f"business_reviews:{business_id}")
    if not review_index:
        print("  No reviews found.")
        return {}

    review_ids = review_index["review_ids"]
    raw        = oget_many(handle, [f"review:{rid}" for rid in review_ids])

    distribution = defaultdict(int)
    for v in raw:
        if v:
            distribution[int(v.get("stars", 0))] += 1

    total = sum(distribution.values())
    print(f"  Total reviews analysed: {total}")
    for star in sorted(distribution):
        bar = "█" * distribution[star]
        print(f"  {star}★  {distribution[star]:4d}  {bar}")
    return dict(distribution)


def q9_most_active_reviewers(handle, city="Philadelphia", top_n=5):
    """Q9 (Aggregated): Find users with most reviews in a city."""
    print(f"\n=== Q9 (Aggregated): Most active reviewers in {city} ===")
    city_result = oget(handle, f"city_category:{city}:Restaurants")
    if not city_result:
        print("  City index not found.")
        return []

    business_ids = city_result["business_ids"]
    raw_indexes  = oget_many(handle, [f"business_reviews:{bid}" for bid in business_ids])

    all_review_ids = []
    for v in raw_indexes:
        if v:
            all_review_ids.extend(v["review_ids"])

    sample      = all_review_ids[:500]
    raw_reviews = oget_many(handle, [f"review:{rid}" for rid in sample])

    user_review_count = defaultdict(int)
    for v in raw_reviews:
        if v:
            user_review_count[v.get("user_id")] += 1

    top_users = sorted(user_review_count.items(), key=lambda x: x[1], reverse=True)[:top_n]
    raw_users = oget_many(handle, [f"user:{uid}" for uid, _ in top_users])

    print(f"  Top {top_n} most active reviewers (from {len(sample)} reviews):")
    for (uid, count), user in zip(top_users, raw_users):
        name = user.get("name", "?") if user else "?"
        print(f"    {name:<25} — {count} reviews")

    return top_users


def q10_avg_stars_by_star_rating_group(handle, city="Philadelphia"):
    """Q10 (Aggregated): Group businesses into rating bands."""
    print(f"\n=== Q10 (Aggregated): Rating-band distribution for {city} restaurants ===")
    city_result = oget(handle, f"city_category:{city}:Restaurants")
    if not city_result:
        return {}

    business_ids = city_result["business_ids"]
    raw_stats    = oget_many(handle, [f"stats:business:{bid}" for bid in business_ids])

    bands = {"1-2★": 0, "3★": 0, "4★": 0, "5★": 0}
    for v in raw_stats:
        if v:
            avg = v.get("avg_stars", 0)
            if avg < 3:
                bands["1-2★"] += 1
            elif avg < 4:
                bands["3★"] += 1
            elif avg < 5:
                bands["4★"] += 1
            else:
                bands["5★"] += 1

    total = sum(bands.values())
    print(f"  Total businesses: {total}")
    for band, count in bands.items():
        pct = count / total * 100 if total else 0
        bar = "█" * (count // max(total // 40, 1))
        print(f"  {band:<6}  {count:4d}  ({pct:5.1f}%)  {bar}")
    return bands


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

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

    q1_restaurants_in_city(handle)
    q2_business_by_id(handle, first_business_id)
    q3_reviews_for_business(handle, first_business_id)
    q4_business_stats(handle, first_business_id)
    q5_top_reviews_for_business(handle, first_business_id)
    if first_user_id:
        q6_user_profile_with_reviews(handle, first_user_id)
    q7_top_businesses_by_avg_stars(handle)
    q8_star_distribution_for_business(handle, first_business_id)
    q9_most_active_reviewers(handle)
    q10_avg_stars_by_star_rating_group(handle)

    handle.close()


if __name__ == "__main__":
    main()
