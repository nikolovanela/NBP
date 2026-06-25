import json
import sys
import redis
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")


def get_client():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)


def rget(r, key):
    value = r.get(key)
    return json.loads(value) if value else None


# ════════════════════════════════════════════════════════════
#  SIMPLE QUERIES
# ════════════════════════════════════════════════════════════

def q1_restaurants_in_city(r, city="Philadelphia"):
    """Q1 (Simple): List all restaurant business IDs in a city."""
    print(f"\n=== Q1 (Simple): Restaurants in {city} ===")
    result = rget(r, f"city_category:{city}:Restaurants")
    if not result:
        print("Key not found.")
        return []
    ids = result["business_ids"]
    print(f"Total restaurants: {len(ids)}")
    print(f"First 3 IDs: {ids[:3]}")
    return ids


def q2_business_by_id(r, business_id):
    """Q2 (Simple): Fetch one business by ID."""
    print(f"\n=== Q2 (Simple): Business by ID ===")
    b = rget(r, f"business:{business_id}")
    if b:
        print(f"  Name    : {b.get('name')}")
        print(f"  City    : {b.get('city')}")
        print(f"  Stars   : {b.get('stars')}")
        print(f"  Categories: {b.get('categories')}")
    return b


def q3_reviews_for_business(r, business_id):
    """Q3 (Simple): Get all review IDs for a business."""
    print(f"\n=== Q3 (Simple): Review IDs for business ===")
    result = rget(r, f"business_reviews:{business_id}")
    if result:
        ids = result["review_ids"]
        print(f"  Total reviews: {len(ids)}")
        print(f"  First 3: {ids[:3]}")
        return ids
    return []


def q4_business_stats(r, business_id):
    """Q4 (Simple): Fetch pre-computed stats for a business."""
    print(f"\n=== Q4 (Simple): Business stats ===")
    stats = rget(r, f"stats:business:{business_id}")
    if stats:
        print(f"  Review count : {stats.get('review_count')}")
        print(f"  Avg stars    : {stats.get('avg_stars'):.3f}")
    return stats


# ════════════════════════════════════════════════════════════
#  COMPLEX QUERIES
# ════════════════════════════════════════════════════════════

def q5_top_reviews_for_business(r, business_id, top_n=5):
    """Q5 (Complex): Fetch full review objects for a business and sort by stars.
    Requires: business_reviews key  +  N × review keys  (multi-key join).
    """
    print(f"\n=== Q5 (Complex): Top-{top_n} reviews for business (join) ===")
    review_index = rget(r, f"business_reviews:{business_id}")
    if not review_index:
        print("  No review index found.")
        return []

    review_ids = review_index["review_ids"]

    # Pipeline: fetch all review objects in one round-trip
    pipe = r.pipeline()
    for rid in review_ids:
        pipe.get(f"review:{rid}")
    raw_values = pipe.execute()

    reviews = [json.loads(v) for v in raw_values if v]
    reviews.sort(key=lambda x: x.get("stars", 0), reverse=True)

    for rev in reviews[:top_n]:
        print(f"  [{rev.get('stars')}★] {rev.get('text', '')[:80]}...")
    return reviews[:top_n]


def q6_user_profile_with_reviews(r, user_id, preview=3):
    """Q6 (Complex): Fetch user profile + all their review texts (join).
    Joins: user key  +  user_reviews key  +  N × review keys.
    """
    print(f"\n=== Q6 (Complex): User profile + reviews (join) ===")
    user = rget(r, f"user:{user_id}")
    if not user:
        print("  User not found.")
        return

    print(f"  Name         : {user.get('name')}")
    print(f"  Review count : {user.get('review_count')}")
    print(f"  Avg stars    : {user.get('average_stars')}")

    review_index = rget(r, f"user_reviews:{user_id}")
    if not review_index:
        print("  No reviews found for this user.")
        return

    review_ids = review_index["review_ids"]
    print(f"  Reviews in DB: {len(review_ids)}")

    pipe = r.pipeline()
    for rid in review_ids[:preview]:
        pipe.get(f"review:{rid}")
    raw = pipe.execute()

    print(f"  Last {preview} reviews:")
    for v in raw:
        if v:
            rev = json.loads(v)
            print(f"    [{rev.get('stars')}★] {rev.get('text', '')[:70]}...")


# ════════════════════════════════════════════════════════════
#  AGGREGATED QUERIES
# ════════════════════════════════════════════════════════════

