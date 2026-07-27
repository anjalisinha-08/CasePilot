from src.config.snowflake_connection import SnowflakeConnection
from src.simulator.merchant_generator import (
    generate_merchants,
    insert_merchants_to_snowflake,
)

with SnowflakeConnection() as conn:
    merchants = generate_merchants()
    rows = insert_merchants_to_snowflake(
        merchants,
        conn
    )

print(f"{rows} merchants inserted successfully.")
