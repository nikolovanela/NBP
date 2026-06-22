import json
import redis


def get_client():
    return redis.Redis(host="localhost", port=6379, decode_responses=True)


def rget(r, key):
    """Get a key and parse JSON. Returns None if key does not exist."""
    value = r.get(key)
    return json.loads(value) if value else None


def main():
    r = get_client()

    city_key = "city_category:Philadelphia:Restaurants"

    # ── QUERY 1: Restaurants in Philadelphia ────────────────────────────────
    print("=== QUERY 1: Restaurants in Philadelphia ===")

    city_result = rget(r, city_key)

    if not city_result:
        print("Key not found. Make sure you have run import_yelp_redis.py first.")
        return

    business_ids = city_result["business_ids"]
    print(f"Key: {city_key}")
    print(f"Total restaurants found: {len(business_ids)}")
    print(f"First 3 business ids: {business_ids[:3]}")

    first_business_id = business_ids[0]

    # ── QUERY 2: Business by ID ──────────────────────────────────────────────
    print("\n=== QUERY 2: Business by ID ===")

    business = rget(r, f"business:{first_business_id}")

    if business:
        print(f"Business ID: {first_business_id}")
        print(f"Name: {business.get('name')}")
        print(f"City: {business.get('city')}")
        print(f"Stars: {business.get('stars')}")
        print(f"Review count: {business.get('review_count')}")
        print(f"Categories: {business.get('categories')}")

    # ── QUERY 3: Reviews for business ───────────────────────────────────────
    print("\n=== QUERY 3: Reviews for business ===")

    reviews_result = rget(r, f"business_reviews:{first_business_id}")
    first_review_id = None

    if reviews_result:
        review_ids = reviews_result["review_ids"]
        print(f"Business ID: {first_business_id}")
        print(f"Total reviews stored for this business: {len(review_ids)}")
        print(f"First 3 review ids: {review_ids[:3]}")
        if review_ids:
            first_review_id = review_ids[0]

    # ── QUERY 4: Business statistics ────────────────────────────────────────
    print("\n=== QUERY 4: Business statistics ===")

    stats = rget(r, f"stats:business:{first_business_id}")

    if stats:
        print(f"Business ID: {stats.get('business_id')}")
        print(f"Review count: {stats.get('review_count')}")
        print(f"Average stars: {stats.get('avg_stars')}")

    # ── QUERY 5: Review by ID ────────────────────────────────────────────────
    first_user_id = None

    if first_review_id:
        print("\n=== QUERY 5: Review by ID ===")

        review = rget(r, f"review:{first_review_id}")

        if review:
            print(f"Review ID: {first_review_id}")
            print(f"Business ID: {review.get('business_id')}")
            print(f"User ID: {review.get('user_id')}")
            print(f"Stars: {review.get('stars')}")
            print(f"Text preview: {review.get('text', '')[:200]}...")
            first_user_id = review.get("user_id")

    # ── QUERY 6: User by ID ──────────────────────────────────────────────────
    if first_user_id:
        print("\n=== QUERY 6: User by ID ===")

        user = rget(r, f"user:{first_user_id}")

        if user:
            print(f"User ID: {first_user_id}")
            print(f"Name: {user.get('name')}")
            print(f"Review count: {user.get('review_count')}")
            print(f"Average stars: {user.get('average_stars')}")


if __name__ == "__main__":
    main()
