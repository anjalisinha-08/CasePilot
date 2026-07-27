from src.config.snowflake_connection import SnowflakeConnection
from src.investigation.case_generator import (
    generate_cases,
    insert_cases_to_snowflake,
)

with SnowflakeConnection() as conn:

    alerts_raw = conn.execute_query("""
        SELECT
            ALERT_ID,
            TXN_ID,
            ACCOUNT_ID,
            CUSTOMER_ID,
            ALERT_TYPE,
            ALERT_DESCRIPTION,
            SEVERITY,
            RULE_VERSION,
            TRIGGERED_AMOUNT,
            TRIGGERED_THRESHOLD,
            STATUS,
            CREATED_AT,
            UPDATED_AT
        FROM ALERTS.ALERT
    """)

    alerts = [
        {
            "ALERT_ID": r[0],
            "TXN_ID": r[1],
            "ACCOUNT_ID": r[2],
            "CUSTOMER_ID": r[3],
            "ALERT_TYPE": r[4],
            "ALERT_DESCRIPTION": r[5],
            "SEVERITY": r[6],
            "RULE_VERSION": r[7],
            "TRIGGERED_AMOUNT": r[8],
            "TRIGGERED_THRESHOLD": r[9],
            "STATUS": r[10],
            "CREATED_AT": r[11].strftime("%Y-%m-%d %H:%M:%S") if r[11] else None,
            "UPDATED_AT": r[12].strftime("%Y-%m-%d %H:%M:%S") if r[12] else None,
        }
        for r in alerts_raw
    ]

    cases = generate_cases(alerts)

    rows = insert_cases_to_snowflake(
        cases,
        conn
    )

print(f"{rows} cases inserted successfully.")
