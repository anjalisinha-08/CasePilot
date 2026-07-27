"""
CasePilot — Clear Preloaded Transaction and Investigation Data
===============================================================
Truncates all transactions, alerts, cases, enrichments, intelligence,
recoveries, and notification logs in Snowflake so CasePilot starts in
an empty state as required.
"""

import logging
from src.config.snowflake_connection import SnowflakeConnection

logging.basicConfig(level=logging.INFO)

TABLES_TO_TRUNCATE = [
    "RAW.TRANSACTION",
    "ALERTS.ALERT",
    "INVESTIGATION.INVESTIGATION_CASE",
    "INVESTIGATION.CASE_ENRICHMENT",
    "ANALYTICS.CASE_INTELLIGENCE",
    "INVESTIGATION.FRAUD_RECOVERY",
    "INVESTIGATION.NOTIFICATION_LOG",
]


def clear_data():
    conn = SnowflakeConnection()
    conn.connect()
    try:
        cursor = conn.get_connection().cursor()
        for table in TABLES_TO_TRUNCATE:
            try:
                logging.info(f"Truncating {table}...")
                cursor.execute(f"TRUNCATE TABLE CASEPILOT_DB.{table}")
            except Exception as e:
                logging.warning(f"Could not truncate {table}: {e}")
        conn.get_connection().commit()
        cursor.close()
        logging.info("All preloaded transaction, alert, case, and recovery data cleared successfully.")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    clear_data()