def q7_top_businesses_by_avg_stars(r, city="Philadelphia", top_n=10):
    """Q7 (Aggregated): Rank ALL businesses in a city by computed avg stars.
    Reads city index → fetches all stats keys via pipeline → sorts in Python.
    """
    print(f"\n=== Q7 (Aggregated): Top-{top_n} businesses by avg stars in {city} ===")
    city_result = rget(r, f"city_category:{city}:Restaurants")
    if not city_result:
        print("  City index not found.")
        return []

    business_ids = city_result["business_ids"]

    # Batch-fetch stats
    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"stats:business:{bid}")
    raw_stats = pipe.execute()

    # Batch-fetch names
    pipe2 = r.pipeline()
    for bid in business_ids:
        pipe2.get(f"business:{bid}")
    raw_biz = pipe2.execute()

    ranked = []
    for stats_raw, biz_raw in zip(raw_stats, raw_biz):
        if not stats_raw or not biz_raw:
            continue
        stats = json.loads(stats_raw)
        biz   = json.loads(biz_raw)
        if stats["review_count"] >= 5:          # ignore businesses with <5 reviews
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


def q8_star_distribution_for_business(r, business_id):
    """Q8 (Aggregated): Star-rating distribution (histogram) for one business.
    Reads all review objects and counts 1–5 star buckets.
    """
    print(f"\n=== Q8 (Aggregated): Star distribution for business ===")
    review_index = rget(r, f"business_reviews:{business_id}")
    if not review_index:
        print("  No reviews found.")
        return {}

    review_ids = review_index["review_ids"]

    pipe = r.pipeline()
    for rid in review_ids:
        pipe.get(f"review:{rid}")
    raw = pipe.execute()

    distribution = defaultdict(int)
    for v in raw:
        if v:
            rev = json.loads(v)
            stars = int(rev.get("stars", 0))
            distribution[stars] += 1

    total = sum(distribution.values())
    print(f"  Total reviews analysed: {total}")
    for star in sorted(distribution):
        bar = "█" * distribution[star]
        print(f"  {star}★  {distribution[star]:4d}  {bar}")
    return dict(distribution)


def q9_most_active_reviewers(r, city="Philadelphia", top_n=5):
    """Q9 (Aggregated): Find users who wrote the most reviews for restaurants
    in a city.  Joins city index → business_reviews → reviews → users.
    """
    print(f"\n=== Q9 (Aggregated): Most active reviewers in {city} ===")
    city_result = rget(r, f"city_category:{city}:Restaurants")
    if not city_result:
        print("  City index not found.")
        return []

    business_ids = city_result["business_ids"]

    # Batch-fetch all business_reviews indexes
    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"business_reviews:{bid}")
    raw_indexes = pipe.execute()

    # Collect ALL review IDs across all businesses
    all_review_ids = []
    for raw in raw_indexes:
        if raw:
            idx = json.loads(raw)
            all_review_ids.extend(idx["review_ids"])

    # Batch-fetch reviews (limit to 500 — same as Oracle for fair comparison)
    sample = all_review_ids[:500]
    pipe2 = r.pipeline()
    for rid in sample:
        pipe2.get(f"review:{rid}")
    raw_reviews = pipe2.execute()

    user_review_count = defaultdict(int)
    for v in raw_reviews:
        if v:
            rev = json.loads(v)
            user_review_count[rev.get("user_id")] += 1

    top_users = sorted(user_review_count.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Fetch user names
    pipe3 = r.pipeline()
    for uid, _ in top_users:
        pipe3.get(f"user:{uid}")
    raw_users = pipe3.execute()

    print(f"  Top {top_n} most active reviewers (from {len(sample)} reviews):")
    for (uid, count), user_raw in zip(top_users, raw_users):
        name = json.loads(user_raw).get("name", "?") if user_raw else "?"
        print(f"    {name:<25} — {count} reviews")

    return top_users


def q10_avg_stars_by_star_rating_group(r, city="Philadelphia"):
    """Q10 (Aggregated): Group businesses into rating bands (1-2, 3, 4, 5 stars)
    and count how many fall in each band. Full aggregation report.
    """
    print(f"\n=== Q10 (Aggregated): Rating-band distribution for {city} restaurants ===")
    city_result = rget(r, f"city_category:{city}:Restaurants")
    if not city_result:
        return {}

    business_ids = city_result["business_ids"]

    pipe = r.pipeline()
    for bid in business_ids:
        pipe.get(f"stats:business:{bid}")
    raw_stats = pipe.execute()

    bands = {"1-2★": 0, "3★": 0, "4★": 0, "5★": 0}
    for v in raw_stats:
        if v:
            stats = json.loads(v)
            avg = stats.get("avg_stars", 0)
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
#  MAIN — run all queries in sequence
# ════════════════════════════════════════════════════════════

def main():
    r = get_client()

    # ── Resolve seed IDs from the data ──
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

    # ── Run all 10 queries ──
    q1_restaurants_in_city(r)
    q2_business_by_id(r, first_business_id)
    q3_reviews_for_business(r, first_business_id)
    q4_business_stats(r, first_business_id)
    q5_top_reviews_for_business(r, first_business_id)
    if first_user_id:
        q6_user_profile_with_reviews(r, first_user_id)
    q7_top_businesses_by_avg_stars(r)
    q8_star_distribution_for_business(r, first_business_id)
    q9_most_active_reviewers(r)
    q10_avg_stars_by_star_rating_group(r)


if __name__ == "__main__":
    main()