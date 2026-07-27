"""
CasePilot — Real-Time Pipeline Runner
========================================
Monitors for new investigation cases that lack enrichment/intelligence
and automatically processes them through the full pipeline:

    New Cases (no enrichment) → Enrich → Score → Generate Intelligence

This complements the Snowflake Tasks which only handle:
    Transactions → Alerts → Cases

The enrichment + intelligence steps require Python logic that can't
run inside Snowflake Tasks, so this script fills that gap.

Usage:
    python -m src.pipeline.realtime_pipeline

    Options (via environment or defaults):
        PIPELINE_INTERVAL_SEC=15    Seconds between pipeline runs
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.snowflake_connection import SnowflakeConnection
from src.investigation.case_enrichment import (
    _build_customer_profile, _build_account_profile, _build_txn_history,
    _build_merchant_history, _build_device_history, _build_previous_alerts,
    _build_historical_stats,
)
from src.intelligence.priority_scoring import calculate_priority_score
from src.intelligence.case_summary import (
    _generate_summary, _generate_recommendations,
    _generate_timeline, _generate_key_findings,
)
from src.utils.helpers import generate_uuid, setup_logging

logger = logging.getLogger(__name__)

INTERVAL_SEC = int(os.getenv("PIPELINE_INTERVAL_SEC", "15"))


def _fetch_unenriched_cases(conn):
    """Find cases that don't have enrichment records yet."""
    query = """
        SELECT ic.CASE_ID, ic.ALERT_ID, ic.CUSTOMER_ID, ic.ACCOUNT_ID
        FROM CASEPILOT_DB.INVESTIGATION.INVESTIGATION_CASE ic
        LEFT JOIN CASEPILOT_DB.INVESTIGATION.CASE_ENRICHMENT ce
            ON ic.CASE_ID = ce.CASE_ID
        WHERE ce.CASE_ID IS NULL
        ORDER BY ic.CREATED_AT DESC
        LIMIT 50
    """
    rows = conn.execute_query(query)
    return [
        {"CASE_ID": r[0], "ALERT_ID": r[1], "CUSTOMER_ID": r[2], "ACCOUNT_ID": r[3]}
        for r in rows
    ]


def _fetch_alert(conn, alert_id):
    """Fetch a single alert record."""
    query = f"""
        SELECT ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
               ALERT_DESCRIPTION, SEVERITY, TRIGGERED_AMOUNT, STATUS, CREATED_AT
        FROM CASEPILOT_DB.ALERTS.ALERT
        WHERE ALERT_ID = '{alert_id}'
    """
    rows = conn.execute_query(query)
    if not rows:
        return {}
    r = rows[0]
    return {
        "ALERT_ID": r[0], "TXN_ID": r[1], "ACCOUNT_ID": r[2], "CUSTOMER_ID": r[3],
        "ALERT_TYPE": r[4], "ALERT_DESCRIPTION": r[5], "SEVERITY": r[6],
        "TRIGGERED_AMOUNT": r[7], "STATUS": r[8], "CREATED_AT": str(r[9]),
    }


