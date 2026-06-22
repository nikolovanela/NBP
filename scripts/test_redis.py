import redis
import json

def get_client():
    return redis.Redis(host="localhost", port=6380, decode_responses=True)

def main():
    r = get_client()

    # Test connection
    r.ping()
    print("Redis connection OK.")

    # Write a test key
    r.set("test:hello", json.dumps({"message": "Redis works!"}))

    # Read it back
    value = r.get("test:hello")
    print("Test key written and read back:")
    print(json.loads(value))

    # Cleanup
    r.delete("test:hello")
    print("Test key deleted. All good.")

if __name__ == "__main__":
    main()
