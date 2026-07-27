from src.config.snowflake_connection import SnowflakeConnection
from src.alerts.alert_engine import (
    run_alert_engine,
    insert_alerts_to_snowflake,
)

with SnowflakeConnection() as conn:

    transactions_raw = conn.execute_query("""
        SELECT
            TXN_ID,
            ACCOUNT_ID,
            CUSTOMER_ID,
            MERCHANT_ID,
            DEVICE_ID,
            AMOUNT,
            CURRENCY,
            TXN_TYPE,
            CHANNEL,
            STATUS,
            TXN_TIMESTAMP,
            DESCRIPTION,
            MERCHANT_CITY,
            MERCHANT_COUNTRY,
            LATITUDE,
            LONGITUDE,
            IS_INTERNATIONAL
        FROM RAW.TRANSACTION
	LIMIT 100
    """)

    devices_raw = conn.execute_query("""
        SELECT
            DEVICE_ID,
            CUSTOMER_ID,
            IS_TRUSTED
        FROM RAW.DEVICE
    """)

    transactions = [
        {
            "TXN_ID": r[0],
            "ACCOUNT_ID": r[1],
            "CUSTOMER_ID": r[2],
            "MERCHANT_ID": r[3],
            "DEVICE_ID": r[4],
            "AMOUNT": float(r[5]),
            "CURRENCY": r[6],
            "TXN_TYPE": r[7],
            "CHANNEL": r[8],
            "STATUS": r[9],
	    "TXN_TIMESTAMP": r[10].strftime("%Y-%m-%d %H:%M:%S"),
            "DESCRIPTION": r[11],
            "MERCHANT_CITY": r[12],
            "MERCHANT_COUNTRY": r[13],
            "LATITUDE": r[14],
            "LONGITUDE": r[15],
            "IS_INTERNATIONAL": r[16],
        }
        for r in transactions_raw
    ]

    devices = [
        {
            "DEVICE_ID": r[0],
            "CUSTOMER_ID": r[1],
            "IS_TRUSTED": r[2],
        }
        for r in devices_raw
    ]

    alerts = run_alert_engine(
        transactions,
        devices
    )

    rows = insert_alerts_to_snowflake(
        alerts,
        conn
    )

print(f"{rows} alerts inserted successfully.")
