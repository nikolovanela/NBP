"""
test_oracle.py
--------------
Tests the Oracle NoSQL connection and basic operations.
Compatible with borneo 5.4.3 — uses plain dict instead of MapValue.
Equivalent of test_redis.py.
"""

import json
from borneo import (NoSQLHandle, NoSQLHandleConfig,
                    PutRequest, GetRequest, DeleteRequest,
                    TableRequest, TableLimits)
from borneo.kv import StoreAccessTokenProvider

ENDPOINT = "http://localhost:8080"
TABLE    = "test_kv"


def get_client():
    provider = StoreAccessTokenProvider()
    config   = NoSQLHandleConfig(ENDPOINT, provider)
    return NoSQLHandle(config)


def main():
    print("=" * 50)
    print("Testing Oracle NoSQL Connection")
    print("=" * 50)

    handle = get_client()

    # Create temp test table
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            kv_key   STRING,
            kv_value STRING,
            PRIMARY KEY(kv_key)
        )
    """
    req = TableRequest().set_statement(ddl).set_table_limits(TableLimits(50, 50, 1))
    res = handle.table_request(req)
    res.wait_for_completion(handle, 30000, 1000)
    print(f"[OK] Table '{TABLE}' ready.")

    # PUT — plain dict
    row     = {"kv_key": "test:hello", "kv_value": json.dumps({"message": "Oracle NoSQL works!"})}
    put_req = PutRequest().set_table_name(TABLE).set_value(row)
    handle.put(put_req)
    print("[OK] PUT test:hello")

    # GET — plain dict as key
    key     = {"kv_key": "test:hello"}
    get_req = GetRequest().set_table_name(TABLE).set_key(key)
    get_res = handle.get(get_req)
    val     = json.loads(get_res.get_value()["kv_value"])
    print(f"[OK] GET test:hello => {val}")

    # DELETE
    del_req = DeleteRequest().set_table_name(TABLE).set_key(key)
    handle.delete(del_req)
    print("[OK] DELETE test:hello")

    # Drop temp table
    drop = TableRequest().set_statement(f"DROP TABLE IF EXISTS {TABLE}")
    res  = handle.table_request(drop)
    res.wait_for_completion(handle, 30000, 1000)
    print(f"[OK] Table '{TABLE}' dropped.")

    handle.close()
    print("\n[OK] All connection tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
