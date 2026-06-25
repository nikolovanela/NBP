import json
import redis
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

DATA_DIR = Path("../data/processed")

BUSINESS_FILE = DATA_DIR / "business_subset.jsonl"
REVIEW_FILE   = DATA_DIR / "review_subset.jsonl"
USER_FILE     = DATA_DIR / "user_subset.jsonl"


def get_client():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)


def rset(r, key, value):
    """Store a Python dict/list as JSON string."""
    r.set(key, json.dumps(value, ensure_ascii=False))


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    r = get_client()
    r.ping()
    print("Connected to Redis on port 6379.")

    business_reviews   = defaultdict(list)
    user_reviews       = defaultdict(list)
    business_stats     = defaultdict(lambda: {"review_count": 0, "stars_sum": 0.0})
    city_category_index = defaultdict(list)

    # ── Level 1: basic entities ──────────────────────────────────────────────

    print("\nImporting businesses...")
    for business in tqdm(load_jsonl(BUSINESS_FILE)):
        business_id = business["business_id"]

        rset(r, f"business:{business_id}", business)

        city       = business.get("city", "UNKNOWN")
        categories = business.get("categories") or ""

        if "Restaurants" in categories:
            city_category_index[f"city_category:{city}:Restaurants"].append(business_id)

    print("Importing users...")
    for user in tqdm(load_jsonl(USER_FILE)):
        rset(r, f"user:{user['user_id']}", user)

    print("Importing reviews...")
    for review in tqdm(load_jsonl(REVIEW_FILE)):
        review_id   = review["review_id"]
        business_id = review["business_id"]
        user_id     = review["user_id"]
        stars       = float(review.get("stars", 0))

        rset(r, f"review:{review_id}", review)

        business_reviews[business_id].append(review_id)
        user_reviews[user_id].append(review_id)

        business_stats[business_id]["review_count"] += 1
        business_stats[business_id]["stars_sum"]    += stars

    # ── Level 2: aggregated / denormalized keys ──────────────────────────────

    print("\nWriting aggregate keys: business_reviews...")
    for business_id, review_ids in tqdm(business_reviews.items()):
        rset(r, f"business_reviews:{business_id}", {
            "business_id": business_id,
            "review_ids":  review_ids
        })

    print("Writing aggregate keys: user_reviews...")
    for user_id, review_ids in tqdm(user_reviews.items()):
        rset(r, f"user_reviews:{user_id}", {
            "user_id":    user_id,
            "review_ids": review_ids
        })

    print("Writing aggregate keys: business stats...")
    for business_id, stats in tqdm(business_stats.items()):
        count    = stats["review_count"]
        avg_stars = stats["stars_sum"] / count if count > 0 else 0
        rset(r, f"stats:business:{business_id}", {
            "business_id":  business_id,
            "review_count": count,
            "avg_stars":    avg_stars
        })

    print("Writing aggregate keys: city category index...")
    for key, business_ids in tqdm(city_category_index.items()):
        rset(r, key, {"business_ids": business_ids})

    total_keys = r.dbsize()
    print(f"\nImport finished. Total keys in Redis: {total_keys}")


if __name__ == "__main__":
    main()
