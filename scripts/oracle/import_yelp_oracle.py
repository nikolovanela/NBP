"""
import_yelp_oracle.py
---------------------
Imports the Philadelphia Yelp subset into Oracle NoSQL.
Compatible with borneo 5.4.3 — uses plain dict instead of MapValue.
Mirrors import_yelp_redis.py exactly — same keys, same two data models.

Level 1: business:{id}, review:{id}, user:{id}
Level 2: city_category:..., business_reviews:{id}, user_reviews:{id}, stats:business:{id}
"""

import json
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

from borneo import (NoSQLHandle, NoSQLHandleConfig,
                    PutRequest, TableRequest, TableLimits)
from borneo.kv import StoreAccessTokenProvider

ENDPOINT = "http://localhost:8080"
TABLE    = "yelp_kv"

DATA_DIR      = Path("data/processed")
BUSINESS_FILE = DATA_DIR / "business_subset.jsonl"
REVIEW_FILE   = DATA_DIR / "review_subset.jsonl"
USER_FILE     = DATA_DIR / "user_subset.jsonl"


def get_client():
    provider = StoreAccessTokenProvider()
    config   = NoSQLHandleConfig(ENDPOINT, provider)
    return NoSQLHandle(config)


def ensure_table(handle):
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            kv_key   STRING,
            kv_value STRING,
            PRIMARY KEY(kv_key)
        )
    """
    req = TableRequest().set_statement(ddl).set_table_limits(TableLimits(500, 500, 50))
    res = handle.table_request(req)
    res.wait_for_completion(handle, 60000, 1000)
    print(f"[OK] Table '{TABLE}' ready.")


def oset(handle, key, value):
    """Store a Python dict/list as JSON string in Oracle NoSQL."""
    row     = {"kv_key": key, "kv_value": json.dumps(value, ensure_ascii=False)}
    put_req = PutRequest().set_table_name(TABLE).set_value(row)
    handle.put(put_req)


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def import_businesses(handle):
    print("\nImporting businesses...")
    city_category_index = defaultdict(list)
    count = 0

    for business in tqdm(load_jsonl(BUSINESS_FILE)):
        business_id = business["business_id"]
        oset(handle, f"business:{business_id}", business)

        city       = business.get("city", "UNKNOWN")
        categories = business.get("categories") or ""
        if "Restaurants" in categories:
            city_category_index[f"city_category:{city}:Restaurants"].append(business_id)
        count += 1

    print(f"  Businesses written: {count}")
    return city_category_index


def import_users(handle):
    print("Importing users...")
    count = 0
    for user in tqdm(load_jsonl(USER_FILE)):
        oset(handle, f"user:{user['user_id']}", user)
        count += 1
    print(f"  Users written: {count}")


def import_reviews(handle):
    print("Importing reviews...")
    business_reviews = defaultdict(list)
    user_reviews     = defaultdict(list)
    business_stats   = defaultdict(lambda: {"review_count": 0, "stars_sum": 0.0})
    count = 0

    for review in tqdm(load_jsonl(REVIEW_FILE)):
        review_id   = review["review_id"]
        business_id = review["business_id"]
        user_id     = review["user_id"]
        stars       = float(review.get("stars", 0))

        oset(handle, f"review:{review_id}", review)

        business_reviews[business_id].append(review_id)
        user_reviews[user_id].append(review_id)
        business_stats[business_id]["review_count"] += 1
        business_stats[business_id]["stars_sum"]    += stars
        count += 1

    print(f"  Reviews written: {count}")
    return business_reviews, user_reviews, business_stats


def write_aggregate_keys(handle, city_category_index, business_reviews, user_reviews, business_stats):
    print("\nWriting aggregate keys: business_reviews...")
    for business_id, review_ids in tqdm(business_reviews.items()):
        oset(handle, f"business_reviews:{business_id}", {
            "business_id": business_id,
            "review_ids":  review_ids
        })

    print("Writing aggregate keys: user_reviews...")
    for user_id, review_ids in tqdm(user_reviews.items()):
        oset(handle, f"user_reviews:{user_id}", {
            "user_id":    user_id,
            "review_ids": review_ids
        })

    print("Writing aggregate keys: business stats...")
    for business_id, stats in tqdm(business_stats.items()):
        count     = stats["review_count"]
        avg_stars = stats["stars_sum"] / count if count > 0 else 0
        oset(handle, f"stats:business:{business_id}", {
            "business_id":  business_id,
            "review_count": count,
            "avg_stars":    avg_stars
        })

    print("Writing aggregate keys: city category index...")
    for key, business_ids in tqdm(city_category_index.items()):
        oset(handle, key, {"business_ids": business_ids})


def main():
    print("=" * 55)
    print("Yelp -> Oracle NoSQL Import (Two Data Models)")
    print("=" * 55)

    for path in [BUSINESS_FILE, REVIEW_FILE, USER_FILE]:
        if not path.exists():
            print(f"[ERROR] Missing: {path}")
            print("Run prepare_yelp_subset.py first.")
            return

    handle = get_client()
    ensure_table(handle)

    city_category_index = import_businesses(handle)
    import_users(handle)
    business_reviews, user_reviews, business_stats = import_reviews(handle)
    write_aggregate_keys(handle, city_category_index, business_reviews, user_reviews, business_stats)

    handle.close()
    print("\n[DONE] Import finished.")
    print("=" * 55)


if __name__ == "__main__":
    main()
