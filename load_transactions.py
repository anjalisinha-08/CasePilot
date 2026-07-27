from src.config.snowflake_connection import SnowflakeConnection
from src.simulator.transaction_generator import (
    generate_transactions,
    insert_transactions_to_snowflake,
)

with SnowflakeConnection() as conn:

    # 1. Fetch Customers in pages of 1,000
    customers_raw = []
    limit = 1000
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT CUSTOMER_ID, PERSONA, CITY
            FROM RAW.CUSTOMER
            ORDER BY CUSTOMER_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        customers_raw.extend(rows)
        offset += limit

    # 2. Fetch Accounts in pages of 1,000
    accounts_raw = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_TYPE, BALANCE
            FROM RAW.ACCOUNT
            ORDER BY ACCOUNT_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        accounts_raw.extend(rows)
        offset += limit

    # 3. Fetch Merchants in pages of 1,000
    merchants_raw = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT MERCHANT_ID, MERCHANT_NAME, CITY, COUNTRY, CATEGORY
            FROM RAW.MERCHANT
            ORDER BY MERCHANT_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        merchants_raw.extend(rows)
        offset += limit

    # 4. Fetch Devices in pages of 1,000
    devices_raw = []
    offset = 0
    while True:
        rows = conn.execute_query(f"""
            SELECT DEVICE_ID, CUSTOMER_ID, DEVICE_TYPE, IS_TRUSTED
            FROM RAW.DEVICE
            ORDER BY DEVICE_ID
            LIMIT {limit} OFFSET {offset}
        """)
        if not rows:
            break
        devices_raw.extend(rows)
        offset += limit

    customers = [
        {
            "CUSTOMER_ID": r[0],
            "PERSONA": r[1],
            "CITY": r[2]
        }
        for r in customers_raw
    ]

    accounts = [
        {
            "ACCOUNT_ID": r[0],
            "CUSTOMER_ID": r[1],
            "ACCOUNT_TYPE": r[2],
            "BALANCE": float(r[3])
        }
        for r in accounts_raw
    ]

    merchants = [
        {
            "MERCHANT_ID": r[0],
            "MERCHANT_NAME": r[1],
            "CITY": r[2],
            "COUNTRY": r[3],
            "CATEGORY": r[4]
        }
        for r in merchants_raw
    ]

    devices = [
        {
            "DEVICE_ID": r[0],
            "CUSTOMER_ID": r[1],
            "DEVICE_TYPE": r[2],
            "IS_TRUSTED": r[3]
        }
        for r in devices_raw
    ]

    print("Generating 500,000 transactions (this may take a minute)...")
    transactions = generate_transactions(
        customers,
        accounts,
        merchants,
        devices
    )

    print("Uploading transactions to Snowflake in chunks...")
    rows = insert_transactions_to_snowflake(
        transactions,
        conn
    )

print(f"{rows} transactions inserted successfully.")