def _fetch_customer_data(conn, customer_id):
    """Fetch all data needed for enrichment of a single customer."""
    # Customer
    rows = conn.execute_query(f"""
        SELECT CUSTOMER_ID, FIRST_NAME, LAST_NAME, EMAIL, PHONE, PERSONA,
               CITY, STATE, COUNTRY, ANNUAL_INCOME, OCCUPATION,
               KYC_STATUS, RISK_RATING, CREATED_AT, IS_ACTIVE
        FROM CASEPILOT_DB.RAW.CUSTOMER WHERE CUSTOMER_ID = '{customer_id}'
    """)
    customer = None
    if rows:
        r = rows[0]
        customer = {
            "CUSTOMER_ID": r[0], "FIRST_NAME": r[1], "LAST_NAME": r[2],
            "EMAIL": r[3], "PHONE": r[4], "PERSONA": r[5], "CITY": r[6],
            "STATE": r[7], "COUNTRY": r[8], "ANNUAL_INCOME": float(r[9]) if r[9] else 0,
            "OCCUPATION": r[10], "KYC_STATUS": r[11], "RISK_RATING": r[12],
            "CREATED_AT": str(r[13]), "IS_ACTIVE": r[14],
        }

    # Accounts
    rows = conn.execute_query(f"""
        SELECT ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_TYPE, ACCOUNT_NUMBER,
               IFSC_CODE, BALANCE, CURRENCY, ACCOUNT_STATUS, OPENED_AT
        FROM CASEPILOT_DB.RAW.ACCOUNT WHERE CUSTOMER_ID = '{customer_id}'
    """)
    accounts = [
        {"ACCOUNT_ID": r[0], "CUSTOMER_ID": r[1], "ACCOUNT_TYPE": r[2],
         "ACCOUNT_NUMBER": r[3], "IFSC_CODE": r[4], "BALANCE": float(r[5]) if r[5] else 0,
         "CURRENCY": r[6], "ACCOUNT_STATUS": r[7], "OPENED_AT": str(r[8])}
        for r in rows
    ]

    # Transactions (last 90 days)
    rows = conn.execute_query(f"""
        SELECT TXN_ID, ACCOUNT_ID, CUSTOMER_ID, MERCHANT_ID, DEVICE_ID,
               AMOUNT, CHANNEL, TXN_TIMESTAMP, DESCRIPTION,
               MERCHANT_CITY, IS_INTERNATIONAL
        FROM CASEPILOT_DB.RAW.TRANSACTION
        WHERE CUSTOMER_ID = '{customer_id}'
          AND TXN_TIMESTAMP >= DATEADD(day, -90, CURRENT_TIMESTAMP())
        ORDER BY TXN_TIMESTAMP DESC LIMIT 200
    """)
    transactions = [
        {"TXN_ID": r[0], "ACCOUNT_ID": r[1], "CUSTOMER_ID": r[2],
         "MERCHANT_ID": r[3], "DEVICE_ID": r[4], "AMOUNT": float(r[5]) if r[5] else 0,
         "CHANNEL": r[6], "TXN_TIMESTAMP": str(r[7]), "DESCRIPTION": r[8],
         "MERCHANT_CITY": r[9], "IS_INTERNATIONAL": r[10]}
        for r in rows
    ]

    # Merchants (used by this customer)
    merchant_ids = list(set(t["MERCHANT_ID"] for t in transactions if t["MERCHANT_ID"]))
    merchants = []
    if merchant_ids:
        ids_str = ",".join(f"'{mid}'" for mid in merchant_ids[:50])
        rows = conn.execute_query(f"""
            SELECT MERCHANT_ID, MERCHANT_NAME, CATEGORY, RISK_LEVEL
            FROM CASEPILOT_DB.RAW.MERCHANT WHERE MERCHANT_ID IN ({ids_str})
        """)
        merchants = [
            {"MERCHANT_ID": r[0], "MERCHANT_NAME": r[1], "CATEGORY": r[2], "RISK_LEVEL": r[3]}
            for r in rows
        ]

    # Devices
    rows = conn.execute_query(f"""
        SELECT DEVICE_ID, CUSTOMER_ID, DEVICE_TYPE, DEVICE_NAME, OS,
               IP_ADDRESS, CITY, IS_TRUSTED, FIRST_SEEN, LAST_SEEN
        FROM CASEPILOT_DB.RAW.DEVICE WHERE CUSTOMER_ID = '{customer_id}'
    """)
    devices = [
        {"DEVICE_ID": r[0], "CUSTOMER_ID": r[1], "DEVICE_TYPE": r[2],
         "DEVICE_NAME": r[3], "OS": r[4], "IP_ADDRESS": r[5], "CITY": r[6],
         "IS_TRUSTED": r[7], "FIRST_SEEN": str(r[8]), "LAST_SEEN": str(r[9])}
        for r in rows
    ]

    # Previous alerts
    rows = conn.execute_query(f"""
        SELECT ALERT_ID, ALERT_TYPE, SEVERITY, STATUS,
               ALERT_DESCRIPTION, CREATED_AT
        FROM CASEPILOT_DB.ALERTS.ALERT
        WHERE CUSTOMER_ID = '{customer_id}'
        ORDER BY CREATED_AT DESC LIMIT 20
    """)
    alerts = [
        {"ALERT_ID": r[0], "alert_type": r[1], "severity": r[2],
         "status": r[3], "description": str(r[4])[:200], "created_at": str(r[5])}
        for r in rows
    ]

    return customer, accounts, transactions, merchants, devices, alerts


