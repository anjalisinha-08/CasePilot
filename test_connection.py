from src.config.snowflake_connection import SnowflakeConnection

try:
    with SnowflakeConnection() as conn:
        result = conn.execute_query(
            "SELECT CURRENT_VERSION(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
        )

        print("SUCCESS ✅")
        print(result)

except Exception as e:
    print("FAILED ❌")
    print(e)

