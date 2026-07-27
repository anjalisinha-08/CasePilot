from src.config.snowflake_connection import SnowflakeConnection
from src.simulator.account_generator import (
    generate_accounts,
    insert_accounts_to_snowflake,
)

with SnowflakeConnection() as conn:
    customers = []
    limit = 1000
    offset = 0
    while True:
        rows = conn.execute_query(
            f"""
            SELECT CUSTOMER_ID, PERSONA, CREATED_AT
            FROM RAW.CUSTOMER
            ORDER BY CUSTOMER_ID
            LIMIT {limit} OFFSET {offset}
            """
        )
        if not rows:
            break
        customers.extend(rows)
        offset += limit

    customer_records = [
        {
            "CUSTOMER_ID": row[0],
            "PERSONA": row[1],
            "CREATED_AT": row[2].strftime("%Y-%m-%d %H:%M:%S")
        }
        for row in customers
    ]

    accounts = generate_accounts(customer_records)

    rows = insert_accounts_to_snowflake(
        accounts,
        conn
    )

print(f"{rows} accounts inserted successfully.")