def _process_case(conn, case):
    """Process a single case through enrichment → scoring → intelligence."""
    case_id = case["CASE_ID"]
    alert_id = case["ALERT_ID"]
    customer_id = case["CUSTOMER_ID"]

    # 1. Fetch alert
    alert = _fetch_alert(conn, alert_id)
    if not alert:
        logger.warning(f"Alert {alert_id} not found for case {case_id}, skipping.")
        return False

    # 2. Fetch customer data
    customer, accounts, transactions, merchants, devices, prev_alerts = \
        _fetch_customer_data(conn, customer_id)

    if not customer:
        logger.warning(f"Customer {customer_id} not found, skipping case {case_id}.")
        return False

    # 3. Build enrichment
    customers_list = [customer]
    enrichment = {
        "CUSTOMER_PROFILE": _build_customer_profile(customer_id, customers_list),
        "ACCOUNT_PROFILE": _build_account_profile(customer_id, accounts),
        "TXN_HISTORY": _build_txn_history(customer_id, transactions),
        "MERCHANT_HISTORY": _build_merchant_history(customer_id, transactions, merchants),
        "DEVICE_HISTORY": _build_device_history(customer_id, devices),
        "PREVIOUS_ALERTS": prev_alerts,
        "HISTORICAL_STATS": _build_historical_stats(customer_id, transactions, prev_alerts),
    }

    # 4. Insert enrichment
    enrichment_id = generate_uuid()
    conn.execute_non_query(f"""
        INSERT INTO CASEPILOT_DB.INVESTIGATION.CASE_ENRICHMENT (
            ENRICHMENT_ID, CASE_ID, CUSTOMER_PROFILE, ACCOUNT_PROFILE,
            TXN_HISTORY, MERCHANT_HISTORY, DEVICE_HISTORY,
            PREVIOUS_ALERTS, HISTORICAL_STATS, ENRICHED_AT
        )
        SELECT
            '{enrichment_id}', '{case_id}',
            PARSE_JSON('{json.dumps(enrichment["CUSTOMER_PROFILE"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["ACCOUNT_PROFILE"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["TXN_HISTORY"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["MERCHANT_HISTORY"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["DEVICE_HISTORY"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["PREVIOUS_ALERTS"]).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(enrichment["HISTORICAL_STATS"]).replace(chr(39), chr(39)+chr(39))}'),
            CURRENT_TIMESTAMP()
    """)

    # 5. Calculate priority score
    score_result = calculate_priority_score(alert, enrichment)

    # 6. Generate intelligence
    summary = _generate_summary(alert, enrichment, score_result)
    recommendations = _generate_recommendations(alert, score_result)
    timeline = _generate_timeline(alert, enrichment)
    key_findings = _generate_key_findings(alert, enrichment, score_result)

    # 7. Insert intelligence
    intelligence_id = generate_uuid()
    conn.execute_non_query(f"""
        INSERT INTO CASEPILOT_DB.ANALYTICS.CASE_INTELLIGENCE (
            INTELLIGENCE_ID, CASE_ID, ALERT_ID, PRIORITY_SCORE,
            RISK_BAND, INVESTIGATION_SUMMARY, RECOMMENDATIONS,
            TIMELINE, KEY_FINDINGS, MODEL_VERSION, GENERATED_AT
        )
        SELECT
            '{intelligence_id}', '{case_id}', '{alert_id}',
            {score_result['priority_score']},
            '{score_result['risk_band']}',
            '{summary.replace(chr(39), chr(39)+chr(39))}',
            PARSE_JSON('{json.dumps(recommendations).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(timeline).replace(chr(39), chr(39)+chr(39))}'),
            PARSE_JSON('{json.dumps(key_findings).replace(chr(39), chr(39)+chr(39))}'),
            '1.0',
            CURRENT_TIMESTAMP()
    """)

    return True


def run_pipeline():
    """
    Main loop: continuously check for unenriched cases and process them.

    Press Ctrl+C to stop.
    """
    setup_logging()
    logger.info("=" * 60)
    logger.info("🔄 CasePilot Real-Time Pipeline Starting")
    logger.info(f"   Check interval: {INTERVAL_SEC}s")
    logger.info("=" * 60)

    conn = SnowflakeConnection()
    conn.connect()

    total_processed = 0

    try:
        while True:
            # Find unenriched cases
            cases = _fetch_unenriched_cases(conn)

            if cases:
                logger.info(f"📋 Found {len(cases)} unenriched cases. Processing...")

                for case in cases:
                    try:
                        success = _process_case(conn, case)
                        if success:
                            total_processed += 1
                            logger.info(
                                f"  ✅ Case {case['CASE_ID'][:8]}... processed "
                                f"(total: {total_processed})"
                            )
                    except Exception as e:
                        logger.error(f"  ❌ Error processing case {case['CASE_ID'][:8]}...: {e}")
            else:
                logger.debug("No new cases to process.")

            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        logger.info(f"\n🛑 Pipeline stopped. Total cases processed: {total_processed}")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    run_pipeline()
