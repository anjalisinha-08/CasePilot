from src.config.snowflake_connection import SnowflakeConnection
from src.simulator.customer_generator import (
    generate_customers,
    insert_customers_to_snowflake,
)

customers = generate_customers()

with SnowflakeConnection() as conn:
    rows = insert_customers_to_snowflake(customers, conn)

print(f"{rows} customers inserted successfully.")
