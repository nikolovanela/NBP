import json
from pathlib import Path

RAW_DIR = Path("data/raw")
OUT_DIR = Path("../data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BUSINESS_FILE = RAW_DIR / "yelp_academic_dataset_business.json"
REVIEW_FILE = RAW_DIR / "yelp_academic_dataset_review.json"
USER_FILE = RAW_DIR / "yelp_academic_dataset_user.json"

BUSINESS_OUT = OUT_DIR / "business_subset.jsonl"
REVIEW_OUT = OUT_DIR / "review_subset.jsonl"
USER_OUT = OUT_DIR / "user_subset.jsonl"

CITY = "Philadelphia"
CATEGORY = "Restaurants"

MAX_BUSINESSES = 3000
MAX_REVIEWS = 50000

business_ids = set()
user_ids = set()

print("Filtering businesses...")

with BUSINESS_FILE.open("r", encoding="utf-8") as f, BUSINESS_OUT.open("w", encoding="utf-8") as out:
    for line in f:
        business = json.loads(line)

        categories = business.get("categories") or ""
        city = business.get("city")

        if city == CITY and CATEGORY in categories:
            business_ids.add(business["business_id"])
            out.write(json.dumps(business) + "\n")

        if len(business_ids) >= MAX_BUSINESSES:
            break

print(f"Selected businesses: {len(business_ids)}")

print("Filtering reviews...")

review_count = 0

with REVIEW_FILE.open("r", encoding="utf-8") as f, REVIEW_OUT.open("w", encoding="utf-8") as out:
    for line in f:
        review = json.loads(line)

        if review.get("business_id") in business_ids:
            user_ids.add(review["user_id"])
            out.write(json.dumps(review) + "\n")
            review_count += 1

        if review_count >= MAX_REVIEWS:
            break

print(f"Selected reviews: {review_count}")
print(f"Selected users: {len(user_ids)}")

print("Filtering users...")

user_count = 0

with USER_FILE.open("r", encoding="utf-8") as f, USER_OUT.open("w", encoding="utf-8") as out:
    for line in f:
        user = json.loads(line)

        if user.get("user_id") in user_ids:
            out.write(json.dumps(user) + "\n")
            user_count += 1

print(f"Selected users written: {user_count}")
print("Done.")