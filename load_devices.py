from src.config.snowflake_connection import SnowflakeConnection
from src.simulator.device_generator import (
    generate_devices,
    insert_devices_to_snowflake,
)

with SnowflakeConnection() as conn:
    customers = []
    limit = 1000
    offset = 0
    while True:
        rows = conn.execute_query(
            f"""
            SELECT CUSTOMER_ID, CITY, CREATED_AT
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
            "CITY": row[1],
            "CREATED_AT": row[2].strftime("%Y-%m-%d %H:%M:%S")
        }
        for row in customers
    ]

    devices = generate_devices(customer_records)

    rows = insert_devices_to_snowflake(
        devices,
        conn
    )

print(f"{rows} devices inserted successfully.")

