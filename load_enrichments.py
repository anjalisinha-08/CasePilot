from src.config.snowflake_connection import SnowflakeConnection
from src.investigation.case_enrichment import (
    enrich_cases,
    insert_enrichments_to_snowflake,
)

with SnowflakeConnection() as conn:

    cases_raw = conn.execute_query("""
        SELECT
            CASE_ID,
            ALERT_ID,
            CUSTOMER_ID,
            ACCOUNT_ID,
            CASE_NUMBER
        FROM INVESTIGATION.INVESTIGATION_CASE
    """)

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

    customers_raw = conn.execute_query("""
        SELECT *
        FROM RAW.CUSTOMER
        LIMIT 100
    """)

    accounts_raw = conn.execute_query("""
        SELECT *
        FROM RAW.ACCOUNT
        LIMIT 150
    """)

    transactions_raw = conn.execute_query("""
        SELECT *
        FROM RAW.TRANSACTION
        LIMIT 100
    """)

    merchants_raw = conn.execute_query("""
        SELECT *
        FROM RAW.MERCHANT
        LIMIT 50
    """)

    devices_raw = conn.execute_query("""
        SELECT *
        FROM RAW.DEVICE
        LIMIT 300
    """)

    cases = [
        {
            "CASE_ID": r[0],
            "ALERT_ID": r[1],
            "CUSTOMER_ID": r[2],
            "ACCOUNT_ID": r[3],
            "CASE_NUMBER": r[4],
        }
        for r in cases_raw
    ]

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
            "CREATED_AT": r[11].strftime("%Y-%m-%d %H:%M:%S")
            if r[11] else None,
            "UPDATED_AT": r[12].strftime("%Y-%m-%d %H:%M:%S")
            if r[12] else None,
        }
        for r in alerts_raw
    ]

    customers = [
        {
            "CUSTOMER_ID": r[0],
            "FIRST_NAME": r[1],
            "LAST_NAME": r[2],
            "EMAIL": r[3],
            "PHONE": r[4],
            "PERSONA": r[5],
            "DATE_OF_BIRTH": str(r[6]) if r[6] else None,
            "CITY": r[7],
            "STATE": r[8],
            "COUNTRY": r[9],
            "PIN_CODE": r[10],
            "ANNUAL_INCOME": float(r[11]) if r[11] is not None else 0,
            "OCCUPATION": r[12],
            "KYC_STATUS": r[13],
            "RISK_RATING": r[14],
            "PAN_NUMBER": r[15],
            "AADHAR_HASH": r[16],
            "CREATED_AT": r[17].strftime("%Y-%m-%d %H:%M:%S")
            if r[17] else None,
            "UPDATED_AT": r[18].strftime("%Y-%m-%d %H:%M:%S")
            if r[18] else None,
            "IS_ACTIVE": r[19],
        }
        for r in customers_raw
    ]

    accounts = [
        {
            "ACCOUNT_ID": r[0],
            "CUSTOMER_ID": r[1],
            "ACCOUNT_TYPE": r[2],
            "ACCOUNT_NUMBER": r[3],
            "IFSC_CODE": r[4],
            "BRANCH_CODE": r[5],
            "BALANCE": float(r[6]) if r[6] is not None else 0,
            "CURRENCY": r[7],
            "ACCOUNT_STATUS": r[8],
            "OPENED_AT": r[9].strftime("%Y-%m-%d %H:%M:%S")
            if r[9] else None,
            "UPDATED_AT": r[10].strftime("%Y-%m-%d %H:%M:%S")
            if r[10] else None,
        }
        for r in accounts_raw
    ]

    transactions = [
        {
            "TXN_ID": r[0],
            "ACCOUNT_ID": r[1],
            "CUSTOMER_ID": r[2],
            "MERCHANT_ID": r[3],
            "DEVICE_ID": r[4],
            "AMOUNT": float(r[5]) if r[5] is not None else 0,
            "CURRENCY": r[6],
            "TXN_TYPE": r[7],
            "CHANNEL": r[8],
            "STATUS": r[9],
            "TXN_TIMESTAMP": r[10].strftime("%Y-%m-%d %H:%M:%S")
            if r[10] else None,
            "DESCRIPTION": r[11],
            "MERCHANT_CITY": r[12],
            "MERCHANT_COUNTRY": r[13],
            "LATITUDE": float(r[14]) if r[14] is not None else None,
            "LONGITUDE": float(r[15]) if r[15] is not None else None,
            "IS_INTERNATIONAL": r[16],
        }
        for r in transactions_raw
    ]

    merchants = [
        {
            "MERCHANT_ID": r[0],
            "MERCHANT_NAME": r[1],
            "CATEGORY": r[2],
            "MCC_CODE": r[3],
            "CITY": r[4],
            "STATE": r[5],
            "COUNTRY": r[6],
            "RISK_LEVEL": r[7],
            "IS_ACTIVE": r[8],
            "REGISTERED_AT": r[9].strftime("%Y-%m-%d %H:%M:%S")
            if r[9] else None,
        }
        for r in merchants_raw
    ]

    devices = [
        {
            "DEVICE_ID": r[0],
            "CUSTOMER_ID": r[1],
            "DEVICE_TYPE": r[2],
            "DEVICE_NAME": r[3],
            "OS": r[4],
            "BROWSER": r[5],
            "IP_ADDRESS": r[6],
            "CITY": r[7],
            "COUNTRY": r[8],
            "IS_TRUSTED": r[9],
            "FIRST_SEEN": r[10].strftime("%Y-%m-%d %H:%M:%S")
            if r[10] else None,
            "LAST_SEEN": r[11].strftime("%Y-%m-%d %H:%M:%S")
            if r[11] else None,
        }
        for r in devices_raw
    ]

    enrichments = enrich_cases(
        cases,
        alerts,
        customers,
        accounts,
        transactions,
        merchants,
        devices,
    )

    rows = insert_enrichments_to_snowflake(
        enrichments,
        conn
    )

print(f"{rows} enrichments inserted successfully.")
